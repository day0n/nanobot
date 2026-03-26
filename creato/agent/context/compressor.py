"""Context compressor — summarises dropped history messages.

Uses a lightweight LLM provider to produce a short summary of conversation
turns that were trimmed by the sliding window. The summary is injected back
into the context so the agent retains awareness of earlier discussion without
consuming the full token budget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from creato.providers.base import LLMProvider

_COMPRESS_PROMPT = """\
Summarize the following conversation between a user and an AI assistant.
Focus on: decisions made, tasks completed, user preferences expressed, and any pending items.
Keep it under 200 words. Write in the same language as the conversation.

Conversation:
{conversation}

Summary:"""


class ContextCompressor:
    """Compress dropped conversation messages into a concise summary."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def compress(self, messages: list[dict[str, Any]]) -> str | None:
        """Compress a list of messages into a summary string.

        Returns None if the messages are too few to be worth compressing.
        """
        if len(messages) < 4:  # fewer than ~2 turns
            return None

        conversation = self._format_messages(messages)
        if not conversation:
            return None

        try:
            response = await self._provider.chat(
                messages=[{
                    "role": "user",
                    "content": _COMPRESS_PROMPT.format(conversation=conversation),
                }],
                max_tokens=300,
                temperature=0.1,
            )
            summary = response.content
            return summary.strip() if summary else None
        except Exception as e:
            logger.warning("Context compression LLM call failed: {}", e)
            return None

    @staticmethod
    def _format_messages(messages: list[dict[str, Any]]) -> str:
        """Format messages into readable text for the compression prompt."""
        lines: list[str] = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role not in ("user", "agent", "assistant"):
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            label = "User" if role == "user" else "Assistant"
            text = content[:500] + "..." if len(content) > 500 else content
            lines.append(f"{label}: {text}")
        return "\n".join(lines)
