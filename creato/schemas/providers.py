"""LLM provider response contracts — Pydantic (runtime validation).

These types cross the provider → executor boundary. Different developers
may implement different providers; the output contract must be strict.

LLMStreamChunk and GenerationSettings stay as dataclass in providers/base.py
(hot path / internal config).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolCallRequest(BaseModel):
    """A tool call request from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]
    provider_specific_fields: dict[str, Any] | None = None
    function_provider_specific_fields: dict[str, Any] | None = None

    @field_validator("arguments", mode="before")
    @classmethod
    def _coerce_arguments(cls, v: Any) -> dict[str, Any]:
        """LLMs sometimes return arguments as a JSON string or list. Coerce to dict."""
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {"_raw": parsed}
            except (json.JSONDecodeError, TypeError):
                return {"_raw": v}
        if isinstance(v, list):
            return {"_items": v}
        return {"_raw": v}

    def to_openai_tool_call(self) -> dict[str, Any]:
        """Serialize to an OpenAI-style tool_call payload."""
        tool_call: dict[str, Any] = {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments, ensure_ascii=False),
            },
        }
        if self.provider_specific_fields:
            tool_call["provider_specific_fields"] = self.provider_specific_fields
        if self.function_provider_specific_fields:
            tool_call["function"]["provider_specific_fields"] = (
                self.function_provider_specific_fields
            )
        return tool_call


class LLMResponse(BaseModel):
    """Response from an LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = Field(default_factory=dict)
    reasoning_content: str | None = None  # Kimi, DeepSeek-R1 etc.
    thinking_blocks: list[dict[str, Any]] | None = None  # Anthropic extended thinking

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0
