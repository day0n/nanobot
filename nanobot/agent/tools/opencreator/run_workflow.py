"""RunWorkflowTool — execute workflow via WorkflowEngine."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from nanobot.agent.request_context import get_request_context
from nanobot.agent.tools.base import Tool, WorkflowExecution
from nanobot.agent.tools.opencreator.common import _API_BASE


class RunWorkflowTool(Tool):
    """Run the current workflow on the canvas. Submits the DAG to Consumer for execution
    and returns a WorkflowExecution stream that the agent loop consumes to emit
    real-time workflow.* SSE events to the frontend."""

    name = "run_workflow"
    description = (
        "Run the current workflow on the canvas. This will execute all connected nodes "
        "in the workflow, calling AI models and producing outputs. Use this when the user "
        "asks to run, execute, or start their workflow."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, api_base: str = "", workflow_engine: Any = None):
        self.api_base = api_base.strip() or _API_BASE
        self._engine = workflow_engine

    async def execute(self, **_: Any) -> str | WorkflowExecution:
        from nanoid import generate as nanoid_generate
        from nanobot.workflow.event_bridge import register, unregister

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
        try:
            flow_task_id = await self._engine.submit_start(
                nodes=nodes,
                edges=edges,
                ws_id=ws_id,
                user_id=user_id or "",
            )
        except Exception as e:
            unregister(ws_id)
            return f"Error: failed to submit workflow — {e}"

        # 4. Return WorkflowExecution — loop.py will consume the event stream
        async def _event_stream():
            try:
                import asyncio
                while True:
                    event = await asyncio.wait_for(event_queue.get(), timeout=300)
                    yield event
                    et = event.get("event_type")
                    if et == "node_status" and event.get("status") == "select":
                        break
                    if et in ("finish_flow", "flow_killed"):
                        break
            except asyncio.TimeoutError:
                logger.warning(f"RunWorkflowTool: timeout waiting for events, killing {flow_task_id}")
                await self._engine.kill(flow_task_id)
            except (asyncio.CancelledError, GeneratorExit):
                await self._engine.kill(flow_task_id)
            finally:
                unregister(ws_id)

        return WorkflowExecution(
            flow_task_id=flow_task_id,
            run_id="",
            ws_id=ws_id,
            event_stream=_event_stream(),
        )
