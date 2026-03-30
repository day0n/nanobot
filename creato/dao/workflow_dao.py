"""Workflow data access layer — direct MongoDB operations.

Replaces Publisher HTTP calls (GET /api/v2/flow/project, POST /api/internal/workflow/edit,
POST /api/v3/result/all_batch_fetch) with direct database access.

All infrastructure dependencies are injected via the constructor.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

import networkx as nx
from loguru import logger

_ASSEMBLE_NODE_TYPE = "assembleNow"
_MAX_VERSION_COUNT = 5
_S3_KEY_PATTERN = re.compile(r"^https?://[^/]+/(.+)$")


class WorkflowDAO:
    """Workflow data access — reads/writes flow, flow_details, flow_version, results."""

    def __init__(
        self,
        flow_col: Any,
        flow_details_col: Any,
        flow_version_col: Any,
        results_col: Any,
        cloudfront_domain: str = "",
    ) -> None:
        self._flow_col = flow_col
        self._flow_details_col = flow_details_col
        self._flow_version_col = flow_version_col
        self._results_col = results_col
        self._cloudfront_domain = cloudfront_domain.strip()

    # ── get_workflow ─────────────────────────────────────────────────

    async def get_workflow(self, flow_id: str, user_id: str) -> dict | None:
        """Fetch workflow structure (nodes, edges) and details (project_name).

        Replaces: GET /api/v2/flow/project/{flow_id}
        """
        flow_doc, details_doc = await asyncio.gather(
            self._flow_col.find_one(
                {"flow_id": flow_id, "user_id": user_id}, {"_id": 0}
            ),
            self._flow_details_col.find_one(
                {"flow_id": flow_id}, {"_id": 0}
            ),
        )
        if not flow_doc:
            return None

        result: dict[str, Any] = {
            "flow_id": flow_doc.get("flow_id", flow_id),
            "nodes": flow_doc.get("nodes", []),
            "edges": flow_doc.get("edges", []),
        }
        if details_doc:
            result["details"] = {
                "project_name": details_doc.get("project_name"),
            }
        return result

    # ── update_workflow ──────────────────────────────────────────────

    async def update_workflow(
        self,
        flow_id: str,
        user_id: str,
        nodes: list,
        edges: list,
    ) -> None:
        """Full-replace workflow nodes and edges, with version history.

        Replaces: POST /api/internal/workflow/edit
        """
        edges = self._filter_invalid_edges(nodes, edges)
        self._validate_dag(nodes, edges)
        await self._save_version(flow_id, user_id)
        nodes = self._clean_assemble_nodes(nodes)

        update_doc = {"nodes": nodes, "edges": edges, "updated_at": datetime.now()}
        await self._flow_col.update_one(
            {"flow_id": flow_id, "user_id": user_id},
            {"$set": update_doc},
        )
        logger.info(f"WorkflowDAO.update_workflow: {flow_id=}")

    # ── get_node_results ─────────────────────────────────────────────

    async def get_node_results(
        self,
        workflow_id: str,
        user_id: str,
        node_ids: list[str],
    ) -> dict[str, list]:
        """Batch fetch latest execution results for nodes.

        Replaces: POST /api/v3/result/all_batch_fetch
        """
        pipeline = [
            {"$match": {
                "workflow_id": workflow_id,
                "user_id": user_id,
                "node_id": {"$in": node_ids},
            }},
            {"$sort": {"sort": 1, "created_at": 1}},
            {"$group": {
                "_id": {"node_id": "$node_id", "run_id": "$run_id"},
                "allResults": {"$push": "$$ROOT"},
                "maxCreatedAt": {"$max": "$created_at"},
            }},
            {"$sort": {"maxCreatedAt": -1}},
            {"$project": {
                "node_id": "$_id.node_id",
                "run_id": "$_id.run_id",
                "results": "$allResults",
                "_id": 0,
            }},
        ]
        aggregated = await self._results_col.aggregate(pipeline).to_list(length=None)

        # Group by node_id
        grouped: dict[str, list] = defaultdict(list)
        for item in aggregated:
            grouped[item["node_id"]].append({
                "run_id": item["run_id"],
                "node_id": item["node_id"],
                "outputs": item["results"],
            })

        # V3 behavior: only keep latest run per node
        result: dict[str, list] = {}
        for node_id in node_ids:
            runs = grouped.get(node_id, [])
            result[node_id] = [runs[0]] if runs else []

        if self._cloudfront_domain:
            self._convert_cdn_urls(result)

        return result

    # ── Internal helpers ─────────────────────────────────────────────

    @staticmethod
    def _filter_invalid_edges(nodes: list, edges: list) -> list:
        """Remove edges referencing non-existent nodes."""
        node_ids = {
            n.get("id")
            for n in (nodes or [])
            if isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"].strip()
        }
        if not edges:
            return []
        return [
            e for e in edges
            if isinstance(e, dict)
            and isinstance(e.get("source"), str) and e["source"].strip()
            and isinstance(e.get("target"), str) and e["target"].strip()
            and e["source"] in node_ids
            and e["target"] in node_ids
        ]

    @staticmethod
    def _validate_dag(nodes: list, edges: list) -> None:
        """Build networkx DiGraph and verify it's acyclic."""
        if not nodes:
            return
        node_ids = set()
        for node in nodes:
            nid = node.get("id", "")
            if nid in node_ids:
                raise ValueError(f"duplicate node id: {nid}")
            node_ids.add(nid)

        graph = nx.DiGraph()
        graph.add_nodes_from(node_ids)
        graph.add_edges_from(
            (e["source"], e["target"]) for e in edges
            if isinstance(e, dict) and e.get("source") and e.get("target")
        )
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("workflow must be a DAG; cycles are not allowed")

    async def _save_version(self, flow_id: str, user_id: str) -> None:
        """Save current workflow as a version snapshot (max 5 kept)."""
        try:
            old_flow = await self._flow_col.find_one(
                {"flow_id": flow_id, "user_id": user_id}, {"_id": 0}
            )
            if not old_flow or not old_flow.get("nodes"):
                return

            await self._flow_version_col.insert_one({
                "flow_id": flow_id,
                "user_id": user_id,
                "nodes": old_flow.get("nodes", []),
                "edges": old_flow.get("edges", []),
                "created_at": datetime.now(),
            })

            versions = await self._flow_version_col.find(
                {"flow_id": flow_id}, {"_id": 1}
            ).sort("created_at", -1).to_list(None)

            if len(versions) > _MAX_VERSION_COUNT:
                old_ids = [v["_id"] for v in versions[_MAX_VERSION_COUNT:]]
                await self._flow_version_col.delete_many({"_id": {"$in": old_ids}})
                logger.debug(f"WorkflowDAO: deleted {len(old_ids)} old versions for {flow_id=}")
        except Exception as e:
            logger.error(f"WorkflowDAO._save_version failed: {e}")

    @staticmethod
    def _clean_assemble_nodes(nodes: list) -> list:
        """Remove cover fields from assembleNow nodes."""
        for node in (nodes or []):
            if node.get("type") != _ASSEMBLE_NODE_TYPE:
                continue
            assemble = node.get("data", {}).get("assemble")
            if not assemble:
                continue
            for track in assemble.get("tracks", []):
                for clip in track.get("clips", []):
                    source_info = clip.get("source_info", {})
                    source_info.pop("cover", None)
        return nodes

    def _convert_cdn_urls(self, results: dict) -> None:
        """Convert S3 paths to CloudFront CDN URLs in-place."""
        domain = self._cloudfront_domain
        for node_results in results.values():
            for run in node_results:
                for output in run.get("outputs", []):
                    if output.get("type") in ("image", "video", "audio"):
                        raw = output.get("output", "")
                        if raw:
                            key = self._extract_s3_key(raw)
                            if key:
                                output["output"] = f"https://{domain}/{key}"
                    metadata = output.get("metadata")
                    if not isinstance(metadata, dict):
                        continue
                    if "output_s3_object_key" in metadata:
                        metadata["output_cdn_url"] = f"https://{domain}/{metadata['output_s3_object_key']}"
                    if "output_s3_thumbnail_object_key" in metadata:
                        metadata["output_cdn_thumbnail_url"] = f"https://{domain}/{metadata['output_s3_thumbnail_object_key']}"

    @staticmethod
    def _extract_s3_key(path: str) -> str | None:
        """Extract object key from S3 URL or CDN URL."""
        if not path:
            return None
        match = _S3_KEY_PATTERN.match(path)
        return match.group(1) if match else path
