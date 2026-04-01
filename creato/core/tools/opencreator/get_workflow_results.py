"""GetWorkflowResultsTool — fetch latest execution results for all nodes."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from creato.core.request_context import get_request_context
from creato.core.tools.base import Tool


class GetWorkflowResultsTool(Tool):
    """Fetch the latest execution results for all nodes in the current workflow.

    Returns each node's most recent outputs (text, images, videos, audio).
    Use this before single-node runs to understand what data is available
    from predecessor nodes, or to check the results of a previous execution."""

    name = "get_workflow_results"
    description = (
        "Fetch the latest execution results for all nodes in the current workflow. "
        "Returns each node's most recent outputs (CDN URLs for media, text content for text). "
        "Use this before running a single node to check what predecessor results are available, "
        "or to review the output of a previous workflow run."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, workflow_dao: Any = None):
        self._dao = workflow_dao

    async def execute(self, **_: Any) -> str:
        request_context = get_request_context()
        flow_id = request_context.get("flow_id")
        user_id = request_context.get("user_id")

        if not isinstance(flow_id, str) or not flow_id.strip():
            return "Error: no flow_id in context. This tool requires an active canvas session."
        if not isinstance(user_id, str) or not user_id.strip():
            return "Error: no authenticated user in context."

        flow_id = flow_id.strip()
        user_id = user_id.strip()

        if not self._dao:
            return "Error: workflow data access is not configured."

        # 1. Get workflow to know all node IDs
        try:
            data = await self._dao.get_workflow(flow_id, user_id)
        except Exception as e:
            return f"Error: failed to fetch workflow — {e}"

        if not data:
            return "Error: workflow not found."

        nodes = data.get("nodes", [])
        if not nodes:
            return "Error: workflow has no nodes."

        node_ids = [n["id"] for n in nodes if isinstance(n, dict) and "id" in n]

        # 2. Fetch latest results for all nodes
        try:
            results_data = await self._dao.get_node_results(flow_id, user_id, node_ids)
        except Exception as e:
            return f"Error: failed to fetch results — {e}"

        # 3. Build a concise summary for LLM
        summary = {}
        for node_id, runs in results_data.items():
            if not runs:
                summary[node_id] = {"has_results": False}
                continue

            latest_run = runs[0] if isinstance(runs, list) and runs else {}
            outputs = latest_run.get("outputs", [])
            run_id = latest_run.get("run_id", "")

            # Expand outputs: splitText results store multiple segments in one
            # document (formatted_output list or JSON-encoded output string).
            # Flatten them so each segment gets its own index for selection.
            expanded = _expand_outputs(outputs)

            output_summary = []
            for idx, out in enumerate(expanded, 1):
                entry = {
                    "index": idx,
                    "type": out.get("type", "unknown"),
                    "model": out.get("model", ""),
                    "status": out.get("status", ""),
                }
                # For text / splitText, include content preview;
                # for media, include CDN URL
                # MongoDB stores content in "result", not "output"
                content = out.get("result", "") or out.get("output", "")
                if out.get("type") in ("text", "splitText"):
                    entry["content_preview"] = (
                        content[:200] + "..." if len(content) > 200 else content
                    )
                else:
                    entry["output_url"] = content
                output_summary.append(entry)

            summary[node_id] = {
                "has_results": True,
                "run_id": run_id,
                "output_count": len(expanded),
                "outputs": output_summary,
            }

        # Find node labels for readability
        node_labels = {}
        for n in nodes:
            if isinstance(n, dict):
                nid = n.get("id", "")
                label = n.get("data", {}).get("label", nid)
                node_labels[nid] = label

        result = {
            "workflow_id": flow_id,
            "node_results": summary,
            "node_labels": node_labels,
        }

        return json.dumps(result, ensure_ascii=False, indent=2)


def _expand_outputs(outputs: list[dict]) -> list[dict]:
    """Expand splitText results so each segment is a separate entry.

    A splitText node stores all segments in a single result document:
    - ``formatted_output``: ``["seg1", "seg2", ...]``  (preferred)
    - ``output``: JSON-encoded array string as fallback

    Regular (non-split) outputs pass through unchanged.
    """
    expanded: list[dict] = []
    for out in outputs:
        if out.get("type") != "splitText":
            expanded.append(out)
            continue

        # Try formatted_output first, then parse result/output JSON string
        segments = out.get("formatted_output")
        if not isinstance(segments, list):
            raw = out.get("result", "") or out.get("output", "")
            try:
                segments = json.loads(raw) if raw and raw.startswith("[") else None
            except (json.JSONDecodeError, TypeError):
                segments = None

        if isinstance(segments, list) and len(segments) > 1:
            # Expand: one entry per segment, inherit model/status/type
            for seg in segments:
                expanded.append({
                    **{k: v for k, v in out.items()
                       if k not in ("output", "formatted_output", "result")},
                    "result": seg if isinstance(seg, str) else str(seg),
                })
        else:
            # Single segment or unparseable — keep as-is
            expanded.append(out)
    return expanded
