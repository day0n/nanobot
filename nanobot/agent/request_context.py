"""Request-scoped private context for tool calls."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_request_context: ContextVar[dict[str, Any]] = ContextVar(
    "nanobot_request_context",
    default={},
)


def set_request_context(context: dict[str, Any] | None) -> Token[dict[str, Any]]:
    """Set the current request-scoped private context."""
    return _request_context.set(dict(context or {}))


def reset_request_context(token: Token[dict[str, Any]]) -> None:
    """Reset the current request-scoped private context."""
    _request_context.reset(token)


def get_request_context() -> dict[str, Any]:
    """Return the current request-scoped private context."""
    return dict(_request_context.get())
