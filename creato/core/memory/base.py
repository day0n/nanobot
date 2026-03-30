"""Memory provider interface — defines the contract for memory backends.

Two dimensions:
- Long-term memory: keyed by user_id, persists across sessions (preferences, background, etc.)
- Session memory: keyed by session_id, scoped to a single conversation (future: summarization)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MemoryEntry:
    """A single memory item."""

    content: str
    source: str  # "conversation", "tool_result", "user_correction", etc.
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0


class MemoryProvider(ABC):
    """Abstract interface for long-term memory backends.

    Long-term memory is keyed by user_id — it persists across sessions
    and captures user preferences, background, and behavioral patterns.
    """

    @abstractmethod
    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Retrieve relevant long-term memories for a user given a query."""

    @abstractmethod
    async def store(self, user_id: str, messages: list[dict[str, Any]]) -> None:
        """Extract and store memories from a conversation turn."""


class NoOpMemory(MemoryProvider):
    """Default no-op memory provider. Does nothing, returns nothing."""

    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> list[MemoryEntry]:
        return []

    async def store(self, user_id: str, messages: list[dict[str, Any]]) -> None:
        pass
