"""ContinueWorkflowTool — restart a paused workflow from the select point.

Instead of sending flow_run_type=continue to the consumer (which depends on
consumer in-memory state), this tool kills the old flow and starts a fresh
run with start_ids pointing to the resume frontier. The consumer's existing
start_ids + user_selection mechanism handles the rest.
"""

from __future__ import annotations

import json
from typing import Any

import networkx as nx
from loguru import logger

from creato.core.request_context import get_request_context
from creato.core.tools.base import Tool, WorkflowExecution


class ContinueWorkflowTool(Tool):
    """Continue a paused workflow after the user has chosen which result to use."""

    name = "continue_workflow"
    description = (
        "Continue a paused workflow after the user has chosen which output to use. "
        "Call get_workflow_results first to see the available outputs for the paused node, "
        "then pass the node_id and the 1-based indices of the chosen outputs.\n"
        "- Multi-model node (e.g. 2 models): pass selected_indices=[1] to pick the first model's output.\n"
        "- Text splitter node (splitText): pass selected_indices=[1,2,3] to pick segments, "
        "or omit selected_indices to use ALL segments."
    )
    parameters = {
        "type": "object",
        "properties": {
            "flow_task_id": {
                "type": "string",
                "description": "The flow_task_id from the paused workflow context.",
            },
            "node_id": {
                "type": "string",
                "description": "The node_id of the paused select node.",
            },
            "selected_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "1-based indices of the outputs to use. "
                    "For multi-model nodes pass one index (e.g. [1]). "
                    "For splitText nodes pass multiple (e.g. [1,2,3]) or omit to select all."
                ),
            },
        },
        "required": ["flow_task_id", "node_id"],
    }

    def __init__(self, workflow_engine: Any = None, workflow_dao: Any = None):
        self._engine = workflow_engine
        self._dao = workflow_dao

    async def execute(
        self,
        flow_task_id: str = "",
        node_id: str = "",
        selected_indices: list[int] | None = None,
        **_: Any,
    ) -> str | WorkflowExecution:
        from nanoid import generate as nanoid_generate
        from creato.workflow.event_bridge import (
            register, unregister,
            get_run_snapshot, clear_run_snapshot,
            store_run_snapshot, RunSnapshot,
        )

        request_context = get_request_context()
        user_id = request_context.get("user_id")
        flow_id = request_context.get("flow_id")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."
        if not flow_task_id:
            return "Error: flow_task_id is required."
        if not node_id:
            return "Error: node_id is required."

        # ── 1. Get run snapshot ─────────────────────────────────────
        snapshot = get_run_snapshot(flow_task_id)
        if not snapshot:
            return (
                f"Error: no run snapshot found for flow_task_id={flow_task_id}. "
                "The workflow may not have been run in this session."
            )
        if not snapshot.nodes:
            return "Error: run snapshot has no DAG data."

        # ── 2. Get paused node outputs from snapshot ───────────────────
        paused_outputs = snapshot.node_outputs.get(node_id)
        if not paused_outputs:
            return (
                f"Error: no outputs captured for paused node {node_id}. "
                "The node may not have produced results yet."
            )

        # ── 3. Expand splitText + select by indices ────────────────────
        expanded = _expand_outputs(paused_outputs)
        if selected_indices is None:
            chosen = expanded  # select all (typical for splitText)
        else:
            if any(i < 1 or i > len(expanded) for i in selected_indices):
                return (
                    f"Error: selected_indices out of range "
                    f"(valid: 1–{len(expanded)}, got: {selected_indices})."
                )
            chosen = [expanded[i - 1] for i in selected_indices]

        if not chosen:
            return "Error: no outputs selected."

        # ── 4. Build user_selection ────────────────────────────────────
        user_selection = _build_user_selection(node_id, chosen)

        # ── 5. Compute start_ids (successors of paused node) ──────────
        graph = nx.DiGraph()
        for n in snapshot.nodes:
            if isinstance(n, dict) and "id" in n:
                graph.add_node(n["id"])
        for e in snapshot.edges:
            if isinstance(e, dict) and e.get("source") and e.get("target"):
                graph.add_edge(e["source"], e["target"])

        start_ids = list(graph.successors(node_id))
        if not start_ids:
            return f"Error: paused node {node_id} has no downstream nodes to resume."

        # ── 6. Kill old flow ───────────────────────────────────────────
        await self._engine.kill(flow_task_id)
        logger.info(f"ContinueWorkflowTool: killed old flow {flow_task_id}")

        # ── 7. Submit fresh start ──────────────────────────────────────
        new_ws_id = nanoid_generate(size=9)
        event_queue = register(new_ws_id)

        try:
            new_flow_task_id, new_flow_run_id = await self._engine.submit_start(
                nodes=snapshot.nodes,
                edges=snapshot.edges,
                ws_id=new_ws_id,
                user_id=user_id or "",
                start_ids=start_ids,
                end_ids=None,
                user_selection=user_selection,
            )
        except Exception as e:
            unregister(new_ws_id)
            return f"Error: failed to restart workflow — {e}"

        # ── 8. Rotate snapshots ────────────────────────────────────────
        clear_run_snapshot(flow_task_id)
        store_run_snapshot(new_flow_task_id, RunSnapshot(
            flow_task_id=new_flow_task_id,
            ws_id=new_ws_id,
            nodes=snapshot.nodes,
            edges=snapshot.edges,
        ))

        logger.info(
            f"ContinueWorkflowTool: restarted as {new_flow_task_id}, "
            f"start_ids={start_ids}, ws_id={new_ws_id}"
        )

        # ── 9. Return new WorkflowExecution ────────────────────────────
        async def _event_stream():
            _terminal_seen = False
            try:
                import asyncio
                while True:
                    event = await asyncio.wait_for(event_queue.get(), timeout=480)
                    et = event.get("event_type")
                    if et in ("finish_flow", "flow_killed"):
                        _terminal_seen = True
                    if et == "node_status" and event.get("status") == "select":
                        _terminal_seen = True
                    yield event
                    if _terminal_seen:
                        break
            except asyncio.TimeoutError:
                logger.info(
                    "ContinueWorkflowTool: 8min timeout, disconnecting SSE "
                    "(not killing). flow_task_id={}",
                    new_flow_task_id,
                )
            except asyncio.CancelledError:
                if not _terminal_seen:
                    await self._engine.kill(new_flow_task_id)
                    logger.info(f"ContinueWorkflowTool: task cancelled, killed workflow. {new_flow_task_id=}")
                raise
            except GeneratorExit:
                if not _terminal_seen:
                    await self._engine.kill(new_flow_task_id)
                    logger.info(f"ContinueWorkflowTool: stream closed, killed workflow. {new_flow_task_id=}")
                else:
                    logger.debug(f"ContinueWorkflowTool: stream closed after terminal, no kill. {new_flow_task_id=}")
            finally:
                unregister(new_ws_id)

        from ._workflow_callbacks import build_interpret_event, build_make_sse_event

        return WorkflowExecution(
            flow_task_id=new_flow_task_id,
            run_id=new_flow_run_id,
            ws_id=new_ws_id,
            event_stream=_event_stream(),
            interpret_event=build_interpret_event(new_flow_task_id, new_flow_run_id, new_ws_id),
            make_sse_event=build_make_sse_event(),
        )


# ── Helpers ─────────────────────────────────────────────


def _expand_outputs(node_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten node_outputs into a list of individual output items.

    node_outputs format from events:
      {"text": {"node_id": "xxx", "outputs": [item1, item2, ...]}}

    For splitText, a single output item may contain a JSON array in its
    "output" field — expand each segment into its own item.

    Returns a flat list of output items (each is a dict with model, output, path, type, etc.)
    """
    expanded: list[dict[str, Any]] = []

    for io_type, io_data in node_outputs.items():
        if not isinstance(io_data, dict):
            continue
        outputs = io_data.get("outputs", [])
        for out in outputs:
            if not isinstance(out, dict):
                continue
            # Tag with io_type for user_selection building
            item = {**out, "_io_type": io_type}

            # splitText: expand formatted_output or JSON-encoded output
            if io_type == "splitText" or out.get("type") == "splitText":
                segments = out.get("formatted_output")
                if not isinstance(segments, list):
                    raw = out.get("output", "")
                    try:
                        segments = json.loads(raw) if isinstance(raw, str) and raw.startswith("[") else None
                    except (json.JSONDecodeError, TypeError):
                        segments = None

                if isinstance(segments, list) and len(segments) > 1:
                    for seg in segments:
                        expanded.append({
                            **{k: v for k, v in item.items() if k not in ("output", "formatted_output")},
                            "output": seg if isinstance(seg, str) else str(seg),
                        })
                    continue

            expanded.append(item)

    return expanded


def _build_user_selection(
    paused_node_id: str,
    chosen_items: list[dict[str, Any]],
) -> dict[str, list[dict]]:
    """Build user_selection dict from chosen output items.

    Format: { "text": [{ "node_id": "xxx", "outputs": [...] }] }
    splitText is normalized to "text" (matching frontend behavior).
    """
    grouped: dict[str, list[dict]] = {}

    for item in chosen_items:
        io_type = item.pop("_io_type", "text")
        # Frontend normalizes splitText → text
        selection_key = "text" if io_type == "splitText" else io_type

        if selection_key not in grouped:
            grouped[selection_key] = []

        # Find or create the entry for this node
        entry = None
        for e in grouped[selection_key]:
            if e["node_id"] == paused_node_id:
                entry = e
                break
        if entry is None:
            entry = {"node_id": paused_node_id, "outputs": []}
            grouped[selection_key].append(entry)

        entry["outputs"].append({
            "model": item.get("model", ""),
            "output": item.get("output", ""),
            "path": item.get("path") or [],
        })

    return grouped
