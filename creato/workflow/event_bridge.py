"""Event bridge between RabbitMQ consumer and SSE generators.

Provides a ws_id → asyncio.Queue registry so that:
- rabbitmq.py dispatches events here (via injected callback)
- api/workflow.py consumes events from the queue in SSE generators

This module owns no infrastructure — it's pure in-process routing.
"""

from __future__ import annotations

import asyncio
from typing import Any

_event_queues: dict[str, asyncio.Queue] = {}


def register(ws_id: str) -> asyncio.Queue:
    """Register an event queue for a workflow execution. Returns the queue."""
    q: asyncio.Queue = asyncio.Queue()
    _event_queues[ws_id] = q
    return q


def unregister(ws_id: str) -> None:
    """Remove the event queue for a workflow execution."""
    _event_queues.pop(ws_id, None)


async def dispatch(ws_id: str, event: dict[str, Any]) -> bool:
    """Dispatch an event to the registered queue. Returns True if delivered."""
    q = _event_queues.get(ws_id)
    if q is not None:
        await q.put(event)
        return True
    return False
