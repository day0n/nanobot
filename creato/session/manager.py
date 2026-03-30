"""Session management for conversation history.

Persistence: MongoDB (primary) + Redis (cache layer).

New schema (opencreator_agent database):
  - ``agent_sessions`` — one document per session (metadata only).
  - ``agent_messages`` — one document per message, append-only, all roles.
  - ``agent_tool_traces`` — one document per tool call execution.

Redis cache:
  - ``agent:session:meta:{session_id}`` — session metadata JSON (24h TTL).
  - ``agent:session:ctx:{session_id}`` — full message list JSON for LLM context (24h TTL).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from creato.schemas.messages import MessageList, StoredMessage
from creato.schemas.session import SessionMetaDoc, StoredMessageDoc, ToolTraceDoc


REDIS_META_PREFIX = "agent:session:meta:"
REDIS_CTX_PREFIX = "agent:session:ctx:"
REDIS_TTL = 60 * 60 * 24  # 24 hours


@dataclass
class Session:
    """
    A conversation session.

    Important: Messages are append-only for LLM cache efficiency.
    """

    session_id: str
    user_id: str
    workflow_id: str | None = None
    channel: str = "api"
    messages: list[StoredMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    summary: str | None = field(default=None)
    message_count: int = 0       # user + agent display messages only
    turn_count: int = 0          # total turns
    last_message_preview: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _persisted_count: int = field(default=0, repr=False)

    @staticmethod
    def _find_legal_start(messages: list[dict[str, Any]]) -> int:
        """Find first index where every tool result has a matching assistant tool_call."""
        declared: set[str] = set()
        start = 0
        for i, msg in enumerate(messages):
            role = msg.get("role")
            if role in ("assistant", "agent"):
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict) and tc.get("id"):
                        declared.add(str(tc["id"]))
            elif role == "tool":
                tid = msg.get("tool_call_id")
                if tid and str(tid) not in declared:
                    start = i + 1
                    declared.clear()
                    for prev in messages[start:i + 1]:
                        if prev.get("role") in ("assistant", "agent"):
                            for tc in prev.get("tool_calls") or []:
                                if isinstance(tc, dict) and tc.get("id"):
                                    declared.add(str(tc["id"]))
        return start

    def get_history(self, max_messages: int = 500) -> MessageList:
        """Return messages for LLM input, aligned to a legal tool-call boundary.

        Note: For LLM context, ``agent`` role messages are mapped back to ``assistant``
        since LLM APIs expect the standard ``assistant`` role.
        """
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
            role = m["role"]
            # Map "agent" back to "assistant" for LLM API compatibility
            if role == "agent":
                role = "assistant"
            entry: dict[str, Any] = {"role": role, "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name", "thinking_blocks", "reasoning_content"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self._persisted_count = 0
        self.summary = None
        self.message_count = 0
        self.turn_count = 0
        self.last_message_preview = None
        self.updated_at = datetime.now()


# ---------------------------------------------------------------------------
# SessionManager — MongoDB (persistent) + Redis (cache)
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages conversation sessions with MongoDB + Redis.

    Uses the new three-collection schema in opencreator_agent database:
      - agent_sessions: session metadata
      - agent_messages: all messages (user/agent/assistant/tool)
      - agent_tool_traces: tool execution traces

    Read path:  Redis ctx → MongoDB agent_messages → create new
    Write path: insert_many (new messages) + insert_many (traces) + update_one (session) + Redis SET
    """

    def __init__(
        self,
        sessions_col,
        messages_col,
        tool_traces_col,
        redis_client,
        # Legacy collections (kept for backward compat, can be None)
        legacy_sessions_col=None,
        legacy_messages_col=None,
    ) -> None:
        self._sessions_col = sessions_col
        self._messages_col = messages_col
        self._traces_col = tool_traces_col
        self._redis = redis_client
        # Legacy (unused in new code paths, kept for gradual migration)
        self._legacy_sessions_col = legacy_sessions_col
        self._legacy_messages_col = legacy_messages_col

    # -- public API (all async) ------------------------------------------------

    async def get_or_create(
        self,
        session_id: str,
        user_id: str = "",
        workflow_id: str | None = None,
        channel: str = "api",
    ) -> Session:
        """Get an existing session or create a new one."""
        # 1. Redis cache (ctx key has full messages)
        session = await self._load_from_redis(session_id)
        if session is not None:
            return session

        # 2. MongoDB (new agent database)
        session = await self._load_from_mongo(session_id)
        if session is not None:
            # Warm Redis cache
            await self._write_redis(session)
            return session

        # 3. New session
        session = Session(
            session_id=session_id,
            user_id=user_id,
            workflow_id=workflow_id,
            channel=channel,
        )
        return session

    async def save(
        self,
        session: Session,
        tool_traces: list[dict[str, Any]] | None = None,
    ) -> None:
        """Persist new messages to MongoDB (append-only) and update Redis cache.

        Args:
            session: The session to save.
            tool_traces: Optional list of tool trace documents to insert into agent_tool_traces.
        """
        now = datetime.now()
        session.updated_at = now
        new_messages = session.messages[session._persisted_count:]

        try:
            # Upsert session metadata (write-side validation)
            meta = SessionMetaDoc(
                user_id=session.user_id,
                workflow_id=session.workflow_id,
                channel=session.channel,
                summary=session.summary,
                message_count=session.message_count,
                turn_count=session.turn_count,
                last_message_preview=session.last_message_preview,
                created_at=session.created_at,
                updated_at=now,
                metadata=session.metadata,
            )
            set_fields = meta.model_dump(exclude_none=True)
            # Remove created_at from $set — it goes in $setOnInsert
            set_fields.pop("created_at", None)
            await self._sessions_col.update_one(
                {"_id": session.session_id},
                {
                    "$set": set_fields,
                    "$setOnInsert": {
                        "created_at": session.created_at,
                    },
                },
                upsert=True,
            )

            # Append only new messages (write-side validation)
            if new_messages:
                base_seq = session._persisted_count
                docs = [
                    {
                        "session_id": session.session_id,
                        "seq": base_seq + i,
                        **StoredMessageDoc.model_validate(msg).model_dump(exclude_none=True),
                    }
                    for i, msg in enumerate(new_messages)
                ]
                await self._messages_col.insert_many(docs, ordered=True)
                session._persisted_count = len(session.messages)

            # Insert tool traces (write-side validation)
            if tool_traces:
                validated_traces = [
                    ToolTraceDoc.model_validate(t).model_dump(exclude_none=True)
                    for t in tool_traces
                ]
                await self._traces_col.insert_many(validated_traces, ordered=False)

        except Exception:
            logger.exception("Failed to save session {} to MongoDB", session.session_id)
            raise

        await self._write_redis(session)

    async def invalidate(self, session_id: str) -> None:
        """Remove session messages from MongoDB and Redis (for /new)."""
        try:
            await self._redis.delete(f"{REDIS_CTX_PREFIX}{session_id}")
            await self._redis.delete(f"{REDIS_META_PREFIX}{session_id}")
        except Exception:
            logger.warning("Failed to delete Redis cache for session {}", session_id)

        try:
            await self._messages_col.delete_many({"session_id": session_id})
            await self._traces_col.delete_many({"session_id": session_id})
            await self._sessions_col.update_one(
                {"_id": session_id},
                {"$set": {
                    "updated_at": datetime.now(),
                    "metadata": {},
                    "summary": None,
                    "message_count": 0,
                    "turn_count": 0,
                    "last_message_preview": None,
                }},
            )
        except Exception:
            logger.warning("Failed to invalidate session {} in MongoDB", session_id)

    async def list_sessions(
        self,
        user_id: str,
        workflow_id: str | None = None,
        limit: int = 10,
        after_session_id: str | None = None,
    ) -> dict[str, Any]:
        """List sessions for a user with cursor-based lazy loading.

        Args:
            user_id: Filter by user.
            workflow_id: Optional — filter by workflow (canvas). When provided,
                only returns sessions belonging to that workflow.
            limit: Max sessions to return.
            after_session_id: Cursor — the session_id of the last item from the previous page.

        Returns:
            { "sessions": [...], "has_more": bool }
        """
        query: dict[str, Any] = {"user_id": user_id}
        if workflow_id is not None:
            query["workflow_id"] = workflow_id

        # Resolve cursor: look up the updated_at of the given session_id
        if after_session_id is not None:
            cursor_doc = await self._sessions_col.find_one(
                {"_id": after_session_id}, {"updated_at": 1}
            )
            if cursor_doc and cursor_doc.get("updated_at"):
                query["updated_at"] = {"$lt": cursor_doc["updated_at"]}

        cursor = self._sessions_col.find(query).sort("updated_at", -1).limit(limit + 1)
        sessions = []
        async for doc in cursor:
            sessions.append({
                "session_id": doc["_id"],
                "user_id": doc.get("user_id", ""),
                "workflow_id": doc.get("workflow_id"),
                "channel": doc.get("channel", "api"),
                "summary": doc.get("summary"),
                "message_count": doc.get("message_count", 0),
                "turn_count": doc.get("turn_count", 0),
                "last_message_preview": doc.get("last_message_preview"),
                "created_at": doc.get("created_at", ""),
                "updated_at": doc.get("updated_at", ""),
            })

        has_more = len(sessions) > limit
        if has_more:
            sessions = sessions[:limit]

        return {"sessions": sessions, "has_more": has_more}

    async def get_messages_page(
        self,
        session_id: str,
        turns: int = 10,
        before_turn: int | None = None,
    ) -> dict[str, Any]:
        """Get paginated messages for frontend display (user + agent only).

        Args:
            session_id: The session to query.
            turns: Number of turns to return.
            before_turn: Cursor — return turns before this turn number.

        Returns:
            { "messages": [...], "has_more": bool }
        """
        query: dict[str, Any] = {
            "session_id": session_id,
            "role": {"$in": ["user", "agent"]},
        }
        if before_turn is not None:
            query["turn"] = {"$lt": before_turn}

        # We need to find the distinct turn numbers first, then fetch messages for those turns.
        # Use aggregation to get distinct turns, then fetch messages.
        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$turn"}},
            {"$sort": {"_id": -1}},
            {"$limit": turns + 1},  # +1 to check has_more
        ]
        turn_docs = await self._messages_col.aggregate(pipeline).to_list(length=turns + 1)
        turn_numbers = [d["_id"] for d in turn_docs]

        has_more = len(turn_numbers) > turns
        if has_more:
            turn_numbers = turn_numbers[:turns]

        if not turn_numbers:
            return {"messages": [], "has_more": False}

        # Fetch all messages for these turns
        messages_cursor = self._messages_col.find(
            {
                "session_id": session_id,
                "role": {"$in": ["user", "agent"]},
                "turn": {"$in": turn_numbers},
            },
        ).sort([("turn", -1), ("seq", 1)])

        messages = []
        async for doc in messages_cursor:
            doc.pop("_id", None)
            doc.pop("session_id", None)
            doc.pop("seq", None)
            # Remove LLM-internal fields from display messages
            doc.pop("tool_calls", None)
            doc.pop("tool_call_id", None)
            doc.pop("name", None)
            messages.append(doc)

        return {"messages": messages, "has_more": has_more}

    async def save_summary(self, session_id: str, summary: str) -> None:
        """Update only the summary field (used by background generation)."""
        try:
            await self._sessions_col.update_one(
                {"_id": session_id}, {"$set": {"summary": summary}},
            )
            # Update Redis meta cache if it exists
            meta_key = f"{REDIS_META_PREFIX}{session_id}"
            raw = await self._redis.get(meta_key)
            if raw:
                doc = json.loads(raw)
                doc["summary"] = summary
                await self._redis.set(
                    meta_key,
                    json.dumps(doc, ensure_ascii=False),
                    ex=REDIS_TTL,
                )
        except Exception:
            logger.warning("Failed to save summary for session {}", session_id)

    # -- Redis helpers ---------------------------------------------------------

    async def _write_redis(self, session: Session) -> None:
        """Write session metadata and LLM context to Redis."""
        # Preserve existing summary if current session doesn't have one yet
        # (avoids overwriting a summary written by the background generation task)
        summary = session.summary
        if summary is None:
            try:
                meta_key_existing = f"{REDIS_META_PREFIX}{session.session_id}"
                raw = await self._redis.get(meta_key_existing)
                if raw:
                    existing = json.loads(raw)
                    if existing.get("summary"):
                        summary = existing["summary"]
                        session.summary = summary  # sync back to in-memory session
            except Exception:
                pass

        # Meta cache (lightweight)
        meta_key = f"{REDIS_META_PREFIX}{session.session_id}"
        meta_doc = {
            "_id": session.session_id,
            "user_id": session.user_id,
            "workflow_id": session.workflow_id,
            "channel": session.channel,
            "summary": summary,
            "message_count": session.message_count,
            "turn_count": session.turn_count,
            "last_message_preview": session.last_message_preview,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
        }

        # Context cache (full messages for LLM)
        ctx_key = f"{REDIS_CTX_PREFIX}{session.session_id}"
        ctx_doc = {
            "_id": session.session_id,
            "user_id": session.user_id,
            "workflow_id": session.workflow_id,
            "channel": session.channel,
            "messages": session.messages,
            "summary": summary,
            "message_count": session.message_count,
            "turn_count": session.turn_count,
            "last_message_preview": session.last_message_preview,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata,
            "_persisted_count": len(session.messages),
        }

        try:
            await self._redis.set(
                meta_key,
                json.dumps(meta_doc, ensure_ascii=False),
                ex=REDIS_TTL,
            )
            await self._redis.set(
                ctx_key,
                json.dumps(ctx_doc, ensure_ascii=False),
                ex=REDIS_TTL,
            )
        except Exception:
            logger.warning("Failed to write session {} to Redis", session.session_id)

    async def _load_from_redis(self, session_id: str) -> Session | None:
        """Try to load session from Redis ctx cache."""
        ctx_key = f"{REDIS_CTX_PREFIX}{session_id}"
        try:
            raw = await self._redis.get(ctx_key)
            if raw:
                doc = json.loads(raw)
                return self._doc_to_session(doc)
        except Exception:
            logger.warning("Failed to read session {} from Redis", session_id)
        return None

    # -- MongoDB helpers -------------------------------------------------------

    async def _load_from_mongo(self, session_id: str) -> Session | None:
        """Try to load session from MongoDB (new agent database)."""
        try:
            meta_doc = await self._sessions_col.find_one({"_id": session_id})
            if not meta_doc:
                return None

            # Load all messages sorted by seq (for LLM context)
            messages: list[dict[str, Any]] = []
            cursor = self._messages_col.find(
                {"session_id": session_id},
            ).sort("seq", 1)
            async for msg_doc in cursor:
                # Strip MongoDB-internal fields
                msg_doc.pop("_id", None)
                msg_doc.pop("session_id", None)
                msg_doc.pop("seq", None)
                # Read-side normalize: validate + strip unknown fields
                validated = StoredMessageDoc.model_validate(msg_doc)
                messages.append(validated.model_dump(exclude_none=True))

            created = meta_doc.get("created_at")
            updated = meta_doc.get("updated_at")
            if isinstance(created, str):
                created = datetime.fromisoformat(created)
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated)

            session = Session(
                session_id=session_id,
                user_id=meta_doc.get("user_id", ""),
                workflow_id=meta_doc.get("workflow_id"),
                channel=meta_doc.get("channel", "api"),
                messages=messages,
                created_at=created or datetime.now(),
                updated_at=updated or datetime.now(),
                summary=meta_doc.get("summary"),
                message_count=meta_doc.get("message_count", 0),
                turn_count=meta_doc.get("turn_count", 0),
                last_message_preview=meta_doc.get("last_message_preview"),
                metadata=meta_doc.get("metadata", {}),
                _persisted_count=len(messages),
            )
            return session
        except Exception:
            logger.warning("Failed to load session {} from MongoDB", session_id)
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
        messages_raw = doc.get("messages", [])
        # Read-side normalize: validate each message from Redis cache
        messages = [
            StoredMessageDoc.model_validate(m).model_dump(exclude_none=True)
            for m in messages_raw
        ]
        return Session(
            session_id=doc["_id"],
            user_id=doc.get("user_id", ""),
            workflow_id=doc.get("workflow_id"),
            channel=doc.get("channel", "api"),
            messages=messages,
            created_at=created or datetime.now(),
            updated_at=updated or datetime.now(),
            summary=doc.get("summary"),
            message_count=doc.get("message_count", 0),
            turn_count=doc.get("turn_count", 0),
            last_message_preview=doc.get("last_message_preview"),
            metadata=doc.get("metadata", {}),
            _persisted_count=doc.get("_persisted_count", len(messages)),
        )
