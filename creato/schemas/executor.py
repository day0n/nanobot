"""Executor output contract — Pydantic (runtime validation).

ExecutorResult crosses the executor → loop boundary.
ExecutorHooks stays as dataclass in executor.py (callback container).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from creato.schemas.messages import MessageList


class ExecutorResult(BaseModel):
    """Structured result from AgentExecutor.run()."""

    content: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    messages: MessageList = Field(default_factory=list)
    tool_timings: dict[str, dict[str, Any]] = Field(default_factory=dict)
    iterations: int = 0
