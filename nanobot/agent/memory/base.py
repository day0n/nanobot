"""Memory provider interface — defines the contract for memory backends.

Not yet integrated into the agent loop. This module establishes the interface
so that future memory implementations (vector store, knowledge graph, etc.)
can be plugged in without changing the prompt builder or loop.
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
    """Abstract interface for memory backends.

    Future implementations:
    - ConversationSummaryMemory: summarize old turns to save context window
    - VectorMemory: embed and retrieve relevant past interactions
    - WorkflowMemory: remember user's workflow patterns and preferences
    """

    @abstractmethod
    async def store(self, session_id: str, entry: MemoryEntry) -> None:
        """Store a memory entry."""

    @abstractmethod
    async def retrieve(
        self, session_id: str, query: str, limit: int = 5,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories for a query."""

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Clear all memories for a session."""


class NoOpMemory(MemoryProvider):
    """Default no-op memory provider. Does nothing, returns nothing."""

    async def store(self, session_id: str, entry: MemoryEntry) -> None:
        pass

    async def retrieve(
        self, session_id: str, query: str, limit: int = 5,
    ) -> list[MemoryEntry]:
        return []

    async def clear(self, session_id: str) -> None:
        pass
