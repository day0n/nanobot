"""EditWorkflowTool — edit workflow via WorkflowDAO."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from creato.core.request_context import get_request_context
from creato.core.tools.base import Tool, ToolResult
from creato.schemas.tools import ToolEventPayload
from creato.core.tools.opencreator.common import (
    _normalize_nodes, _normalize_edges, _find_position_issues,
    _merge_with_db_content,
)


class EditWorkflowTool(Tool):
    """Edit an OpenCreator workflow in the current canvas via WorkflowDAO."""

    name = "edit_workflow"
    description = (
        "Update the workflow (nodes + edges) in the current canvas session. "
        "IMPORTANT: This is a FULL REPLACEMENT — you must provide ALL nodes and edges, not just the changed ones. "
        "Always call get_workflow FIRST to see the current canvas state, then modify the returned nodes/edges "
        "and pass the complete list here. Skipping get_workflow will lose existing nodes and layout. "
        "Content fields (prompts, images, audio, video) and heavy config fields are automatically "
        "preserved from the database — you do NOT need to provide them unless you want to change them. "
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
        workflow_dao: Any = None,
        editor_base: str = "",
    ):
        self._dao = workflow_dao
        self.editor_base = editor_base.rstrip("/") if editor_base else ""

    async def execute(
        self,
        *,
        nodes: list,
        edges: list,
        **_: Any,
    ) -> str | ToolResult:
        request_context = get_request_context()
        user_id = request_context.get("user_id")
        flow_id = request_context.get("flow_id")

        if not isinstance(user_id, str) or not user_id.strip():
            return "Error: no authenticated user context. This tool requires a canvas session with a logged-in user."
        user_id = user_id.strip()

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session with an existing workflow."
        flow_id = flow_id.strip()

        if not self._dao:
            return "Error: workflow data access is not configured."

        # Fetch current DB nodes to preserve content fields stripped by get_workflow
        try:
            db_data = await self._dao.get_workflow(flow_id, user_id)
        except Exception:
            db_data = None
        db_nodes = db_data.get("nodes", []) if db_data else []
        nodes = _merge_with_db_content(nodes, db_nodes)

        normalized_nodes, id_map, node_warnings = _normalize_nodes(nodes)
        if not normalized_nodes and nodes:
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

        try:
            await self._dao.update_workflow(flow_id, user_id, normalized_nodes, normalized_edges)
        except ValueError as exc:
            return f"Error: validation failed — {exc}"
        except Exception as e:
            logger.error("edit_workflow error: {}", e)
            return f"Error: failed to update workflow — {e}"

        message = (
            f"Workflow updated successfully!\n"
            f"  flow_id: {flow_id}\n"
            f"  Nodes: {len(normalized_nodes)}, Edges: {len(normalized_edges)}"
        )
        if self.editor_base:
            message += f"\n  Editor URL: {self.editor_base}/canvas/{flow_id}"
        if preflight_warnings:
            preview = "\n".join(f"  - {w}" for w in preflight_warnings[:8])
            if len(preflight_warnings) > 8:
                preview += f"\n  - ... and {len(preflight_warnings) - 8} more"
            message += f"\nPreflight adjustments:\n{preview}"
        return ToolResult(
            content=message,
            events=[ToolEventPayload(name="workflow_update", data={"flow_id": flow_id})],
        )
