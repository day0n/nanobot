"""OpenCreator platform tools."""

import json
from typing import Any

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool

_API_BASE = "https://api-develop.opencreator.io"
_INTERNAL_AUTH = "ODljMGNjYzgtNjk5Ni00NGYzLWJlNDMtOWQ5NzIyYWNlOGVj"
_EDITOR_BASE = "https://editor-dev.opencreator.io"


class CreateWorkflowTool(Tool):
    """Create an OpenCreator workflow via the Internal API."""

    name = "create_workflow"
    description = (
        "Save a fully-constructed OpenCreator workflow (nodes + edges) to a user's account "
        "via the Internal API. Call this AFTER you have built the complete nodes and edges arrays. "
        "Returns the flow_id and an editor URL the user can open."
    )
    parameters = {
        "type": "object",
        "properties": {
            "user_email": {
                "type": "string",
                "description": "Email address of the user who will own the workflow.",
            },
            "workflow_name": {
                "type": "string",
                "description": "Display name for the workflow project.",
            },
            "nodes": {
                "type": "array",
                "description": (
                    "Array of node objects. Each node must have: "
                    "id ({nodeType}-{13-digit-timestamp}-{4-hex}), type, position ({x, y}), "
                    "selected (false), data ({label, description, themeColor, selectedModels, "
                    "inputText, imageBase64, inputAudio, inputVideo, status, isSelectMode, isNodeConnected})."
                ),
                "items": {"type": "object"},
            },
            "edges": {
                "type": "array",
                "description": (
                    "Array of edge objects. Each edge must have: "
                    "id (edge-{sourceId}-{targetId}), source, target, sourceHandle, targetHandle, "
                    "type ('customEdge'), animated (true). Pin types must match."
                ),
                "items": {"type": "object"},
            },
        },
        "required": ["user_email", "workflow_name", "nodes", "edges"],
    }

    async def execute(self, *, user_email: str, workflow_name: str, nodes: list, edges: list, **_: Any) -> str:
        payload = {
            "user_email": user_email,
            "project_name": workflow_name,
            "nodes": nodes,
            "edges": edges,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_API_BASE}/api/internal/workflow/create-by-email",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": _INTERNAL_AUTH,
                    },
                    content=json.dumps(payload, ensure_ascii=False),
                )
        except Exception as e:
            logger.error("create_workflow HTTP error: {}", e)
            return f"Error: HTTP request failed — {e}"

        if resp.status_code == 404:
            return f"Error: User not found for email '{user_email}'. Please check the email address."

        if not resp.is_success:
            return f"Error: API returned {resp.status_code} — {resp.text[:500]}"

        try:
            data = resp.json()
        except Exception:
            return f"Error: Could not parse API response — {resp.text[:300]}"

        flow_id = data.get("flow_id") or data.get("id") or data.get("data", {}).get("flow_id")
        if not flow_id:
            return f"Workflow created but could not extract flow_id. Raw response: {resp.text[:300]}"

        editor_url = f"{_EDITOR_BASE}/convas/{flow_id}"
        return (
            f"Workflow created successfully!\n"
            f"  flow_id: {flow_id}\n"
            f"  Editor URL: {editor_url}\n"
            f"  Nodes: {len(nodes)}, Edges: {len(edges)}"
        )
