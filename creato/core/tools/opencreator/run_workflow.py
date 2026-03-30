"""RunWorkflowTool — execute workflow via WorkflowEngine."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from creato.core.request_context import get_request_context
from creato.core.tools.base import Tool, WorkflowExecution
from creato.core.tools.opencreator.common import _API_BASE


class RunWorkflowTool(Tool):
    """Run the current workflow on the canvas. Submits the DAG to Consumer for execution
    and returns a WorkflowExecution stream that the agent loop consumes to emit
    real-time workflow.* SSE events to the frontend."""

    name = "run_workflow"
    description = (
        "Run the current workflow on the canvas. By default executes all connected nodes. "
        "If node_ids is provided, only those specific nodes (and their upstream dependencies) "
        "will be executed — this is single-node or selected-nodes run mode. "
        "When the user @mentions a specific node or says 'run this node', extract the node ID "
        "from the context and pass it in node_ids."
    )
    parameters = {
        "type": "object",
        "properties": {
            "node_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional. List of node IDs to run. When provided, only these nodes "
                    "and their upstream ancestors will execute. When omitted, the entire "
                    "workflow runs. Node IDs look like 'textGenerator-1711234567890-abc123'."
                ),
            },
            "user_selection": {
                "type": "object",
                "description": (
                    "Optional. Required for single-node runs when predecessor nodes have "
                    "historical results. Keys are pin types ('text', 'image', 'video', 'audio'), "
                    "values are arrays of {node_id, outputs: [{model, output, path}]}. "
                    "Use get_workflow_results first to see available results, then build this "
                    "from the predecessor outputs. If a predecessor has multiple results, "
                    "ask the user which one to use before calling this tool."
                ),
            },
        },
        "required": [],
    }

    def __init__(self, api_base: str = "", workflow_engine: Any = None):
        self.api_base = api_base.strip() or _API_BASE
        self._engine = workflow_engine

    async def execute(self, node_ids: list[str] | None = None, user_selection: dict | None = None, **_: Any) -> str | WorkflowExecution:
        from nanoid import generate as nanoid_generate
        from creato.workflow.event_bridge import register, unregister

        request_context = get_request_context()
        flow_id = request_context.get("flow_id")
        auth_token = request_context.get("auth_token")
        user_id = request_context.get("user_id")

        if not self._engine:
            return "Error: workflow engine is not configured on this server."

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session."

        if not isinstance(auth_token, str) or not auth_token.strip():
            return "Error: no authenticated user token in context."

        # 1. Fetch current workflow from Publisher API (reuse GetWorkflowTool logic)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.api_base.rstrip('/')}/api/v2/flow/project/{flow_id.strip()}",
                    headers={"Authorization": f"Bearer {auth_token.strip()}"},
                )
        except Exception as e:
            return f"Error: failed to fetch workflow — {e}"

        if not resp.is_success:
            return f"Error: API returned {resp.status_code}"

        data = resp.json().get("data", {})
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        if not nodes:
            return "Error: workflow has no nodes."

        # 2. Generate ws_id and register event queue
        ws_id = nanoid_generate(size=9)
        event_queue = register(ws_id)

        # 3. Submit to Consumer via WorkflowEngine
        start_ids = node_ids if node_ids else None
        end_ids = node_ids if node_ids else None
        try:
            flow_task_id, flow_run_id = await self._engine.submit_start(
                nodes=nodes,
                edges=edges,
                ws_id=ws_id,
                user_id=user_id or "",
                start_ids=start_ids,
                end_ids=end_ids,
                user_selection=user_selection,
            )
        except Exception as e:
            unregister(ws_id)
            return f"Error: failed to submit workflow — {e}"

        # 4. Return WorkflowExecution — loop.py will consume the event stream
        async def _event_stream():
            _terminal_seen = False  # Track whether workflow reached a natural end
            try:
                import asyncio
                while True:
                    event = await asyncio.wait_for(event_queue.get(), timeout=480)  # 8 minutes
                    et = event.get("event_type")
                    # Mark terminal BEFORE yield — GeneratorExit arrives at the yield point,
                    # so the flag must already be set by then.
                    if et in ("finish_flow", "flow_killed", "node_time_out"):
                        _terminal_seen = True
                    if et == "node_status" and event.get("status") in ("select", "failed"):
                        _terminal_seen = True
                    yield event
                    if _terminal_seen:
                        break
            except asyncio.TimeoutError:
                # Don't kill — let Consumer finish in background.
                # Results will be saved to assets automatically.
                logger.info(f"RunWorkflowTool: 8min timeout, disconnecting SSE (not killing). {flow_task_id=}")
            except (asyncio.CancelledError, GeneratorExit):
                if not _terminal_seen:
                    await self._engine.kill(flow_task_id)
                    logger.info(f"RunWorkflowTool: stream cancelled, killed workflow. {flow_task_id=}")
                else:
                    logger.debug(f"RunWorkflowTool: stream closed after terminal event, no kill needed. {flow_task_id=}")
            finally:
                unregister(ws_id)

        return WorkflowExecution(
            flow_task_id=flow_task_id,
            run_id=flow_run_id,
            ws_id=ws_id,
            event_stream=_event_stream(),
        )
