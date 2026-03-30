"""Tool contracts — Pydantic (runtime validation).

These types cross the tool → executor boundary. Different developers
write different tools; the return contract must be strict.

WorkflowExecution stays as dataclass in tools/base.py (contains AsyncGenerator).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolEventPayload(BaseModel):
    """Structure for each event in ToolResult.events."""

    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Rich return type for tools that need to emit side-channel events.

    Tools that only return text can keep returning ``str``. Tools that
    also need to notify the frontend (e.g. ``workflow_update``) return a
    ``ToolResult`` instead — the executor dispatches ``events`` via SSE
    while feeding ``content`` back to the LLM.
    """

    content: str
    events: list[ToolEventPayload] = Field(default_factory=list)


class SubagentRequest(BaseModel):
    """Main agent → Subagent task request."""

    task: str
    agent_type: str


class SubagentResult(BaseModel):
    """Subagent → Main agent execution result."""

    agent_type: str
    content: str
    tools_used: list[str] = Field(default_factory=list)
    iterations: int = 0

    def to_tool_response(self) -> str:
        """Serialize to a tool result string for the LLM."""
        tool_summary = (
            ", ".join(sorted(set(self.tools_used))) if self.tools_used else "none"
        )
        return (
            f"[subagent:{self.agent_type} | {self.iterations} iterations "
            f"| tools: {tool_summary}]\n\n{self.content}"
        )
