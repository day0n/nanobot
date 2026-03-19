"""Session management for conversation history.

Persistence: MongoDB (primary) + Redis (cache layer).

Schema:
  - ``agent_sessions`` — one document per session (metadata only, no messages).
  - ``agent_session_messages`` — one document per message, append-only.

Write path is append-only: only newly added messages are ``insert_many``-ed.
Read path: Redis cache → MongoDB (dual-collection query) → create new.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


REDIS_SESSION_PREFIX = "nanobot:session:"
REDIS_SESSION_TTL = 60 * 60 * 24  # 24 hours


@dataclass
class Session:
    """
    A conversation session.

    Important: Messages are append-only for LLM cache efficiency.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    _persisted_count: int = field(default=0, repr=False)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    @staticmethod
    def _find_legal_start(messages: list[dict[str, Any]]) -> int:
        """Find first index where every tool result has a matching assistant tool_call."""
        declared: set[str] = set()
        start = 0
        for i, msg in enumerate(messages):
            role = msg.get("role")
            if role == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict) and tc.get("id"):
                        declared.add(str(tc["id"]))
            elif role == "tool":
                tid = msg.get("tool_call_id")
                if tid and str(tid) not in declared:
                    start = i + 1
                    declared.clear()
                    for prev in messages[start:i + 1]:
                        if prev.get("role") == "assistant":
                            for tc in prev.get("tool_calls") or []:
                                if isinstance(tc, dict) and tc.get("id"):
                                    declared.add(str(tc["id"]))
        return start

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """Return messages for LLM input, aligned to a legal tool-call boundary."""
        sliced = self.messages[-max_messages:] if max_messages > 0 else list(self.messages)

        # Drop leading non-user messages to avoid starting mid-turn when possible.
        for i, message in enumerate(sliced):
            if message.get("role") == "user":
                sliced = sliced[i:]
                break

        # Some providers reject orphan tool results if the matching assistant
        # tool_calls message fell outside the fixed-size history window.
        start = self._find_legal_start(sliced)
        if start:
            sliced = sliced[start:]

        out: list[dict[str, Any]] = []
        for m in sliced:
            entry: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name", "thinking_blocks", "reasoning_content"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self._persisted_count = 0
        self.updated_at = datetime.now()


# ---------------------------------------------------------------------------
# SessionManager — MongoDB (persistent) + Redis (cache)
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages conversation sessions with MongoDB + Redis.

    Read path:  Redis → MongoDB → create new
    Write path: append-only insert_many (new messages) + update_one (metadata) + Redis SET
    """

    def __init__(self, mongo_sessions_col, mongo_messages_col, redis_client) -> None:
        self._sessions_col = mongo_sessions_col
        self._messages_col = mongo_messages_col
        self._redis = redis_client

    # -- public API (all async) ------------------------------------------------

    async def get_or_create(self, key: str) -> Session:
        """Get an existing session or create a new one."""
        # 1. Redis cache
        session = await self._load_from_redis(key)
        if session is not None:
            return session

        # 2. MongoDB (dual-collection)
        session = await self._load_from_mongo(key)
        if session is not None:
            # Warm Redis cache
            await self._write_redis(session)
            return session

        # 3. New session
        session = Session(key=key)
        return session

    async def save(self, session: Session) -> None:
        """Persist new messages to MongoDB (append-only) and update Redis cache."""
        now = datetime.now()
        session.updated_at = now
        new_messages = session.messages[session._persisted_count:]

        try:
            # Upsert session metadata (no messages stored here)
            await self._sessions_col.update_one(
                {"_id": session.key},
                {
                    "$set": {
                        "user_id": self._extract_user_id(session.key),
                        "updated_at": now,
                        "metadata": session.metadata,
                    },
                    "$setOnInsert": {
                        "created_at": session.created_at,
                    },
                },
                upsert=True,
            )

            # Append only new messages
            if new_messages:
                base_seq = session._persisted_count
                docs = [
                    {
                        "session_key": session.key,
                        "seq": base_seq + i,
                        **msg,
                    }
                    for i, msg in enumerate(new_messages)
                ]
                await self._messages_col.insert_many(docs, ordered=True)
                session._persisted_count = len(session.messages)
        except Exception:
            logger.exception("Failed to save session {} to MongoDB", session.key)
            raise

        await self._write_redis(session)

    async def invalidate(self, key: str) -> None:
        """Remove session messages from MongoDB and Redis (for /new)."""
        try:
            await self._redis.delete(f"{REDIS_SESSION_PREFIX}{key}")
        except Exception:
            logger.warning("Failed to delete Redis cache for session {}", key)

        try:
            await self._messages_col.delete_many({"session_key": key})
            await self._sessions_col.update_one(
                {"_id": key},
                {"$set": {"updated_at": datetime.now(), "metadata": {}}},
            )
        except Exception:
            logger.warning("Failed to invalidate session {} in MongoDB", key)

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions (without messages) sorted by updated_at desc."""
        cursor = self._sessions_col.find({}).sort("updated_at", -1)
        sessions = []
        async for doc in cursor:
            sessions.append({
                "key": doc["_id"],
                "created_at": doc.get("created_at", ""),
                "updated_at": doc.get("updated_at", ""),
                "user_id": doc.get("user_id", ""),
            })
        return sessions

    # -- static helpers --------------------------------------------------------

    @staticmethod
    def _extract_user_id(key: str) -> str:
        """Extract user_id from session key for indexing.

        Key formats:
          api:{user_id}:{session_id}                 → user_id
          api:{user_id}:flow:{flow_id}:{session_id} → user_id
          telegram:{user_id}          → user_id
          discord:{user_id}           → user_id
          cli:direct                  → _local
          cron:{job_id}               → _system
          heartbeat                   → _system
          other                       → _default
        """
        if not key or ":" not in key:
            return "_system" if key == "heartbeat" else "_default"

        parts = key.split(":", 2)
        channel = parts[0]

        if channel == "api" and len(parts) >= 3:
            return parts[1]
        if channel in ("telegram", "discord") and len(parts) >= 2:
            return parts[1]
        if channel == "cli":
            return "_local"
        if channel == "cron":
            return "_system"

        return parts[1] if len(parts) >= 2 else "_default"

    # -- Redis helpers ---------------------------------------------------------

    async def _write_redis(self, session: Session) -> None:
        """Write session to Redis with TTL."""
        redis_key = f"{REDIS_SESSION_PREFIX}{session.key}"
        doc = {
            "_id": session.key,
            "user_id": self._extract_user_id(session.key),
            "messages": session.messages,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
            "_persisted_count": len(session.messages),
        }
        try:
            await self._redis.set(
                redis_key,
                json.dumps(doc, ensure_ascii=False),
                ex=REDIS_SESSION_TTL,
            )
        except Exception:
            logger.warning("Failed to write session {} to Redis", session.key)

    async def _load_from_redis(self, key: str) -> Session | None:
        """Try to load session from Redis cache."""
        redis_key = f"{REDIS_SESSION_PREFIX}{key}"
        try:
            raw = await self._redis.get(redis_key)
            if raw:
                doc = json.loads(raw)
                return self._doc_to_session(doc)
        except Exception:
            logger.warning("Failed to read session {} from Redis", key)
        return None

    # -- MongoDB helpers -------------------------------------------------------

    async def _load_from_mongo(self, key: str) -> Session | None:
        """Try to load session from MongoDB (dual-collection)."""
        try:
            meta_doc = await self._sessions_col.find_one({"_id": key})
            if not meta_doc:
                return None

            # Load all messages sorted by seq
            messages: list[dict[str, Any]] = []
            cursor = self._messages_col.find(
                {"session_key": key},
            ).sort("seq", 1)
            async for msg_doc in cursor:
                # Strip MongoDB-internal fields
                msg_doc.pop("_id", None)
                msg_doc.pop("session_key", None)
                msg_doc.pop("seq", None)
                messages.append(msg_doc)

            created = meta_doc.get("created_at")
            updated = meta_doc.get("updated_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated)

            session = Session(
                key=key,
                messages=messages,
                created_at=created or datetime.now(),
                updated_at=updated or datetime.now(),
                metadata=meta_doc.get("metadata", {}),
                _persisted_count=len(messages),
            )
            return session
        except Exception:
            logger.warning("Failed to load session {} from MongoDB", key)
        return None

    @staticmethod
    def _doc_to_session(doc: dict) -> Session:
        """Convert a Redis-cached document back to Session."""
        created = doc.get("created_at")
        updated = doc.get("updated_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)
        messages = doc.get("messages", [])
        return Session(
            key=doc["_id"],
            messages=messages,
            created_at=created or datetime.now(),
            updated_at=updated or datetime.now(),
            metadata=doc.get("metadata", {}),
            _persisted_count=doc.get("_persisted_count", len(messages)),
        )
