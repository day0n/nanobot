"""GetWorkflowTool — fetch current workflow via WorkflowDAO."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from creato.core.request_context import get_request_context
from creato.core.tools.base import Tool, ToolResult
from creato.schemas.tools import ToolEventPayload
from creato.core.tools.opencreator.common import _strip_node_for_agent


class GetWorkflowTool(Tool):
    """Fetch the current OpenCreator workflow in the active canvas session."""

    name = "get_workflow"
    description = (
        "Fetch the current workflow structure from the active canvas session. "
        "Returns a lightweight view: node topology (id, type, position, connections), "
        "model selection, and config — but NOT the actual content inside nodes "
        "(prompts, images, audio, video are replaced with presence indicators like '[has content]'). "
        "Use this before editing an existing workflow so unchanged nodes and layout can be preserved."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, workflow_dao: Any = None):
        self._dao = workflow_dao

    async def execute(self, **_: Any) -> str | ToolResult:
        request_context = get_request_context()
        flow_id = request_context.get("flow_id")
        user_id = request_context.get("user_id")

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session."
        flow_id = flow_id.strip()

        if not isinstance(user_id, str) or not user_id.strip():
            return "Error: no authenticated user in context."
        user_id = user_id.strip()

        if not self._dao:
            return "Error: workflow data access is not configured."

        try:
            data = await self._dao.get_workflow(flow_id, user_id)
        except Exception as e:
            logger.error("get_workflow error: {}", e)
            return f"Error: failed to fetch workflow — {e}"

        if not data:
            return "Error: workflow not found."

        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return "Error: workflow missing valid `nodes` or `edges`."

        project_name = None
        details = data.get("details")
        if isinstance(details, dict):
            project_name = details.get("project_name")

        result = {
            "flow_id": data.get("flow_id", flow_id),
            "project_name": project_name,
            "nodes": [_strip_node_for_agent(n) for n in nodes],
            "edges": edges,
        }

        return ToolResult(
            content=json.dumps(result, ensure_ascii=False, indent=2),
            events=[ToolEventPayload(
                name="get_workflow",
                data={
                    "flow_id": result["flow_id"],
                    "project_name": project_name,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                },
            )],
        )
