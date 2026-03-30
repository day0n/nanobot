"""SSE event payload contracts — Pydantic (runtime validation).

These types define the ``data`` field of AgentEvent for each event type.
The AgentEvent envelope itself stays as a dataclass.

MessageDeltaData is in messages.py as TypedDict (high-frequency streaming).
Workflow event data stays dict[str, Any] (external Consumer protocol).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Agent lifecycle ───────────────────────────────────────────────

class AgentStartedData(BaseModel):
    session_id: str
    run_id: str


class AgentCompletedData(BaseModel):
    content: str
    usage: dict[str, int] | None = None


class AgentFailedData(BaseModel):
    error: str


# ── Tool ──────────────────────────────────────────────────────────

class ToolStartedData(BaseModel):
    tool_name: str
    tool_call_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCompletedData(BaseModel):
    tool_call_id: str
    duration_ms: int


class ToolFailedData(BaseModel):
    tool_call_id: str
    error: str


class SubagentToolCompletedData(BaseModel):
    """Subagent tool completion — carries tool_name, duration_ms, and optional error."""
    tool_name: str
    tool_call_id: str
    duration_ms: int
    error: str | None = None


class ToolEventData(BaseModel):
    """Payload for tool.event / subagent.tool.event — sub-events emitted during tool execution.

    Serialized flat: ``{"event_name": "...", "key1": ..., "key2": ...}``
    to preserve backward compatibility with the old protocol.
    """
    event_name: str
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_flat_dict(self) -> dict[str, Any]:
        """Serialize to the flat format the frontend expects."""
        return {"event_name": self.event_name, **self.extra}


# ── Step ──────────────────────────────────────────────────────────

class StepData(BaseModel):
    step: int


# ── Subagent ──────────────────────────────────────────────────────

class SubagentStartedData(BaseModel):
    agent_type: str
    task: str


class SubagentCompletedData(BaseModel):
    agent_type: str
    tools_used: list[str]
    result_preview: str


# ── AgentResponse (non-streaming) ─────────────────────────────────

class AgentResponse(BaseModel):
    """Non-streaming response, also reconstructable from streaming events."""

    id: str
    session_id: str
    status: str  # "completed" | "failed"
    output: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] | None = None
    model: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Backward-compatible serialization (matches old dataclass API)."""
        d: dict[str, Any] = {
            "id": self.id,
            "session_id": self.session_id,
            "status": self.status,
            "output": self.output,
        }
        if self.usage:
            d["usage"] = self.usage
        if self.model:
            d["model"] = self.model
        if self.error:
            d["error"] = self.error
        return d
