"""Token counting utilities for context window management.

Uses tiktoken (cl100k_base encoding) which covers GPT-4, Claude, and most
modern LLMs with sufficient accuracy for budget calculations.
"""

from __future__ import annotations

import tiktoken

_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def count_text(text: str) -> int:
    """Count tokens in a plain text string."""
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def count_message(msg: dict) -> int:
    """Count tokens for a single chat message (including role overhead).

    Accounts for:
    - ~4 token overhead per message (role tag, separators)
    - Text content
    - Multimodal content (images estimated at 300 tokens each)
    - tool_calls function name + arguments
    """
    tokens = 4  # role + separators overhead

    content = msg.get("content", "")
    if isinstance(content, str):
        tokens += count_text(content)
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                tokens += count_text(part.get("text", ""))
            elif part.get("type") == "image_url":
                tokens += 300  # fixed estimate for images

    for tc in msg.get("tool_calls") or []:
        func = tc.get("function", {})
        tokens += count_text(func.get("name", ""))
        tokens += count_text(func.get("arguments", ""))

    return tokens


def count_messages(messages: list[dict]) -> int:
    """Count total tokens for a message list (with reply priming overhead)."""
    return sum(count_message(m) for m in messages) + 3
