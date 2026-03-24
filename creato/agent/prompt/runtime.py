"""Runtime context injection — per-request metadata prepended to user message.

This is NOT part of the system prompt. It is prepended to the user message
so the LLM knows the current time, channel, and flow context without
polluting the cacheable system prompt.
"""

from typing import Any

from creato.utils.helpers import current_time_str

RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"


def build_runtime_context(
    channel: str | None = None,
    chat_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Build untrusted runtime metadata block for injection before the user message."""
    lines = [f"Current Time: {current_time_str()}"]
    if channel and chat_id:
        lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
    if metadata:
        flow_id = metadata.get("flow_id")
        if isinstance(flow_id, str) and flow_id.strip():
            lines.append(f"Flow ID: {flow_id.strip()}")
    return RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)
