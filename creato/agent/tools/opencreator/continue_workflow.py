"""ContinueWorkflowTool — continue a paused workflow via WorkflowEngine."""

from __future__ import annotations

from typing import Any

from loguru import logger

from creato.agent.request_context import get_request_context
from creato.agent.tools.base import Tool, WorkflowExecution


class ContinueWorkflowTool(Tool):
    """Continue the current paused workflow using request-scoped context."""

    name = "continue_workflow"
    description = (
        "Continue a paused workflow after the user has completed the required "
        "canvas selection. Call this when the workflow previously paused in "
        "select mode and the user now wants to continue."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, workflow_engine: Any = None):
        self._engine = workflow_engine

    async def execute(self, **_: Any) -> str | WorkflowExecution:
        from creato.workflow.event_bridge import register, unregister

        request_context = get_request_context()
        user_id = request_context.get("user_id")
        continue_ctx = request_context.get("continue_workflow")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."

        if not isinstance(continue_ctx, dict):
            return "Error: no continue_workflow context in the current request."

        flow_task_id = continue_ctx.get("flow_task_id")
        flow_run_id = continue_ctx.get("flow_run_id")
        ws_id = continue_ctx.get("ws_id")

        if not isinstance(flow_task_id, str) or not flow_task_id.strip():
            return "Error: continue_workflow.flow_task_id is required."
        if not isinstance(flow_run_id, str) or not flow_run_id.strip():
            return "Error: continue_workflow.flow_run_id is required."
        if not isinstance(ws_id, str) or not ws_id.strip():
            return "Error: continue_workflow.ws_id is required."
        if "user_selection" not in continue_ctx:
            return "Error: continue_workflow.user_selection is required."

        user_selection = continue_ctx.get("user_selection")

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
