"""GetWorkflowTool — fetch current workflow from Publisher API."""

from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger

from creato.agent.request_context import get_request_context
from creato.agent.tools.base import Tool, ToolResult
from creato.agent.tools.opencreator.common import _API_BASE


class GetWorkflowTool(Tool):
    """Fetch the current OpenCreator workflow in the active canvas session."""

    name = "get_workflow"
    description = (
        "Fetch the complete current workflow from the active canvas session, including all nodes, "
        "edges, and their current positions. Use this before editing an existing workflow so "
        "unchanged nodes and layout can be preserved."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, api_base: str = ""):
        self.api_base = api_base.strip() or _API_BASE

    async def execute(self, **_: Any) -> str:
        request_context = get_request_context()
        flow_id = request_context.get("flow_id")
        auth_token = request_context.get("auth_token")

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session."
        flow_id = flow_id.strip()

        if not isinstance(auth_token, str) or not auth_token.strip():
            return "Error: no authenticated user token in context."
        auth_token = auth_token.strip()

        headers = {
            "Authorization": f"Bearer {auth_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.api_base.rstrip('/')}/api/v2/flow/project/{flow_id}",
                    headers=headers,
                )
        except Exception as e:
            logger.error("get_workflow HTTP error: {}", e)
            return f"Error: HTTP request failed — {e}"

        if resp.status_code == 404:
            return "Error: workflow not found."

        if not resp.is_success:
            return f"Error: API returned {resp.status_code} — {resp.text[:500]}"

        try:
            payload = resp.json()
        except Exception:
            return f"Error: Could not parse API response — {resp.text[:300]}"

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return "Error: workflow response missing `data` object."

        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return "Error: workflow response missing valid `nodes` or `edges`."

        project_name = None
        details = data.get("details")
        if isinstance(details, dict):
            project_name = details.get("project_name")

        result = {
            "flow_id": data.get("flow_id", flow_id),
            "project_name": project_name,
            "nodes": nodes,
            "edges": edges,
        }

        return ToolResult(
            content=json.dumps(result, ensure_ascii=False, indent=2),
            events=[{
                "name": "get_workflow",
                "data": {
                    "flow_id": result["flow_id"],
                    "project_name": project_name,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                },
            }],
        )
