"""SSE event definitions for the agent chat protocol.

All events emitted during an agent chat session are defined here.
This module serves as the contract between backend and frontend.

Event naming follows dot-notation (e.g. ``tool.started``), inspired by
the OpenAI Responses API.  Every event is wrapped in an :class:`AgentEvent`
envelope that serialises to ``{"event": "<name>", "data": {…}}``.

Low-frequency event payloads are validated via Pydantic models from
``creato.schemas.events``.  High-frequency ``message.delta`` uses
TypedDict (zero overhead).  Workflow events pass through raw dicts from
the external Consumer protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from creato.schemas.events import (
    AgentCompletedData,
    AgentFailedData,
    AgentResponse,
    AgentStartedData,
    StepData,
    SubagentCompletedData,
    SubagentStartedData,
    SubagentToolCompletedData,
    ToolCompletedData,
    ToolEventData,
    ToolFailedData,
    ToolStartedData,
)
from creato.schemas.messages import MessageDeltaData


# ── event envelope ──────────────────────────────────────────────────

@dataclass(slots=True)
class AgentEvent:
    """SSE event envelope."""

    event: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.event in (_AGENT_COMPLETED, _AGENT_FAILED)

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event, "data": self.data}


# ── event name constants ────────────────────────────────────────────

_AGENT_STARTED = "agent.started"
_AGENT_COMPLETED = "agent.completed"
_AGENT_FAILED = "agent.failed"
_AGENT_HEARTBEAT = "agent.heartbeat"

_MESSAGE_DELTA = "message.delta"

_TOOL_STARTED = "tool.started"
_TOOL_COMPLETED = "tool.completed"
_TOOL_FAILED = "tool.failed"
_TOOL_EVENT = "tool.event"

_STEP_STARTED = "step.started"
_STEP_COMPLETED = "step.completed"

_WORKFLOW_STARTED = "workflow.started"
_WORKFLOW_NODE_STATUS = "workflow.node_status"
_WORKFLOW_MODEL_READY = "workflow.model_ready"
_WORKFLOW_MODEL_STATUS = "workflow.model_status"
_WORKFLOW_PAUSED = "workflow.paused"
_WORKFLOW_COMPLETED = "workflow.completed"
_WORKFLOW_FAILED = "workflow.failed"
_WORKFLOW_KILLED = "workflow.killed"

_SUBAGENT_STARTED = "subagent.started"
_SUBAGENT_COMPLETED = "subagent.completed"
_SUBAGENT_MESSAGE_DELTA = "subagent.message.delta"
_SUBAGENT_TOOL_STARTED = "subagent.tool.started"
_SUBAGENT_TOOL_COMPLETED = "subagent.tool.completed"
_SUBAGENT_TOOL_EVENT = "subagent.tool.event"
_SUBAGENT_STEP_STARTED = "subagent.step.started"
_SUBAGENT_STEP_COMPLETED = "subagent.step.completed"


# ── constructor functions ───────────────────────────────────────────

def agent_started(session_id: str, run_id: str | None = None) -> AgentEvent:
    payload = AgentStartedData(session_id=session_id, run_id=run_id or uuid4().hex[:12])
    return AgentEvent(event=_AGENT_STARTED, data=payload.model_dump())


def agent_completed(content: str, usage: dict[str, int] | None = None) -> AgentEvent:
    payload = AgentCompletedData(content=content, usage=usage)
    return AgentEvent(event=_AGENT_COMPLETED, data=payload.model_dump(exclude_none=True))


def agent_failed(error: str) -> AgentEvent:
    payload = AgentFailedData(error=error)
    return AgentEvent(event=_AGENT_FAILED, data=payload.model_dump())


def agent_heartbeat() -> AgentEvent:
    return AgentEvent(event=_AGENT_HEARTBEAT, data={})


def message_delta(content: str) -> AgentEvent:
    # High-frequency — TypedDict, no Pydantic overhead
    return AgentEvent(event=_MESSAGE_DELTA, data=MessageDeltaData(content=content))


def tool_started(
    tool_name: str,
    tool_call_id: str,
    arguments: dict[str, Any] | None = None,
) -> AgentEvent:
    payload = ToolStartedData(tool_name=tool_name, tool_call_id=tool_call_id, arguments=arguments or {})
    return AgentEvent(event=_TOOL_STARTED, data=payload.model_dump())


def tool_completed(tool_call_id: str, duration_ms: int) -> AgentEvent:
    payload = ToolCompletedData(tool_call_id=tool_call_id, duration_ms=duration_ms)
    return AgentEvent(event=_TOOL_COMPLETED, data=payload.model_dump())


def tool_failed(tool_call_id: str, error: str) -> AgentEvent:
    payload = ToolFailedData(tool_call_id=tool_call_id, error=error)
    return AgentEvent(event=_TOOL_FAILED, data=payload.model_dump())


def tool_event(event_name: str, data: dict[str, Any] | None = None) -> AgentEvent:
    payload = ToolEventData(event_name=event_name, extra=data or {})
    return AgentEvent(event=_TOOL_EVENT, data=payload.to_flat_dict())


def step_started(step: int) -> AgentEvent:
    payload = StepData(step=step)
    return AgentEvent(event=_STEP_STARTED, data=payload.model_dump())


def step_completed(step: int) -> AgentEvent:
    payload = StepData(step=step)
    return AgentEvent(event=_STEP_COMPLETED, data=payload.model_dump())


# ── workflow event constructors (data is Consumer's raw event, passed through) ──

def workflow_started(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_STARTED, data=data)

def workflow_node_status(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_NODE_STATUS, data=data)

def workflow_model_ready(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_MODEL_READY, data=data)

def workflow_model_status(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_MODEL_STATUS, data=data)

def workflow_paused(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_PAUSED, data=data)

def workflow_completed(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_COMPLETED, data=data)

def workflow_failed(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_FAILED, data=data)

def workflow_killed(data: dict[str, Any]) -> AgentEvent:
    return AgentEvent(event=_WORKFLOW_KILLED, data=data)


# Consumer event_type → Agent SSE constructor
# NOTE: start_flow is NOT mapped here — loop.py emits workflow.started
# when it receives the WorkflowExecution object, before consuming the stream.
# Mapping it here would cause a duplicate workflow.started event.
WORKFLOW_EVENT_MAP: dict[str, Any] = {
    "node_status": workflow_node_status,
    "llm_model_ready": workflow_model_ready,
    "llm_model_status": workflow_model_status,
    "finish_flow": workflow_completed,
    "flow_killed": workflow_killed,
    "node_time_out": workflow_failed,
}


# ── subagent event constructors ────────────────────────────────────

def subagent_started(agent_type: str, task: str) -> AgentEvent:
    payload = SubagentStartedData(agent_type=agent_type, task=task[:200])
    return AgentEvent(event=_SUBAGENT_STARTED, data=payload.model_dump())


def subagent_completed(agent_type: str, tools_used: list[str], result_preview: str) -> AgentEvent:
    payload = SubagentCompletedData(
        agent_type=agent_type, tools_used=tools_used, result_preview=result_preview[:200],
    )
    return AgentEvent(event=_SUBAGENT_COMPLETED, data=payload.model_dump())


def subagent_message_delta(content: str) -> AgentEvent:
    """Subagent text streaming — TypedDict (high-frequency)."""
    return AgentEvent(event=_SUBAGENT_MESSAGE_DELTA, data=MessageDeltaData(content=content))


def subagent_tool_started(tool_name: str, tool_call_id: str, arguments: dict[str, Any] | None = None) -> AgentEvent:
    payload = ToolStartedData(tool_name=tool_name, tool_call_id=tool_call_id, arguments=arguments or {})
    return AgentEvent(event=_SUBAGENT_TOOL_STARTED, data=payload.model_dump())


def subagent_tool_completed(
    tool_name: str, tool_call_id: str, duration_ms: int, error: str | None = None,
) -> AgentEvent:
    payload = SubagentToolCompletedData(
        tool_name=tool_name, tool_call_id=tool_call_id,
        duration_ms=duration_ms, error=error,
    )
    return AgentEvent(event=_SUBAGENT_TOOL_COMPLETED, data=payload.model_dump(exclude_none=True))


def subagent_tool_event(event_name: str, data: dict[str, Any] | None = None) -> AgentEvent:
    payload = ToolEventData(event_name=event_name, extra=data or {})
    return AgentEvent(event=_SUBAGENT_TOOL_EVENT, data=payload.to_flat_dict())


def subagent_step_started(step: int) -> AgentEvent:
    payload = StepData(step=step)
    return AgentEvent(event=_SUBAGENT_STEP_STARTED, data=payload.model_dump())


def subagent_step_completed(step: int) -> AgentEvent:
    payload = StepData(step=step)
    return AgentEvent(event=_SUBAGENT_STEP_COMPLETED, data=payload.model_dump())


# ── response accumulator ───────────────────────────────────────────

class ResponseAccumulator:
    """Accumulate streaming AgentEvents into an AgentResponse.

    Usage::

        acc = ResponseAccumulator()
        for event in stream:
            acc.feed(event)
        response = acc.build()
    """

    def __init__(self) -> None:
        self._id: str = ""
        self._session_id: str = ""
        self._status: str = "completed"
        self._output: list[dict[str, Any]] = []
        self._usage: dict[str, int] | None = None
        self._error: str | None = None
        # accumulation buffers
        self._current_text: str = ""
        self._current_tool: dict[str, Any] | None = None

    def _flush_text(self) -> None:
        if self._current_text:
            self._output.append({"type": "message", "content": self._current_text})
            self._current_text = ""

    def _flush_tool(self) -> None:
        if self._current_tool:
            self._output.append(self._current_tool)
            self._current_tool = None

    def feed(self, event: AgentEvent) -> None:
        e, d = event.event, event.data

        if e == _AGENT_STARTED:
            self._id = d.get("run_id", "")
            self._session_id = d.get("session_id", "")

        elif e == _MESSAGE_DELTA:
            # If we were building a tool, flush it first
            self._flush_tool()
            self._current_text += d.get("content", "")

        elif e == _TOOL_STARTED:
            # Flush any pending text
            self._flush_text()
            self._current_tool = {
                "type": "tool_use",
                "tool_name": d.get("tool_name", ""),
                "tool_call_id": d.get("tool_call_id", ""),
                "arguments": d.get("arguments", {}),
                "events": [],
            }

        elif e == _TOOL_COMPLETED:
            if self._current_tool:
                self._current_tool["duration_ms"] = d.get("duration_ms", 0)
            self._flush_tool()

        elif e == _TOOL_FAILED:
            if self._current_tool:
                self._current_tool["error"] = d.get("error", "")
            self._flush_tool()

        elif e == _TOOL_EVENT:
            if self._current_tool:
                self._current_tool["events"].append(d)

        elif e == _AGENT_COMPLETED:
            self._flush_text()
            self._flush_tool()
            # If the final content differs from accumulated text, append it
            final = d.get("content", "")
            if final and (not self._output or self._output[-1].get("content") != final):
                self._output.append({"type": "message", "content": final})
            self._usage = d.get("usage")
            self._status = "completed"

        elif e == _AGENT_FAILED:
            self._flush_text()
            self._flush_tool()
            self._error = d.get("error", "")
            self._status = "failed"

    def build(self) -> AgentResponse:
        self._flush_text()
        self._flush_tool()
        return AgentResponse(
            id=self._id,
            session_id=self._session_id,
            status=self._status,
            output=self._output,
            usage=self._usage,
            error=self._error,
        )
