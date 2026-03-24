"""PostHog LLM Analytics — client singleton and event capture helpers.

All public functions are silent no-ops when PostHog is not configured,
mirroring the pattern used by creato/sentry.py.
"""

from __future__ import annotations

import json
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from posthog import Posthog
    from creato.config.schema import PostHogConfig

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_client: Posthog | None = None
_privacy_mode: bool = False


def init_posthog(cfg: PostHogConfig) -> None:
    """Initialize the PostHog client. No-op if api_key is empty or disabled."""
    global _client, _privacy_mode
    if _client is not None:
        return
    if not cfg.enabled or not cfg.api_key:
        logger.info("PostHog skipped (enabled={}, api_key={})", cfg.enabled, "set" if cfg.api_key else "empty")
        return
    try:
        from posthog import Posthog
        _client = Posthog(cfg.api_key, host=cfg.host)
        _privacy_mode = cfg.privacy_mode
        logger.info("PostHog initialized (host={})", cfg.host)
    except Exception as e:
        logger.warning("Failed to initialize PostHog: {}", e)


def shutdown_posthog() -> None:
    """Flush and close the PostHog client."""
    global _client
    if _client is None:
        return
    try:
        _client.flush()
        _client.shutdown()
    except Exception:
        pass
    _client = None


# ---------------------------------------------------------------------------
# User identification — link Clerk user_id with email for PostHog
# ---------------------------------------------------------------------------

_identified_users: set[str] = set()  # avoid repeated identify calls per process


def identify_user(user_id: str, email: str) -> None:
    """Identify a user in PostHog, linking user_id with email.

    Also creates an alias so that publisher events (distinct_id=email)
    and agent events (distinct_id=user_id) merge into one PostHog person.

    Called once per user per process lifetime (cached in _identified_users).
    """
    if _client is None or not user_id or not email:
        return
    if user_id in _identified_users:
        return
    _identified_users.add(user_id)

    try:
        # Set user properties (email visible in PostHog UI)
        _client.identify(
            distinct_id=user_id,
            properties={
                "email": email,
                "$email": email,  # PostHog's built-in email property
            },
        )
        # Alias: merge publisher's email-based events with agent's user_id-based events
        _client.alias(
            previous_id=email,
            distinct_id=user_id,
        )
    except Exception as e:
        logger.debug("PostHog identify/alias failed: {}", e)


# ---------------------------------------------------------------------------
# Context propagation via contextvars
# ---------------------------------------------------------------------------

@dataclass
class PostHogContext:
    """Per-request PostHog context."""
    trace_id: str = ""
    session_id: str = ""
    distinct_id: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


_posthog_ctx: ContextVar[PostHogContext] = ContextVar(
    "creato_posthog_context",
    default=PostHogContext(),
)


def set_posthog_context(
    trace_id: str = "",
    session_id: str = "",
    distinct_id: str = "",
    properties: dict[str, Any] | None = None,
) -> Token[PostHogContext]:
    """Set PostHog context for the current async task."""
    return _posthog_ctx.set(PostHogContext(
        trace_id=trace_id,
        session_id=session_id,
        distinct_id=distinct_id,
        properties=dict(properties or {}),
    ))


def reset_posthog_context(token: Token[PostHogContext]) -> None:
    """Reset PostHog context."""
    _posthog_ctx.reset(token)


def get_posthog_context() -> PostHogContext:
    """Get current PostHog context."""
    return _posthog_ctx.get()


# ---------------------------------------------------------------------------
# Event capture
# ---------------------------------------------------------------------------

def capture_generation(
    *,
    model: str,
    provider: str,
    messages: list[dict[str, Any]] | None = None,
    output_content: str | None = None,
    output_tool_calls: list[dict[str, Any]] | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency: float = 0.0,
    is_error: bool = False,
    error: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    stream: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> None:
    """Capture an $ai_generation event to PostHog.

    Reads trace_id / session_id / distinct_id from the current PostHogContext.
    Silent no-op when PostHog is not initialized.
    """
    if _client is None:
        return

    ctx = _posthog_ctx.get()
    if not ctx.trace_id:
        return  # No trace context — skip (e.g. summary generation)

    distinct_id = ctx.distinct_id or "anonymous"

    # Build output choices
    output_choices: list[dict[str, Any]] = []
    if output_content or output_tool_calls:
        choice_content: list[dict[str, Any]] = []
        if output_content:
            choice_content.append({"type": "text", "text": output_content})
        for tc in (output_tool_calls or []):
            choice_content.append({
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": tc.get("arguments", {}),
                },
            })
        output_choices.append({"role": "assistant", "content": choice_content})

    properties: dict[str, Any] = {
        "$ai_trace_id": ctx.trace_id,
        "$ai_model": model,
        "$ai_provider": provider,
        "$ai_input_tokens": input_tokens,
        "$ai_output_tokens": output_tokens,
        "$ai_latency": round(latency, 3),
        "$ai_is_error": is_error,
        "$ai_stream": stream,
    }

    if ctx.session_id:
        properties["$ai_session_id"] = ctx.session_id

    if not _privacy_mode:
        if messages is not None:
            properties["$ai_input"] = _sanitize_messages(messages)
        if output_choices:
            properties["$ai_output_choices"] = output_choices

    if error:
        properties["$ai_error"] = error[:2000]
    if tools:
        properties["$ai_tools"] = tools
    if temperature is not None:
        properties["$ai_temperature"] = temperature
    if max_tokens is not None:
        properties["$ai_max_tokens"] = max_tokens

    # Merge any custom properties from context
    if ctx.properties:
        properties.update(ctx.properties)

    try:
        _client.capture(
            distinct_id=distinct_id,
            event="$ai_generation",
            properties=properties,
        )
    except Exception as e:
        logger.debug("PostHog capture failed: {}", e)


def capture_trace(
    *,
    input_state: Any = None,
    output_state: Any = None,
    latency: float = 0.0,
    is_error: bool = False,
    error: str | None = None,
    name: str = "agent_chat",
) -> None:
    """Capture an $ai_trace event to PostHog (trace-level summary).

    Silent no-op when PostHog is not initialized.
    """
    if _client is None:
        return

    ctx = _posthog_ctx.get()
    if not ctx.trace_id:
        return

    distinct_id = ctx.distinct_id or "anonymous"

    properties: dict[str, Any] = {
        "$ai_trace_id": ctx.trace_id,
        "$ai_latency": round(latency, 3),
        "$ai_span_name": name,
        "$ai_is_error": is_error,
    }

    if ctx.session_id:
        properties["$ai_session_id"] = ctx.session_id

    if not _privacy_mode:
        if input_state is not None:
            properties["$ai_input_state"] = input_state
        if output_state is not None:
            properties["$ai_output_state"] = output_state

    if error:
        properties["$ai_error"] = error[:2000]

    if ctx.properties:
        properties.update(ctx.properties)

    try:
        _client.capture(
            distinct_id=distinct_id,
            event="$ai_trace",
            properties=properties,
        )
    except Exception as e:
        logger.debug("PostHog trace capture failed: {}", e)


def capture_span(
    *,
    span_id: str = "",
    name: str,
    input_data: Any = None,
    output_data: Any = None,
    latency: float = 0.0,
    is_error: bool = False,
    error: str | None = None,
) -> None:
    """Capture an $ai_span event to PostHog (e.g. tool execution).

    Silent no-op when PostHog is not initialized.
    """
    if _client is None:
        return

    ctx = _posthog_ctx.get()
    if not ctx.trace_id:
        return

    distinct_id = ctx.distinct_id or "anonymous"

    properties: dict[str, Any] = {
        "$ai_trace_id": ctx.trace_id,
        "$ai_span_name": name,
        "$ai_latency": round(latency, 3),
        "$ai_is_error": is_error,
    }

    if span_id:
        properties["$ai_span_id"] = span_id
    if ctx.session_id:
        properties["$ai_session_id"] = ctx.session_id

    if not _privacy_mode:
        if input_data is not None:
            properties["$ai_input_state"] = _truncate_any(input_data, 8000)
        if output_data is not None:
            properties["$ai_output_state"] = _truncate_any(output_data, 8000)

    if error:
        properties["$ai_error"] = error[:2000]

    if ctx.properties:
        properties.update(ctx.properties)

    try:
        _client.capture(
            distinct_id=distinct_id,
            event="$ai_span",
            properties=properties,
        )
    except Exception as e:
        logger.debug("PostHog span capture failed: {}", e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate_any(value: Any, max_len: int) -> Any:
    """Truncate a value for PostHog payload size control."""
    if isinstance(value, str):
        return value[:max_len]
    if isinstance(value, dict):
        s = json.dumps(value, ensure_ascii=False, default=str)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return value
    return value

def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize messages for PostHog — redact large data URLs and cap size."""
    result = []
    for msg in messages:
        clean: dict[str, Any] = {"role": msg.get("role", "unknown")}
        content = msg.get("content")
        if isinstance(content, str):
            clean["content"] = content[:8000]  # Cap per-message size
        elif isinstance(content, list):
            items = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "image_url":
                        items.append({"type": "image_url", "image_url": "[redacted]"})
                    elif item.get("type") == "text":
                        items.append({"type": "text", "text": (item.get("text") or "")[:4000]})
                    else:
                        items.append(item)
                else:
                    items.append(item)
            clean["content"] = items
        else:
            clean["content"] = content
        result.append(clean)
    return result


def posthog_timer() -> float:
    """Return a monotonic timestamp for latency measurement."""
    return time.monotonic()
