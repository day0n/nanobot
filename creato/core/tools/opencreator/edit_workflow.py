"""EditWorkflowTool — edit workflow via Internal API."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
from loguru import logger

from creato.core.request_context import get_request_context
from creato.core.tools.base import Tool, ToolResult
from creato.core.tools.opencreator.common import (
    _API_BASE, _EDITOR_BASE,
    _normalize_nodes, _normalize_edges, _find_position_issues,
)


class EditWorkflowTool(Tool):
    """Edit an OpenCreator workflow in the current canvas via the Internal API."""

    name = "edit_workflow"
    description = (
        "Update the workflow (nodes + edges) in the current canvas session. "
        "IMPORTANT: This is a FULL REPLACEMENT — you must provide ALL nodes and edges, not just the changed ones. "
        "Always call get_workflow FIRST to see the current canvas state, then modify the returned nodes/edges "
        "and pass the complete list here. Skipping get_workflow will lose existing nodes and layout. "
        "The tool performs preflight normalization/validation to keep payloads frontend-compatible "
        "(node defaults, edge handle compatibility, dangling-edge cleanup). "
        "Each node MUST include a position with x/y coordinates for correct canvas layout."
    )
    parameters = {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "description": (
                    "Array of node objects. Each node MUST include type, id, position ({x, y}), and data. "
                    "Position is required for correct canvas layout — do NOT omit it. "
                    "The tool will auto-fill missing default fields in data and sanitize invalid values."
                ),
                "items": {"type": "object"},
            },
            "edges": {
                "type": "array",
                "description": (
                    "Array of edge objects with source/target/sourceHandle/targetHandle. "
                    "The tool will remove dangling edges, infer missing handles, and enforce compatible handle types."
                ),
                "items": {"type": "object"},
            },
        },
        "required": ["nodes", "edges"],
    }

    def __init__(
        self,
        api_base: str = "",
        internal_api_key: str = "",
        editor_base: str = _EDITOR_BASE,
    ):
        self.api_base = api_base.strip() or _API_BASE
        self.internal_api_key = internal_api_key.strip()
        self.editor_base = editor_base.rstrip("/") or _EDITOR_BASE

    def _auth_header(self) -> str:
        if not self.internal_api_key:
            raise ValueError("internal_api_key is not configured. Set CREATO_API__INTERNAL_API_KEY in .env.local.")
        return base64.b64encode(self.internal_api_key.encode("utf-8")).decode("ascii")

    async def execute(
        self,
        *,
        nodes: list,
        edges: list,
        **_: Any,
    ) -> str:
        request_context = get_request_context()
        user_id = request_context.get("user_id")
        flow_id = request_context.get("flow_id")

        if not isinstance(user_id, str) or not user_id.strip():
            return "Error: no authenticated user context. This tool requires a canvas session with a logged-in user."
        user_id = user_id.strip()

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session with an existing workflow."
        flow_id = flow_id.strip()

        normalized_nodes, id_map, node_warnings = _normalize_nodes(nodes)
        if not normalized_nodes and nodes:
            # Caller provided nodes but all were invalid — report the errors.
            warning_text = "\n".join(f"- {w}" for w in node_warnings[:20]) if node_warnings else ""
            return (
                "Error: no valid nodes left after preflight normalization.\n"
                "Please provide at least one valid node.\n"
                f"{warning_text}"
            )

        nodes_by_id = {n["id"]: n for n in normalized_nodes}
        normalized_edges, edge_warnings = _normalize_edges(edges, nodes_by_id, id_map)
        position_warnings = _find_position_issues(normalized_nodes)
        preflight_warnings = node_warnings + edge_warnings + position_warnings

        payload = {
            "user_id": user_id,
            "flow_id": flow_id,
            "nodes": normalized_nodes,
            "edges": normalized_edges,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": self._auth_header(),
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.api_base.rstrip('/')}/api/internal/workflow/edit",
                    headers=headers,
                    content=json.dumps(payload, ensure_ascii=False),
                )
        except Exception as e:
            logger.error("edit_workflow HTTP error: {}", e)
            return f"Error: HTTP request failed — {e}"

        if resp.status_code == 404:
            return "Error: workflow or user not found."

        if not resp.is_success:
            return f"Error: API returned {resp.status_code} — {resp.text[:500]}"

        try:
            data = resp.json()
        except Exception:
            return f"Error: Could not parse API response — {resp.text[:300]}"

        result_flow_id = data.get("flow_id") or data.get("data", {}).get("flow_id") or flow_id
        editor_url = f"{self.editor_base}/canvas/{result_flow_id}"

        message = (
            f"Workflow updated successfully!\n"
            f"  flow_id: {result_flow_id}\n"
            f"  Editor URL: {editor_url}\n"
            f"  Nodes: {len(normalized_nodes)}, Edges: {len(normalized_edges)}"
        )
        if preflight_warnings:
            preview = "\n".join(f"  - {w}" for w in preflight_warnings[:8])
            if len(preflight_warnings) > 8:
                preview += f"\n  - ... and {len(preflight_warnings) - 8} more"
            message += f"\nPreflight adjustments:\n{preview}"
        return ToolResult(
            content=message,
            events=[{"name": "workflow_update", "data": {"flow_id": result_flow_id}}],
        )
