"""Direct OpenAI provider — uses the openai SDK with streaming support."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import json_repair
from loguru import logger
from openai import AsyncOpenAI

from creato.providers.base import LLMProvider, LLMResponse, LLMStreamChunk, ToolCallRequest

# Models that use max_completion_tokens instead of max_tokens,
# AND don't support the temperature parameter.
_REASONING_PREFIXES = ("o1", "o3", "o4")

# Models that use max_completion_tokens but DO support temperature.
# GPT-5 and GPT-4.1 use the newer API surface (max_completion_tokens)
# but still accept temperature normally.
_MAX_COMPLETION_TOKEN_PREFIXES = ("gpt-5", "gpt-4.1")


def _is_reasoning_model(model: str) -> bool:
    """True for o-series reasoning models (no temperature, no max_tokens)."""
    name = model.lower().split("/")[-1]
    return any(name.startswith(p) for p in _REASONING_PREFIXES)


def _uses_max_completion_tokens(model: str) -> bool:
    """True for models that require max_completion_tokens instead of max_tokens."""
    name = model.lower().split("/")[-1]
    return (
        any(name.startswith(p) for p in _REASONING_PREFIXES)
        or any(name.startswith(p) for p in _MAX_COMPLETION_TOKEN_PREFIXES)
    )


class OpenAIProvider(LLMProvider):
    """Direct OpenAI provider using the official openai SDK.

    Features over the LiteLLM path:
    - Native streaming via chat_stream()
    - reasoning_content support for o-series models
    - max_completion_tokens for reasoning models
    - Automatic temperature handling (reasoning models don't support it)
    """

    def __init__(
        self,
        api_key: str = "",
        api_base: str | None = None,
        default_model: str = "gpt-4.1",
        extra_headers: dict[str, str] | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if api_base:
            client_kwargs["base_url"] = api_base
        if extra_headers:
            client_kwargs["default_headers"] = {
                "x-session-affinity": uuid.uuid4().hex,
                **extra_headers,
            }

        self._client = AsyncOpenAI(**client_kwargs)

    def get_default_model(self) -> str:
        return self.default_model

    @staticmethod
    def _strip_provider_prefix(model: str) -> str:
        """Strip 'openai/' prefix — the SDK expects bare model names like 'o3', not 'openai/o3'."""
        if model.startswith("openai/"):
            return model[len("openai/"):]
        return model

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        max_tokens: int,
        temperature: float,
        reasoning_effort: str | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build kwargs for the OpenAI API call."""
        model_name = self._strip_provider_prefix(model or self.default_model)
        is_reasoning = _is_reasoning_model(model_name) or bool(reasoning_effort)
        needs_max_completion_tokens = _uses_max_completion_tokens(model_name) or is_reasoning

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": self._sanitize_empty_content(messages),
        }

        # Newer models (gpt-5, gpt-4.1, o-series) use max_completion_tokens;
        # legacy models (gpt-4o, gpt-4) use max_tokens.
        if needs_max_completion_tokens:
            kwargs["max_completion_tokens"] = max(1, max_tokens)
        else:
            kwargs["max_tokens"] = max(1, max_tokens)

        # Only reasoning models (o-series) and explicit reasoning_effort skip temperature
        if not is_reasoning:
            kwargs["temperature"] = temperature

        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        return kwargs

    @staticmethod
    def _parse_tool_calls(raw_tool_calls: list[Any]) -> list[ToolCallRequest]:
        """Parse tool calls from OpenAI response."""
        result = []
        for tc in raw_tool_calls:
            args = tc.function.arguments
            if isinstance(args, str):
                args = json_repair.loads(args)
            result.append(ToolCallRequest(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))
        return result

    @staticmethod
    def _extract_usage(usage: Any) -> dict[str, int]:
        if not usage:
            return {}
        return {
            "prompt_tokens": usage.prompt_tokens or 0,
            "completion_tokens": usage.completion_tokens or 0,
            "total_tokens": usage.total_tokens or 0,
        }

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        kwargs = self._build_kwargs(
            messages, tools, model, max_tokens, temperature,
            reasoning_effort, tool_choice,
        )

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(content=f"Error: {body.strip()[:500]}", finish_reason="error")
            return LLMResponse(content=f"Error calling OpenAI: {e}", finish_reason="error")

        if not response.choices:
            return LLMResponse(content="Error: empty choices from OpenAI", finish_reason="error")

        choice = response.choices[0]
        msg = choice.message

        tool_calls = self._parse_tool_calls(msg.tool_calls or [])
        reasoning_content = getattr(msg, "reasoning_content", None) or None

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=self._extract_usage(response.usage),
            reasoning_content=reasoning_content,
        )

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream OpenAI responses with native SSE streaming."""
        kwargs = self._build_kwargs(
            messages, tools, model, max_tokens, temperature,
            reasoning_effort, tool_choice,
        )
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

        model_name = model or self.default_model
        logger.debug("OpenAI stream request model={}", model_name)

        # Accumulate tool calls across chunks
        pending_tool_calls: dict[int, dict[str, Any]] = {}  # index → {id, name, arguments_str}

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                # Final chunk with usage only
                if chunk.usage:
                    yield LLMStreamChunk(usage=self._extract_usage(chunk.usage))
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # Text content
            text_delta = delta.content or ""

            # Tool call deltas — accumulate across chunks
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": (tc_delta.function.name if tc_delta.function else "") or "",
                            "arguments": "",
                        }
                    entry = pending_tool_calls[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

            if text_delta:
                yield LLMStreamChunk(text_delta=text_delta)

            if finish_reason:
                # Finalize tool calls
                completed = None
                if pending_tool_calls:
                    completed = []
                    for _idx in sorted(pending_tool_calls):
                        entry = pending_tool_calls[_idx]
                        args = entry["arguments"]
                        if isinstance(args, str):
                            args = json_repair.loads(args) if args else {}
                        completed.append(ToolCallRequest(
                            id=entry["id"],
                            name=entry["name"],
                            arguments=args,
                        ))

                yield LLMStreamChunk(
                    completed_tool_calls=completed,
                    finish_reason=finish_reason,
                    usage=self._extract_usage(chunk.usage) if chunk.usage else None,
                )
