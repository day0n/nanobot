"""Session storage contracts — Pydantic (runtime validation).

These types define the MongoDB document schemas for session persistence.
Used for both write-side validation and read-side normalization.

``extra="allow"`` ensures backward compatibility with old documents
that may contain unknown fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StoredMessageDoc(BaseModel):
    """MongoDB ``agent_messages`` document schema."""

    model_config = {"extra": "allow"}

    role: Literal["user", "agent", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    turn: int | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_hints: list[str] | None = None
    thinking_blocks: list[dict[str, Any]] | None = None
    reasoning_content: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str | None = None


class SessionMetaDoc(BaseModel):
    """MongoDB ``agent_sessions`` document schema."""

    model_config = {"extra": "allow"}

    user_id: str = ""
    workflow_id: str | None = None
    channel: str = "api"
    summary: str | None = None
    message_count: int = 0
    turn_count: int = 0
    last_message_preview: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolTraceDoc(BaseModel):
    """MongoDB ``agent_tool_traces`` document schema."""

    session_id: str
    turn: int
    tool_call_id: str
    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    output_size_bytes: int = 0
    status: Literal["success", "error"] = "success"
    error: str | None = None
    duration_ms: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
