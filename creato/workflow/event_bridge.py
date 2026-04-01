"""Event bridge between RabbitMQ consumer and SSE generators.

Provides a ws_id → asyncio.Queue registry so that:
- rabbitmq.py dispatches events here (via injected callback)
- api/workflow.py consumes events from the queue in SSE generators

This module owns no infrastructure — it's pure in-process routing.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

_MAX_QUEUES = 500
_TTL_SECONDS = 4 * 3600  # 4 hours (aligned with Consumer's 3h lock TTL)

# ws_id → (queue, registered_at_monotonic)
_event_queues: dict[str, tuple[asyncio.Queue, float]] = {}


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


def get_event_queue(ws_id: str) -> asyncio.Queue | None:
    """Return the existing event queue for a ws_id, or None if not registered."""
    entry = _event_queues.get(ws_id)
    if entry is None:
        return None
    q, registered_at = entry
    if time.monotonic() - registered_at > _TTL_SECONDS:
        _event_queues.pop(ws_id, None)
        return None
    return q


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


# ── Run Snapshot Store ────────────────────────────────────────────
# Captures DAG + node outputs during a run so that continue_workflow
# can restart from the paused point without depending on consumer memory.


@dataclass
class RunSnapshot:
    """Snapshot of a workflow run, built incrementally from events."""

    flow_task_id: str
    ws_id: str
    nodes: list[dict]
    edges: list[dict]
    consumer_run_id: str = ""  # Real run_id from consumer's start_flow event
    paused_node_ids: set[str] = field(default_factory=set)
    # node_id → raw node_outputs dict from events
    # e.g. {"text": {"node_id": "xxx", "outputs": [...]}}
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)


_run_snapshots: dict[str, RunSnapshot] = {}


def store_run_snapshot(flow_task_id: str, snapshot: RunSnapshot) -> None:
    """Store or replace a run snapshot."""
    _run_snapshots[flow_task_id] = snapshot


def get_run_snapshot(flow_task_id: str) -> RunSnapshot | None:
    """Peek at a run snapshot (does NOT delete)."""
    return _run_snapshots.get(flow_task_id)


def clear_run_snapshot(flow_task_id: str) -> None:
    """Explicitly remove a run snapshot."""
    _run_snapshots.pop(flow_task_id, None)


def update_snapshot_consumer_run_id(flow_task_id: str, run_id: str) -> None:
    """Store the consumer's real run_id from start_flow event."""
    snap = _run_snapshots.get(flow_task_id)
    if snap:
        snap.consumer_run_id = run_id


def update_snapshot_node_outputs(
    flow_task_id: str, node_id: str, outputs: dict[str, Any]
) -> None:
    """Append/overwrite node outputs in an existing snapshot."""
    snap = _run_snapshots.get(flow_task_id)
    if snap:
        snap.node_outputs[node_id] = outputs


def update_snapshot_paused_node(flow_task_id: str, node_id: str) -> None:
    """Record which node entered select mode."""
    snap = _run_snapshots.get(flow_task_id)
    if snap:
        snap.paused_node_ids.add(node_id)


def resolve_snapshot_paused_node(flow_task_id: str, node_id: str) -> None:
    """Remove a node from the paused set after user selects via HTTP."""
    snap = _run_snapshots.get(flow_task_id)
    if snap:
        snap.paused_node_ids.discard(node_id)


# ── Legacy compat (store_paused_context / get_paused_context) ─────
# Kept for any code that still references the old API.

def store_paused_context(flow_task_id: str, ctx: dict[str, str]) -> None:
    """Legacy: store minimal paused context. Prefer RunSnapshot."""
    node_id = ctx.get("node_id", "")
    if not node_id:
        return
    snap = _run_snapshots.get(flow_task_id)
    if snap:
        snap.paused_node_ids.add(node_id)
    else:
        # Fallback: create a minimal snapshot
        _run_snapshots[flow_task_id] = RunSnapshot(
            flow_task_id=flow_task_id,
            ws_id=ctx.get("ws_id", ""),
            nodes=[],
            edges=[],
            paused_node_ids={node_id},
        )


def get_paused_context(flow_task_id: str) -> dict[str, str] | None:
    """Legacy: retrieve paused context from snapshot (does NOT delete)."""
    snap = _run_snapshots.get(flow_task_id)
    if not snap or not snap.paused_node_ids:
        return None
    return {
        "ws_id": snap.ws_id,
        "node_id": next(iter(snap.paused_node_ids)),
    }
