"""Shared callback builders for RunWorkflowTool and ContinueWorkflowTool.

These callbacks are injected into WorkflowExecution so that the executor
stays free of workflow-specific business logic.
"""

from __future__ import annotations

from typing import Any, Callable

from creato.core.events import WORKFLOW_EVENT_MAP, AgentEvent, workflow_paused
from creato.workflow.event_bridge import store_paused_context


def build_interpret_event(
    flow_task_id: str,
    run_id: str,
    ws_id: str,
) -> Callable[[dict[str, Any]], str | None]:
    """Build an ``interpret_event`` callback for WorkflowExecution.

    Handles abnormal terminations (select / failed / timeout).
    Normal completion (finish_flow / flow_killed) is NOT handled here —
    the ``_event_stream`` generator breaks on those events, and the
    executor falls back to ``WorkflowExecution.default_result``.
    """

    def interpret_event(raw_event: dict[str, Any]) -> str | None:
        et = raw_event.get("event_type")

        # select → pause, return control to LLM
        if et == "node_status" and raw_event.get("status") == "select":
            node_id = raw_event.get("node_id", "unknown")
            store_paused_context(flow_task_id, {
                "flow_run_id": run_id,
                "ws_id": ws_id,
                "node_id": node_id,
            })
            return (
                f"Workflow paused: node {node_id} entered select mode — "
                f"it produced multiple outputs and the downstream node needs "
                f"the user to choose which result to use.\n"
                f"Paused workflow context: flow_task_id={flow_task_id}, "
                f"flow_run_id={run_id}, ws_id={ws_id}\n"
                f"Next step: call get_workflow_results to see the available "
                f"outputs, then present the choices to the user."
            )

        # node failed
        if et == "node_status" and raw_event.get("status") == "failed":
            err = raw_event.get("error_msg", "Node execution failed")
            return f"Workflow failed: {err}"

        # node timed out
        if et == "node_time_out":
            node_id = raw_event.get("node_id", "unknown")
            return f"Workflow failed: node {node_id} timed out"

        return None  # keep consuming

    return interpret_event


def build_make_sse_event() -> Callable[[dict[str, Any]], AgentEvent | None]:
    """Build ``make_sse_event`` callback that converts Consumer events to AgentEvents."""

    def make_sse_event(raw_event: dict[str, Any]) -> AgentEvent | None:
        et = raw_event.get("event_type")

        # select node → emit workflow.paused SSE
        if et == "node_status" and raw_event.get("status") == "select":
            return workflow_paused(raw_event)

        # all other mapped events
        constructor = WORKFLOW_EVENT_MAP.get(et)
        return constructor(raw_event) if constructor else None

    return make_sse_event
