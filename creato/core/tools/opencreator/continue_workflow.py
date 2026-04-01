"""ContinueWorkflowTool — continue a paused workflow via WorkflowEngine.

Uses the consumer's real run_id (captured from start_flow event) to call
submit_continue, which resumes the existing executor in the consumer.
"""

from __future__ import annotations

import json
from typing import Any

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
        from creato.workflow.event_bridge import register, unregister, get_run_snapshot

        request_context = get_request_context()
        user_id = request_context.get("user_id")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."
        if not flow_task_id:
            return "Error: flow_task_id is required."
        if not node_id:
            return "Error: node_id is required."

        # ── 1. Get run snapshot ────────────────────────────────────────
        snapshot = get_run_snapshot(flow_task_id)
        if not snapshot:
            return (
                f"Error: no run snapshot found for flow_task_id={flow_task_id}. "
                "The workflow may not have been run in this session."
            )

        consumer_run_id = snapshot.consumer_run_id
        ws_id = snapshot.ws_id
        if not consumer_run_id:
            return "Error: consumer run_id not captured. The workflow may not have started properly."
        if not ws_id:
            return "Error: ws_id not found in snapshot."

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

        # ── 5. Register event queue and submit continue ────────────────
        event_queue = register(ws_id)

        try:
            await self._engine.submit_continue(
                flow_task_id=flow_task_id,
                flow_run_id=consumer_run_id,
                ws_id=ws_id,
                user_id=user_id or "",
                user_selection=user_selection,
            )
        except Exception as e:
            unregister(ws_id)
            return f"Error: failed to continue workflow — {e}"

        logger.info(
            f"ContinueWorkflowTool: submitted continue for {flow_task_id}, "
            f"consumer_run_id={consumer_run_id}, ws_id={ws_id}"
        )

        # ── 6. Return WorkflowExecution ────────────────────────────────
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
                    flow_task_id,
                )
            except asyncio.CancelledError:
                if not _terminal_seen:
                    await self._engine.kill(flow_task_id)
                    logger.info(f"ContinueWorkflowTool: task cancelled, killed workflow. {flow_task_id=}")
                raise
            except GeneratorExit:
                if not _terminal_seen:
                    await self._engine.kill(flow_task_id)
                    logger.info(f"ContinueWorkflowTool: stream closed, killed workflow. {flow_task_id=}")
                else:
                    logger.debug(f"ContinueWorkflowTool: stream closed after terminal, no kill. {flow_task_id=}")
            finally:
                unregister(ws_id)

        from ._workflow_callbacks import build_interpret_event, build_make_sse_event

        return WorkflowExecution(
            flow_task_id=flow_task_id,
            run_id=consumer_run_id,
            ws_id=ws_id,
            event_stream=_event_stream(),
            interpret_event=build_interpret_event(flow_task_id, consumer_run_id, ws_id),
            make_sse_event=build_make_sse_event(),
        )


# ── Helpers ────────────────────────────────────────────────────────


def _expand_outputs(node_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten node_outputs into a list of individual output items.

    node_outputs format from events:
      {"text": {"node_id": "xxx", "outputs": [item1, item2, ...]}}

    For splitText, a single output item may contain a JSON array in its
    "output" field — expand each segment into its own item.
    """
    expanded: list[dict[str, Any]] = []

    for io_type, io_data in node_outputs.items():
        if not isinstance(io_data, dict):
            continue
        outputs = io_data.get("outputs", [])
        for out in outputs:
            if not isinstance(out, dict):
                continue
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
        selection_key = "text" if io_type == "splitText" else io_type

        if selection_key not in grouped:
            grouped[selection_key] = []

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
