"""ContinueWorkflowTool — continue a paused workflow via WorkflowEngine."""

from __future__ import annotations

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
        "then pass the node_id and the 1-based index of the chosen output."
    )
    parameters = {
        "type": "object",
        "properties": {
            "flow_task_id": {
                "type": "string",
                "description": "The flow_task_id from the paused workflow context.",
            },
            "flow_run_id": {
                "type": "string",
                "description": "The flow_run_id from the paused workflow context.",
            },
            "ws_id": {
                "type": "string",
                "description": "The ws_id from the paused workflow context.",
            },
            "node_id": {
                "type": "string",
                "description": "The node_id of the paused select node.",
            },
            "selected_index": {
                "type": "integer",
                "description": (
                    "1-based index of the output to use. "
                    "For example, if get_workflow_results shows 2 outputs "
                    "and the user picks the first one, pass 1."
                ),
            },
        },
        "required": ["flow_task_id", "flow_run_id", "ws_id", "node_id", "selected_index"],
    }

    def __init__(self, workflow_engine: Any = None, workflow_dao: Any = None):
        self._engine = workflow_engine
        self._dao = workflow_dao

    async def execute(
        self,
        flow_task_id: str = "",
        flow_run_id: str = "",
        ws_id: str = "",
        node_id: str = "",
        selected_index: int = 0,
        **_: Any,
    ) -> str | WorkflowExecution:
        from creato.workflow.event_bridge import register, unregister

        request_context = get_request_context()
        user_id = request_context.get("user_id")
        flow_id = request_context.get("flow_id")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."
        if not self._dao:
            return "Error: workflow data access is not configured."

        if not flow_task_id or not flow_run_id or not ws_id:
            return "Error: flow_task_id, flow_run_id, and ws_id are all required."
        if not node_id:
            return "Error: node_id is required."
        if selected_index < 1:
            return "Error: selected_index must be >= 1."

        # ── Build user_selection from MongoDB results ──────────────────
        if not flow_id or not user_id:
            return "Error: no flow_id or user_id in context."

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

        outputs = node_runs[0].get("outputs", [])
        if not outputs:
            return f"Error: node {node_id} has no outputs."

        if selected_index > len(outputs):
            return (
                f"Error: selected_index {selected_index} out of range "
                f"(1–{len(outputs)})."
            )

        selected = outputs[selected_index - 1]
        output_type = selected.get("type", "text")

        user_selection = {
            output_type: [{
                "node_id": node_id,
                "outputs": [{
                    "model": selected.get("model", ""),
                    "output": selected.get("output", ""),
                    "path": selected.get("path", ""),
                }],
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
                    if et in ("finish_flow", "flow_killed", "node_time_out"):
                        _terminal_seen = True
                    if et == "node_status" and event.get("status") in ("select", "failed"):
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

        return WorkflowExecution(
            flow_task_id=flow_task_id,
            run_id=flow_run_id,
            ws_id=ws_id,
            event_stream=_event_stream(),
        )
