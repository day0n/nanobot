"""Event bridge between RabbitMQ consumer and SSE generators.

Provides a ws_id → asyncio.Queue registry so that:
- rabbitmq.py dispatches events here (via injected callback)
- api/workflow.py consumes events from the queue in SSE generators

This module owns no infrastructure — it's pure in-process routing.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

_MAX_QUEUES = 500
_TTL_SECONDS = 4 * 3600  # 4 hours (aligned with Consumer's 3h lock TTL)

# ws_id → (queue, registered_at_monotonic)
_event_queues: dict[str, tuple[asyncio.Queue, float]] = {}

# Paused workflow context: flow_task_id → {flow_run_id, ws_id, node_id}
# Written by executor when workflow enters select mode,
# read by ContinueWorkflowTool so the LLM doesn't need to pass IDs.
_paused_contexts: dict[str, dict[str, str]] = {}


def _sweep_expired() -> None:
    """Remove queues older than _TTL_SECONDS. Called lazily from register/dispatch."""
    now = time.monotonic()
    expired = [k for k, (_, t) in _event_queues.items() if now - t > _TTL_SECONDS]
    for k in expired:
        _event_queues.pop(k, None)


def register(ws_id: str) -> asyncio.Queue:
    """Register an event queue for a workflow execution. Returns the queue."""
    # Sweep before adding to stay under the cap
    if len(_event_queues) >= _MAX_QUEUES:
        _sweep_expired()
    # If still at cap after sweep, evict the oldest entry
    while len(_event_queues) >= _MAX_QUEUES:
        oldest = next(iter(_event_queues))
        _event_queues.pop(oldest, None)

    q: asyncio.Queue = asyncio.Queue()
    _event_queues[ws_id] = (q, time.monotonic())
    return q


def unregister(ws_id: str) -> None:
    """Remove the event queue for a workflow execution."""
    _event_queues.pop(ws_id, None)


async def dispatch(ws_id: str, event: dict[str, Any]) -> bool:
    """Dispatch an event to the registered queue. Returns True if delivered."""
    entry = _event_queues.get(ws_id)
    if entry is not None:
        q, registered_at = entry
        # Auto-expire stale queues
        if time.monotonic() - registered_at > _TTL_SECONDS:
            _event_queues.pop(ws_id, None)
            return False
        await q.put(event)
        return True
    return False


# ── Paused workflow context ────────────────────────────────────────

def store_paused_context(flow_task_id: str, ctx: dict[str, str]) -> None:
    """Store paused workflow context so continue_workflow can look it up."""
    _paused_contexts[flow_task_id] = ctx


def get_paused_context(flow_task_id: str) -> dict[str, str] | None:
    """Retrieve and remove paused workflow context."""
    return _paused_contexts.pop(flow_task_id, None)
