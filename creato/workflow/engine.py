"""Workflow execution engine — DAG building, validation, submission, and kill.

Pure business logic. All infrastructure dependencies (Redis, MongoDB, Funboost)
are injected via the constructor so this module stays testable and decoupled.
"""

from __future__ import annotations

from datetime import datetime
from time import time
from typing import Any, Callable, List

import networkx as nx
from networkx.readwrite import json_graph
from loguru import logger
from nanoid import generate as nanoid_generate

_ASSEMBLE_NODE_TYPE = "assembleNow"


class WorkflowEngine:
    """Orchestrates workflow DAG building, submission to Consumer, and kill."""

    def __init__(
        self,
        redis_client: Any,
        flow_task_col: Any,
        publish_fn: Callable,
        reply_queue: str,
    ) -> None:
        self._redis = redis_client
        self._flow_task_col = flow_task_col
        self._publish = publish_fn
        self._reply_queue = reply_queue

    async def submit_start(
        self,
        nodes: List[dict],
        edges: List[dict],
        ws_id: str,
        user_id: str,
        start_ids: List[str] | None = None,
        end_ids: List[str] | None = None,
        user_selection: Any = None,
    ) -> tuple[str, str]:
        """Build DAG, persist task, publish to Redis Stream."""
        # 1. Filter non-executable nodes
        nodes, edges = self._filter_non_executable(nodes, edges)

        # 2. Build and validate DAG
        graph = nx.DiGraph()
        graph.add_nodes_from((node["id"], node) for node in nodes)
        graph.add_edges_from((edge["source"], edge["target"], edge) for edge in edges)

        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("There is a cycle in the graph")

        # 3. Serialize DAG (Consumer expects node-link format)
        dag_json = json_graph.node_link_data(graph, edges="edges")

        # 4. Generate IDs
        flow_task_id = nanoid_generate(size=8)
        flow_run_id = nanoid_generate(size=32)

        # 5. Persist to MongoDB
        now = datetime.now()
        await self._flow_task_col.insert_one({
            "user_id": user_id,
            "flow_task_id": flow_task_id,
            "nodes": nodes,
            "edges": edges,
            "status": "running",
            "cost": None,
            "result": None,
            "start_ids": start_ids,
            "end_ids": end_ids,
            "created_at": now,
            "updated_at": now,
        })

        # 6. Publish to Redis Stream via Funboost
        self._publish(
            {
                "flow_task_id": flow_task_id,
                "flow_run_type": "start",
                "flow_run_id": flow_run_id,
                "dag": dag_json,
                "ws_id": ws_id,
                "user_selection": user_selection,
                "start_ids": start_ids,
                "end_ids": end_ids,
                "user_id": user_id,
                "publish_timestamp": time(),
                "reply_queue": self._reply_queue,
            },
            task_id=flow_task_id,
        )

        logger.info(f"Workflow submitted: {flow_task_id=} {flow_run_id=} {ws_id=}")
        return flow_task_id, flow_run_id

    async def submit_continue(
        self,
        flow_task_id: str,
        flow_run_id: str,
        ws_id: str,
        user_id: str,
        user_selection: Any = None,
    ) -> None:
        """Continue a paused workflow (after select mode)."""
        # Verify task exists
        existing = await self._flow_task_col.find_one(
            {"flow_task_id": flow_task_id, "user_id": user_id}
        )
        if not existing:
            raise ValueError(f"Flow task not found: {flow_task_id}")

        self._publish(
            {
                "flow_task_id": flow_task_id,
                "flow_run_type": "continue",
                "flow_run_id": flow_run_id,
                "dag": {},
                "ws_id": ws_id,
                "user_selection": user_selection,
                "start_ids": None,
                "end_ids": None,
                "user_id": user_id,
                "publish_timestamp": time(),
                "reply_queue": self._reply_queue,
            },
            task_id=flow_task_id,
        )

        logger.info(f"Workflow continue submitted: {flow_task_id=} {ws_id=}")

    async def kill(self, flow_task_id: str) -> None:
        """Set Redis kill flag so Consumer stops execution."""
        if not flow_task_id:
            return
        await self._redis.setex(
            f"opencreator:flow_task:kill:{flow_task_id}", 60 * 10, "1"
        )
        logger.info(f"Kill flag set: {flow_task_id=}")

    @staticmethod
    def _filter_non_executable(
        nodes: List[dict], edges: List[dict]
    ) -> tuple[List[dict], List[dict]]:
        """Remove assembleNow nodes and their connected edges."""
        removed_ids = {n["id"] for n in nodes if n.get("type") == _ASSEMBLE_NODE_TYPE}
        if not removed_ids:
            return nodes, edges
        filtered_nodes = [n for n in nodes if n["id"] not in removed_ids]
        filtered_edges = [
            e for e in edges
            if e["source"] not in removed_ids and e["target"] not in removed_ids
        ]
        return filtered_nodes, filtered_edges
