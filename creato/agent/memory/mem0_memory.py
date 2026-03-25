"""Mem0-based long-term memory provider.

Uses mem0 open-source with MongoDB Atlas as vector store backend.
Memories are stored per user_id in the configured agent database.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from creato.agent.memory.base import MemoryEntry, MemoryProvider


class Mem0Memory(MemoryProvider):
    """Long-term memory backed by mem0 + MongoDB Atlas vector search."""

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "opencreator_agent",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        llm_model: str = "gpt-4o-mini",
        embedder_model: str = "text-embedding-3-small",
        openai_api_key: str | None = None,
    ):
        from mem0 import Memory

        config: dict[str, Any] = {
            "vector_store": {
                "provider": "mongodb",
                "config": {
                    "mongo_uri": mongo_uri,
                    "db_name": db_name,
                    "collection_name": collection_name,
                    "embedding_model_dims": embedding_model_dims,
                },
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": llm_model,
                    "temperature": 0.1,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": embedder_model,
                },
            },
        }
        if openai_api_key:
            config["llm"]["config"]["api_key"] = openai_api_key
            config["embedder"]["config"]["api_key"] = openai_api_key

        self._memory = Memory.from_config(config)
        logger.info(
            "Mem0Memory initialized: db={} collection={}",
            db_name, collection_name,
        )

    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Retrieve relevant long-term memories for a user."""
        if not user_id:
            return []
        try:
            results = self._memory.search(query=query, user_id=user_id, limit=limit)
            entries = []
            for r in results:
                memory_text = r.get("memory", "") if isinstance(r, dict) else str(r)
                score = r.get("score", 0.0) if isinstance(r, dict) else 0.0
                entries.append(MemoryEntry(
                    content=memory_text,
                    source="long_term",
                    relevance_score=float(score),
                ))
            return entries
        except Exception as e:
            logger.warning("Mem0 retrieve failed for user {}: {}", user_id, e)
            return []

    async def store(self, user_id: str, messages: list[dict[str, Any]]) -> None:
        """Extract and store memories from conversation messages."""
        if not user_id or not messages:
            return
        try:
            # Filter to user + agent messages only (skip tool results and intermediate assistant)
            conversation = [
                {
                    "role": "user" if m.get("role") == "user" else "assistant",
                    "content": m["content"],
                }
                for m in messages
                if m.get("role") in ("user", "agent")
                and isinstance(m.get("content"), str)
                and m["content"].strip()
            ]
            if not conversation:
                return
            self._memory.add(conversation, user_id=user_id)
        except Exception as e:
            logger.warning("Mem0 store failed for user {}: {}", user_id, e)
