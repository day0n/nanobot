"""LLM message types — TypedDict (zero runtime cost).

These types define the dict structures that flow through the executor,
prompt builder, providers, and session. They are TypedDict (not Pydantic)
because LLM APIs require plain dicts and these are on the hot path.
"""

from __future__ import annotations

from typing import Any, Literal, Union

from typing_extensions import NotRequired, TypedDict


# ── Tool call sub-structures ──────────────────────────────────────

class ToolCallFunction(TypedDict):
    name: str
    arguments: str  # JSON string (OpenAI format)
    provider_specific_fields: NotRequired[dict[str, Any]]


class ToolCallDict(TypedDict):
    id: str
    type: Literal["function"]
    function: ToolCallFunction
    provider_specific_fields: NotRequired[dict[str, Any]]


# ── Message types ─────────────────────────────────────────────────

class SystemMessage(TypedDict):
    role: Literal["system"]
    content: str


class UserMessage(TypedDict):
    role: Literal["user"]
    content: str | list[dict[str, Any]]  # multimodal: list of content blocks


class AssistantMessage(TypedDict):
    role: Literal["assistant"]
    content: str | None
    tool_calls: NotRequired[list[ToolCallDict]]
    reasoning_content: NotRequired[str | None]
    thinking_blocks: NotRequired[list[dict[str, Any]] | None]


class ToolMessage(TypedDict):
    role: Literal["tool"]
    tool_call_id: str
    name: str
    content: str


class AgentDisplayMessage(TypedDict):
    """Display-only role used in session storage.

    Mapped back to 'assistant' for LLM API calls in Session.get_history().
    """

    role: Literal["agent"]
    content: str
    turn: NotRequired[int]
    tool_hints: NotRequired[list[str]]
    created_at: NotRequired[str]


# ── Union types ───────────────────────────────────────────────────

ChatMessage = Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]
StoredMessage = Union[ChatMessage, AgentDisplayMessage]
MessageList = list[ChatMessage]

# ── High-frequency streaming payload (TypedDict, not Pydantic) ───

class MessageDeltaData(TypedDict):
    content: str
