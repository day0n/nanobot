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
        "You MUST call get_workflow_results first to verify the available outputs, "
        "then build user_selection from the user's choice. "
        "The flow_task_id, flow_run_id, and ws_id come from the paused workflow context "
        "returned by run_workflow."
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
            "user_selection": {
                "type": "object",
                "description": (
                    "The user's chosen outputs, keyed by pin type. "
                    "Build this from get_workflow_results output. Example:\n"
                    '{\n'
                    '  "text": [{\n'
                    '    "node_id": "textGenerator-abc123",\n'
                    '    "outputs": [{"model": "openai/gpt-4o-mini", "output": "the full text content", "path": ""}]\n'
                    '  }]\n'
                    '}\n'
                    "Keys are pin types: 'text', 'image', 'video', 'audio'. "
                    "For text nodes, 'output' is the text content. "
                    "For media nodes, 'output' is the CDN URL. "
                    "'path' can be empty string. "
                    "Include only the output(s) the user chose, not all of them."
                ),
            },
        },
        "required": ["flow_task_id", "flow_run_id", "ws_id", "user_selection"],
    }

    def __init__(self, workflow_engine: Any = None):
        self._engine = workflow_engine

    async def execute(
        self,
        flow_task_id: str = "",
        flow_run_id: str = "",
        ws_id: str = "",
        user_selection: dict | None = None,
        **_: Any,
    ) -> str | WorkflowExecution:
        from creato.workflow.event_bridge import register, unregister

        request_context = get_request_context()
        user_id = request_context.get("user_id")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."

        if not flow_task_id or not flow_run_id or not ws_id:
            return "Error: flow_task_id, flow_run_id, and ws_id are all required."
        if user_selection is None:
            return "Error: user_selection is required."

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
