"""ContinueWorkflowTool — continue a paused workflow via WorkflowEngine."""

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
        from creato.workflow.event_bridge import register, unregister, get_paused_context

        request_context = get_request_context()
        user_id = request_context.get("user_id")
        flow_id = request_context.get("flow_id")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."
        if not self._dao:
            return "Error: workflow data access is not configured."
        if not flow_task_id:
            return "Error: flow_task_id is required."
        if not node_id:
            return "Error: node_id is required."
        if not flow_id or not user_id:
            return "Error: no flow_id or user_id in context."

        # ── Look up paused context (flow_run_id, ws_id) ───────────────
        ctx = get_paused_context(flow_task_id)
        if not ctx:
            return (
                f"Error: no paused context found for flow_task_id={flow_task_id}. "
                "The workflow may not be paused or the context expired."
            )
        flow_run_id = ctx["flow_run_id"]
        ws_id = ctx["ws_id"]

        # ── Fetch results from MongoDB ─────────────────────────────────
        try:
            results_data = await self._dao.get_node_results(
                workflow_id=flow_id,
                user_id=user_id,
                node_ids=[node_id],
            )
        except Exception as e:
            return f"Error: failed to fetch node results — {e}"

        node_runs = results_data.get(node_id, [])
        if not node_runs:
            return f"Error: no results found for node {node_id}."

        raw_outputs = node_runs[0].get("outputs", [])
        if not raw_outputs:
            return f"Error: node {node_id} has no outputs."

        # ── Expand splitText segments ──────────────────────────────────
        expanded = _expand_outputs(raw_outputs)

        # ── Select outputs ─────────────────────────────────────────────
        if selected_indices is None:
            # Default: select all (typical for splitText)
            chosen = expanded
        else:
            if any(i < 1 or i > len(expanded) for i in selected_indices):
                return (
                    f"Error: selected_indices out of range "
                    f"(valid: 1–{len(expanded)}, got: {selected_indices})."
                )
            chosen = [expanded[i - 1] for i in selected_indices]

        if not chosen:
            return "Error: no outputs selected."

        # ── Build user_selection ───────────────────────────────────────
        # Frontend normalises splitText → text as the selection key
        output_type = chosen[0].get("type", "text")
        selection_key = "text" if output_type == "splitText" else output_type

        user_selection = {
            selection_key: [{
                "node_id": node_id,
                "outputs": [
                    {
                        "model": item.get("model", ""),
                        # MongoDB stores content as "result", consumer expects "output"
                        "output": item.get("result", "") or item.get("output", ""),
                        "path": item.get("path") or [],
                    }
                    for item in chosen
                ],
            }],
        }

        # ── Submit continue ────────────────────────────────────────────
        event_queue = register(ws_id)

        try:
            await self._engine.submit_continue(
                flow_task_id=flow_task_id,
                flow_run_id=flow_run_id,
                ws_id=ws_id,
                user_id=user_id or "",
                user_selection=user_selection,
            )
        except Exception as e:
            unregister(ws_id)
            return f"Error: failed to continue workflow — {e}"

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
            except (asyncio.CancelledError, GeneratorExit):
                if not _terminal_seen:
                    await self._engine.kill(flow_task_id)
                    logger.info(
                        "ContinueWorkflowTool: stream cancelled, killed workflow. "
                        "flow_task_id={}",
                        flow_task_id,
                    )
                else:
                    logger.debug(
                        "ContinueWorkflowTool: stream closed after terminal event, "
                        "no kill needed. flow_task_id={}",
                        flow_task_id,
                    )
            finally:
                unregister(ws_id)

        from ._workflow_callbacks import build_interpret_event, build_make_sse_event

        return WorkflowExecution(
            flow_task_id=flow_task_id,
            run_id=flow_run_id,
            ws_id=ws_id,
            event_stream=_event_stream(),
            interpret_event=build_interpret_event(flow_task_id, flow_run_id, ws_id),
            make_sse_event=build_make_sse_event(),
        )


def _expand_outputs(outputs: list[dict]) -> list[dict]:
    """Expand splitText results so each segment is a separate entry.

    A splitText node stores all segments in a single result document:
    - ``formatted_output``: ``["seg1", "seg2", ...]``  (preferred)
    - ``output``: JSON-encoded array string as fallback

    Regular (non-split) outputs pass through unchanged.
    """
    expanded: list[dict] = []
    for out in outputs:
        if out.get("type") != "splitText":
            expanded.append(out)
            continue

        segments = out.get("formatted_output")
        if not isinstance(segments, list):
            raw = out.get("result", "") or out.get("output", "")
            try:
                segments = json.loads(raw) if raw and raw.startswith("[") else None
            except (json.JSONDecodeError, TypeError):
                segments = None

        if isinstance(segments, list) and len(segments) > 1:
            for seg in segments:
                expanded.append({
                    **{k: v for k, v in out.items()
                       if k not in ("output", "formatted_output", "result")},
                    "result": seg if isinstance(seg, str) else str(seg),
                })
        else:
            expanded.append(out)
    return expanded
