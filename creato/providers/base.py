"""Base LLM provider interface."""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]
    provider_specific_fields: dict[str, Any] | None = None
    function_provider_specific_fields: dict[str, Any] | None = None

    def to_openai_tool_call(self) -> dict[str, Any]:
        """Serialize to an OpenAI-style tool_call payload."""
        tool_call = {
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
            tool_call["function"]["provider_specific_fields"] = self.function_provider_specific_fields
        return tool_call


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None  # Kimi, DeepSeek-R1 etc.
    thinking_blocks: list[dict] | None = None  # Anthropic extended thinking
    
    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


@dataclass
class LLMStreamChunk:
    """A single chunk from a streaming LLM response.

    Providers yield these from ``chat_stream()``.  The consumer (agent loop)
    accumulates them into a full ``LLMResponse``.

    Design notes (from architecture review):
    - ``completed_tool_calls`` can arrive in ANY chunk (Gemini yields
      function_call parts mid-stream), so the loop must accumulate across
      all chunks, not just the final one.
    - ``thinking_blocks`` are accumulated internally by the provider and
      yielded only on the final chunk.
    - ``error_content`` is set when the stream breaks mid-way (don't retry).
    """

    text_delta: str = ""
    completed_tool_calls: list[ToolCallRequest] | None = None
    finish_reason: str | None = None
    thinking_blocks: list[dict] | None = None
    usage: dict[str, int] | None = None
    error_content: str | None = None


@dataclass(frozen=True)
class GenerationSettings:
    """Default generation parameters for LLM calls.

    Stored on the provider so every call site inherits the same defaults
    without having to pass temperature / max_tokens / reasoning_effort
    through every layer.  Individual call sites can still override by
    passing explicit keyword arguments to chat() / chat_with_retry().
    """

    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning_effort: str | None = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Implementations should handle the specifics of each provider's API
    while maintaining a consistent interface.
    """

    _CHAT_RETRY_DELAYS = (1, 2, 4)
    _TRANSIENT_ERROR_MARKERS = (
        "429",
        "rate limit",
        "500",
        "502",
        "503",
        "504",
        "overloaded",
        "timeout",
        "timed out",
        "connection",
        "server error",
        "temporarily unavailable",
    )

    _SENTINEL = object()

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base
        self.generation: GenerationSettings = GenerationSettings()

    @staticmethod
    def _sanitize_log_value(value: Any) -> Any:
        """Return a log-safe value (redact large data URLs used by multimodal inputs)."""
        if isinstance(value, str):
            if value.startswith("data:") and ";base64," in value:
                return f"[data-url redacted: {len(value)} chars]"
            return value
        if isinstance(value, dict):
            return {k: LLMProvider._sanitize_log_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [LLMProvider._sanitize_log_value(v) for v in value]
        return value

    @classmethod
    def _to_log_json(cls, value: Any) -> str:
        """Convert arbitrary objects to JSON for structured logging."""
        safe = cls._sanitize_log_value(value)
        try:
            return json.dumps(safe, ensure_ascii=False, default=str)
        except Exception:
            return str(safe)

    @staticmethod
    def _sanitize_empty_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize message content: fix empty blocks, strip internal _meta fields."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")

            if isinstance(content, str) and not content:
                clean = dict(msg)
                clean["content"] = None if (msg.get("role") == "assistant" and msg.get("tool_calls")) else "(empty)"
                result.append(clean)
                continue

            if isinstance(content, list):
                new_items: list[Any] = []
                changed = False
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") in ("text", "input_text", "output_text")
                        and not item.get("text")
                    ):
                        changed = True
                        continue
                    if isinstance(item, dict) and "_meta" in item:
                        new_items.append({k: v for k, v in item.items() if k != "_meta"})
                        changed = True
                    else:
                        new_items.append(item)
                if changed:
                    clean = dict(msg)
                    if new_items:
                        clean["content"] = new_items
                    elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                        clean["content"] = None
                    else:
                        clean["content"] = "(empty)"
                    result.append(clean)
                    continue

            if isinstance(content, dict):
                clean = dict(msg)
                clean["content"] = [content]
                result.append(clean)
                continue

            result.append(msg)
        return result

    @staticmethod
    def _sanitize_request_messages(
        messages: list[dict[str, Any]],
        allowed_keys: frozenset[str],
    ) -> list[dict[str, Any]]:
        """Keep only provider-safe message keys and normalize assistant content."""
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in allowed_keys}
            if clean.get("role") == "assistant" and "content" not in clean:
                clean["content"] = None
            sanitized.append(clean)
        return sanitized

    @abstractmethod
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
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier (provider-specific).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            tool_choice: Tool selection strategy ("auto", "required", or specific tool dict).
        
        Returns:
            LLMResponse with content and/or tool calls.
        """
        pass

    @classmethod
    def _is_transient_error(cls, content: str | None) -> bool:
        err = (content or "").lower()
        return any(marker in err for marker in cls._TRANSIENT_ERROR_MARKERS)

    @staticmethod
    def _strip_image_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Replace image_url blocks with text placeholder. Returns None if no images found."""
        found = False
        result = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                new_content = []
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "image_url":
                        path = (b.get("_meta") or {}).get("path", "")
                        placeholder = f"[image: {path}]" if path else "[image omitted]"
                        new_content.append({"type": "text", "text": placeholder})
                        found = True
                    else:
                        new_content.append(b)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
        return result if found else None

    # Map class names to PostHog-friendly provider names
    _POSTHOG_PROVIDER_MAP: dict[str, str] = {
        "OpenAIProvider": "openai",
        "VertexGeminiProvider": "google",
    }

    def _posthog_capture(
        self,
        *,
        resolved_model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        response: LLMResponse,
        start_time: float,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Emit a PostHog $ai_generation event (silent no-op if not configured)."""
        try:
            from creato.posthog import capture_generation
            latency = time.monotonic() - start_time
            is_error = response.finish_reason == "error"
            tc_dicts = [
                {"name": tc.name, "arguments": tc.arguments}
                for tc in response.tool_calls
            ] if response.tool_calls else None
            capture_generation(
                model=resolved_model,
                provider=self._POSTHOG_PROVIDER_MAP.get(self.__class__.__name__, self.__class__.__name__.lower()),
                messages=messages,
                output_content=response.content,
                output_tool_calls=tc_dicts,
                input_tokens=response.usage.get("prompt_tokens", 0),
                output_tokens=response.usage.get("completion_tokens", 0),
                latency=latency,
                is_error=is_error,
                error=response.content if is_error else None,
                tools=tools,
                stream=stream,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            pass  # Never let analytics break LLM calls

    async def _safe_chat(self, **kwargs: Any) -> LLMResponse:
        """Call chat() and convert unexpected exceptions to error responses."""
        try:
            return await self.chat(**kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: object = _SENTINEL,
        temperature: object = _SENTINEL,
        reasoning_effort: object = _SENTINEL,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Call chat() with retry on transient provider failures.

        Parameters default to ``self.generation`` when not explicitly passed,
        so callers no longer need to thread temperature / max_tokens /
        reasoning_effort through every layer.
        """
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort

        resolved_model = model or self.get_default_model()
        provider_name = self.__class__.__name__
        _ph_start = time.monotonic()
        _ph_common = dict(
            resolved_model=resolved_model, messages=messages, tools=tools,
            temperature=float(temperature) if isinstance(temperature, (int, float)) else None,
            max_tokens=int(max_tokens) if isinstance(max_tokens, (int, float)) else None,
        )
        kw: dict[str, Any] = dict(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort, tool_choice=tool_choice,
        )
        logger.info(
            "LLM request [{}] model={} payload={}",
            provider_name,
            resolved_model,
            self._to_log_json(
                {
                    "messages": messages,
                    "tools": tools,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "reasoning_effort": reasoning_effort,
                    "tool_choice": tool_choice,
                }
            ),
        )

        for attempt, delay in enumerate(self._CHAT_RETRY_DELAYS, start=1):
            response = await self._safe_chat(**kw)

            logger.info(
                "LLM response [{}] model={} attempt={} payload={}",
                provider_name,
                resolved_model,
                attempt,
                self._to_log_json(
                    {
                        "finish_reason": response.finish_reason,
                        "content": response.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }
                            for tc in response.tool_calls
                        ],
                        "usage": response.usage,
                        "reasoning_content": response.reasoning_content,
                        "thinking_blocks": response.thinking_blocks,
                    }
                ),
            )

            if response.finish_reason != "error":
                self._posthog_capture(**_ph_common, response=response, start_time=_ph_start)
                return response

            if not self._is_transient_error(response.content):
                stripped = self._strip_image_content(messages)
                if stripped is not None:
                    logger.warning("Non-transient LLM error with image content, retrying without images")
                    fallback = await self._safe_chat(**{**kw, "messages": stripped})
                    self._posthog_capture(**_ph_common, response=fallback, start_time=_ph_start)
                    return fallback
                self._posthog_capture(**_ph_common, response=response, start_time=_ph_start)
                return response

            logger.warning(
                "LLM transient error (attempt {}/{}), retrying in {}s: {}",
                attempt, len(self._CHAT_RETRY_DELAYS), delay,
                (response.content or "")[:120].lower(),
            )
            await asyncio.sleep(delay)

        final = await self._safe_chat(**kw)
        self._posthog_capture(**_ph_common, response=final, start_time=_ph_start)
        return final

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass

    # ── streaming interface ─────────────────────────────────────────

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
        """Stream a chat completion as chunks.

        Default implementation falls back to ``chat()`` and yields a single
        chunk.  Providers that support native streaming (e.g. Vertex Gemini)
        should override this method.
        """
        response = await self.chat(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort, tool_choice=tool_choice,
        )
        yield LLMStreamChunk(
            text_delta=response.content or "",
            completed_tool_calls=response.tool_calls or None,
            finish_reason=response.finish_reason,
            thinking_blocks=response.thinking_blocks,
            usage=response.usage or None,
        )

    async def chat_stream_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: object = _SENTINEL,
        temperature: object = _SENTINEL,
        reasoning_effort: object = _SENTINEL,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream with retry on transient failures.

        Three-level retry strategy:
        1. Connection failure (no chunks received) → retry
        2. First chunk is an error → retry
        3. Mid-stream failure (chunks already yielded) → don't retry, yield error chunk
        """
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort

        resolved_model = model or self.get_default_model()
        provider_name = self.__class__.__name__
        _ph_start = time.monotonic()
        _ph_usage: dict[str, int] = {}
        _ph_content_parts: list[str] = []
        _ph_tool_calls: list[dict] = []
        _ph_is_error = False
        _ph_error: str | None = None
        kw: dict[str, Any] = dict(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
            reasoning_effort=reasoning_effort, tool_choice=tool_choice,
        )
        # Log request summary (once, before streaming starts)
        sys_preview = ""
        if messages:
            for m in messages:
                if m.get("role") == "system":
                    raw = m.get("content", "")
                    sys_preview = (raw[:300] + "...") if len(raw) > 300 else raw
                    break
        tool_names = [t.get("function", {}).get("name", "?") for t in (tools or [])]
        logger.info(
            "LLM stream request [{}] model={} messages={} tools={} system_preview={}",
            provider_name, resolved_model, len(messages), tool_names, sys_preview,
        )

        def _ph_accumulate(chunk: LLMStreamChunk) -> None:
            """Accumulate PostHog data from stream chunks."""
            nonlocal _ph_is_error, _ph_error
            if chunk.text_delta:
                _ph_content_parts.append(chunk.text_delta)
            if chunk.completed_tool_calls:
                for tc in chunk.completed_tool_calls:
                    _ph_tool_calls.append({"name": tc.name, "arguments": tc.arguments})
            if chunk.usage:
                _ph_usage.update(chunk.usage)
            if chunk.error_content:
                _ph_is_error = True
                _ph_error = chunk.error_content
            if chunk.finish_reason == "error":
                _ph_is_error = True

        def _ph_emit() -> None:
            """Emit PostHog generation event from accumulated stream data."""
            try:
                from creato.posthog import capture_generation
                capture_generation(
                    model=resolved_model,
                    provider=self._POSTHOG_PROVIDER_MAP.get(provider_name, provider_name.lower()),
                    messages=messages,
                    output_content="".join(_ph_content_parts) or None,
                    output_tool_calls=_ph_tool_calls or None,
                    input_tokens=_ph_usage.get("prompt_tokens", 0),
                    output_tokens=_ph_usage.get("completion_tokens", 0),
                    latency=time.monotonic() - _ph_start,
                    is_error=_ph_is_error,
                    error=_ph_error,
                    tools=tools,
                    stream=True,
                    temperature=float(temperature) if isinstance(temperature, (int, float)) else None,
                    max_tokens=int(max_tokens) if isinstance(max_tokens, (int, float)) else None,
                )
            except Exception:
                pass

        for attempt, delay in enumerate(self._CHAT_RETRY_DELAYS, start=1):
            first_chunk_received = False
            try:
                async for chunk in self.chat_stream(**kw):
                    first_chunk_received = True
                    _ph_accumulate(chunk)
                    yield chunk
                    if chunk.finish_reason:
                        # Log usage if present
                        if chunk.usage:
                            logger.info(
                                "LLM stream done [{}] model={} attempt={} usage={}",
                                provider_name, resolved_model, attempt, chunk.usage                            )
                _ph_emit()
                return  # stream completed successfully
            except asyncio.CancelledError:
                _ph_is_error = True
                _ph_error = "cancelled"
                _ph_emit()
                raise
            except Exception as exc:
                if first_chunk_received:
                    # Mid-stream failure — don't retry
                    logger.error(
                        "LLM stream broke mid-way [{}] model={}: {}",
                        provider_name, resolved_model, exc,
                    )
                    _ph_is_error = True
                    _ph_error = f"Stream interrupted: {exc}"
                    _ph_emit()
                    yield LLMStreamChunk(
                        finish_reason="error",
                        error_content=f"Stream interrupted: {exc}",
                    )
                    return

                err_str = str(exc)
                if not self._is_transient_error(err_str):
                    # Non-transient — try without images, then give up
                    stripped = self._strip_image_content(messages)
                    if stripped is not None:
                        logger.warning("Non-transient stream error with images, retrying without")
                        try:
                            async for chunk in self.chat_stream(**{**kw, "messages": stripped}):
                                _ph_accumulate(chunk)
                                yield chunk
                            _ph_emit()
                            return
                        except Exception:
                            pass
                    _ph_is_error = True
                    _ph_error = f"Error calling LLM: {exc}"
                    _ph_emit()
                    yield LLMStreamChunk(
                        finish_reason="error",
                        error_content=f"Error calling LLM: {exc}",
                    )
                    return

                logger.warning(
                    "LLM stream transient error (attempt {}/{}), retrying in {}s: {}",
                    attempt, len(self._CHAT_RETRY_DELAYS), delay, err_str[:120],
                )
                # Reset accumulators for retry
                _ph_content_parts.clear()
                _ph_tool_calls.clear()
                _ph_usage.clear()
                _ph_is_error = False
                _ph_error = None
                await asyncio.sleep(delay)

        # Final attempt — no more retries
        try:
            async for chunk in self.chat_stream(**kw):
                _ph_accumulate(chunk)
                yield chunk
            _ph_emit()
        except Exception as exc:
            _ph_is_error = True
            _ph_error = f"Error calling LLM after retries: {exc}"
            _ph_emit()
            yield LLMStreamChunk(
                finish_reason="error",
                error_content=f"Error calling LLM after retries: {exc}",
            )
