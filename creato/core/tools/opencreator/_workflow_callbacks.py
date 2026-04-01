"""Shared callback builders for RunWorkflowTool and ContinueWorkflowTool.

These callbacks are injected into WorkflowExecution so that the executor
stays free of workflow-specific business logic.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from creato.core.events import (
    WORKFLOW_EVENT_MAP,
    AgentEvent,
    workflow_node_failed,
    workflow_paused,
    workflow_select_card,
    workflow_selection_resolved,
)
from creato.workflow.event_bridge import (
    store_paused_context,
    update_snapshot_consumer_run_id,
    update_snapshot_node_outputs,
    update_snapshot_paused_node,
)


# ---------------------------------------------------------------------------
# Node type extraction from node_id
# ---------------------------------------------------------------------------

_NODE_TYPE_LABELS: dict[str, str] = {
    "textGenerator": "Text Generation",
    "textToImage": "Text to Image",
    "textToVideo": "Text to Video",
    "imageToVideo": "Image to Video",
    "tts": "Text to Speech",
    "musicGeneration": "Music Generation",
    "splitText": "Text Splitter",
    "assembleNow": "Assemble",
    "stickyNote": "Sticky Note",
    "imageToImage": "Image to Image",
    "textToMusic": "Text to Music",
    "lipsync": "Lip Sync",
}

# node_id pattern: "{nodeType}-{timestamp}-{random}"
_NODE_ID_PREFIX_RE = re.compile(r"^([a-zA-Z]+)")


def _extract_node_type(node_id: str) -> str:
    """Extract a human-readable node type from a node_id like 'textToImage-171...-abc'."""
    m = _NODE_ID_PREFIX_RE.match(node_id)
    if not m:
        return node_id
    prefix = m.group(1)
    return _NODE_TYPE_LABELS.get(prefix, prefix)


# ---------------------------------------------------------------------------
# Failure analysis
# ---------------------------------------------------------------------------

_ERROR_ANALYSIS: list[tuple[Callable[[str, str], bool], str, str]] = [
    # (matcher, category, suggestion)
    (
        lambda code, msg: code == "3003" or "InsufficientCredits" in msg,
        "insufficient_credits",
        "Not enough credits to run this model. Please top up your balance or switch to a more affordable model.",
    ),
    (
        lambda code, msg: "BlockedDueToSensitiveContent" in msg or "sensitive" in msg.lower(),
        "content_blocked",
        "Content was flagged by the moderation system. Please revise your prompt and try again.",
    ),
    (
        lambda code, msg: "PromptTooLong" in msg or "prompt too long" in msg.lower(),
        "prompt_too_long",
        "The input is too long for this model. Please shorten your prompt or split it into smaller parts.",
    ),
    (
        lambda code, msg: "timeout" in msg.lower() or "timed out" in msg.lower(),
        "timeout",
        "The model API timed out. Please try again — if it persists, consider switching to a different model.",
    ),
    (
        lambda code, msg: "NoValidResponsesFromModel" in msg or "no valid response" in msg.lower(),
        "no_valid_response",
        "The model returned no valid output. Please try again or switch to a different model.",
    ),
    (
        lambda code, msg: "InvalidParameter" in msg or "invalid parameter" in msg.lower(),
        "invalid_parameter",
        "Invalid parameter for this model. Please check the node settings.",
    ),
]


def _analyze_failure(error_msg: str, error_code: str) -> dict[str, str]:
    """Return ``{"error_category": ..., "suggestion": ...}`` for a failure."""
    for matcher, category, suggestion in _ERROR_ANALYSIS:
        if matcher(error_code, error_msg):
            return {"error_category": category, "suggestion": suggestion}
    return {
        "error_category": "unknown",
        "suggestion": error_msg or "An unexpected error occurred. Please try again.",
    }


# ---------------------------------------------------------------------------
# Callback builders
# ----------------------------------------------------------------------

def build_interpret_event(
    flow_task_id: str,
    run_id: str,
    ws_id: str,
    stream_state: dict[str, Any] | None = None,
    initial_paused_nodes: set[str] | None = None,
) -> Callable[[dict[str, Any]], str | None]:
    """Build an ``interpret_event`` callback for WorkflowExecution.

    Tracks running_count to detect when all parallel branches have settled.
    SELECT no longer terminates the stream — it accumulates paused nodes.
    The stream only breaks when running_count == 0 AND there are unresolved
    paused nodes.

    ``initial_paused_nodes`` allows inheriting paused state from a previous
    turn (e.g. when continue_workflow is called after all-settled).

    Also captures node_outputs into the RunSnapshot for continue.
    """
    failed_nodes: list[dict[str, Any]] = []
    running_nodes: set[str] = set()  # track by node_id to prevent double-count
    paused_nodes: set[str] = set(initial_paused_nodes) if initial_paused_nodes else set()

    def _check_all_settled() -> str | None:
        """Return pause message if all branches have settled, else None."""
        if not running_nodes and paused_nodes:
            if stream_state is not None:
                stream_state["select_paused"] = True
            return _build_all_settled_message(
                flow_task_id, run_id, ws_id, paused_nodes, failed_nodes,
            )
        return None

    def interpret_event(raw_event: dict[str, Any]) -> str | None:
        et = raw_event.get("event_type")

        # ── Capture consumer's real run_id from start_flow event ──────
        if et == "start_flow" and raw_event.get("run_id"):
            update_snapshot_consumer_run_id(flow_task_id, raw_event["run_id"])

        # ── node_status events ────────────────────────────────────────
        if et == "node_status":
            status = raw_event.get("status")
            node_id = raw_event.get("node_id", "unknown")

            if status == "running":
                running_nodes.add(node_id)

            elif status == "success":
                running_nodes.discard(node_id)
                _capture_node_outputs(flow_task_id, raw_event)

            elif status == "select":
                running_nodes.discard(node_id)
                _capture_node_outputs(flow_task_id, raw_event)
                update_snapshot_paused_node(flow_task_id, node_id)
                paused_nodes.add(node_id)
                # Legacy compat
                store_paused_context(flow_task_id, {
                    "flow_run_id": run_id,
                    "ws_id": ws_id,
                    "node_id": node_id,
                })
                # DO NOT return — keep consuming. make_sse_event emits the card.

            elif status == "failed":
                running_nodes.discard(node_id)
                failed_nodes.append({
                    "node_id": node_id,
                    "error_msg": raw_event.get("error_msg", ""),
                    "error_code": str(raw_event.get("error_code", "")),
                })

            return _check_all_settled()

        # ── node timed out ────────────────────────────────────────────
        if et == "node_time_out":
            running_nodes.discard(raw_event.get("node_id", "unknown"))
            failed_nodes.append({
                "node_id": raw_event.get("node_id", "unknown"),
                "error_msg": "Node execution timed out",
                "error_code": "TIMEOUT",
            })
            return _check_all_settled()

        # ── Synthetic: selection resolved via HTTP POST ────────────────
        if et == "_selection_resolved":
            paused_nodes.discard(raw_event.get("node_id"))
            return None

        # ── workflow ended ────────────────────────────────────────────
        if et in ("finish_flow", "flow_killed"):
            if failed_nodes:
                return _build_failure_summary(failed_nodes)
            return None  # no failures → fall through to default_result

        return None  # keep consuming

    return interpret_event


def _capture_node_outputs(flow_task_id: str, raw_event: dict[str, Any]) -> None:
    """Extract node_outputs from a node_status event and store in snapshot."""
    node_id = raw_event.get("node_id")
    node_outputs = raw_event.get("node_outputs")
    if node_id and node_outputs and isinstance(node_outputs, dict):
        update_snapshot_node_outputs(flow_task_id, node_id, node_outputs)


def _build_failure_summary(failed_nodes: list[dict[str, Any]]) -> str:
    """Build a human-readable failure summary for the LLM tool result."""
    parts = [
        f"Workflow completed with {len(failed_nodes)} failed node(s):\n"
    ]
    for i, node in enumerate(failed_nodes, 1):
        node_id = node["node_id"]
        node_type = _extract_node_type(node_id)
        analysis = _analyze_failure(node["error_msg"], node["error_code"])
        parts.append(
            f"  {i}. [{node_type}] {node_id}\n"
            f"     Error: {node['error_msg'] or 'unknown'}\n"
            f"     Suggestion: {analysis['suggestion']}"
        )
    parts.append(
        "\nOther nodes in the workflow completed successfully. "
        "Their results have been saved."
    )
    return "\n".join(parts)


def _build_all_settled_message(
    flow_task_id: str,
    run_id: str,
    ws_id: str,
    paused_nodes: set[str],
    failed_nodes: list[dict[str, Any]],
) -> str:
    """Build pause message when all branches have settled (no running nodes)."""
    node_list = ", ".join(sorted(paused_nodes))
    msg = (
        f"Workflow paused: {len(paused_nodes)} node(s) in select mode — {node_list}.\n"
        f"Each produced multiple outputs and the downstream nodes need "
        f"the user to choose which result to use.\n"
        f"Paused workflow context: flow_task_id={flow_task_id}, "
        f"flow_run_id={run_id}, ws_id={ws_id}\n"
        f"Next step: call get_workflow_results to see the available "
        f"outputs, then present the choices to the user."
    )
    if failed_nodes:
        msg += (
            f"\n\nNote: {len(failed_nodes)} node(s) failed during this run:\n"
            + _build_failure_summary(failed_nodes)
        )
    return msg


def build_make_sse_event() -> Callable[[dict[str, Any]], AgentEvent | None]:
    """Build ``make_sse_event`` callback that converts Consumer events to AgentEvents."""

    def make_sse_event(raw_event: dict[str, Any]) -> AgentEvent | None:
        et = raw_event.get("event_type")

        # select node → emit workflow.select_card SSE (does NOT break stream)
        if et == "node_status" and raw_event.get("status") == "select":
            node_id = raw_event.get("node_id", "")
            card_data = {
                **raw_event,
                "card_info": {
                    "node_id": node_id,
                    "node_type": _extract_node_type(node_id),
                    "explanation": (
                        f"{_extract_node_type(node_id)} node produced multiple outputs. "
                        f"Choose which to use."
                    ),
                },
            }
            return workflow_select_card(card_data)

        # selection resolved via HTTP POST → notify frontend
        if et == "_selection_resolved":
            return workflow_selection_resolved(raw_event)

        # failed node → emit workflow.node_failed SSE with analysis
        if et == "node_status" and raw_event.get("status") == "failed":
            return _build_node_failed_sse(raw_event)

        # node timeout → also emit workflow.node_failed (workflow continues)
        if et == "node_time_out":
            return _build_node_failed_sse({
                **raw_event,
                "error_msg": raw_event.get("error_msg", "Node execution timed out"),
                "error_code": raw_event.get("error_code", "TIMEOUT"),
            })

        # all other mapped events
        constructor = WORKFLOW_EVENT_MAP.get(et)
        return constructor(raw_event) if constructor else None

    return make_sse_event


def _build_node_failed_sse(raw_event: dict[str, Any]) -> AgentEvent:
    """Build a ``workflow.node_failed`` SSE event with failure analysis."""
    node_id = raw_event.get("node_id", "unknown")
    error_msg = raw_event.get("error_msg", "")
    error_code = str(raw_event.get("error_code", ""))

    analysis = _analyze_failure(error_msg, error_code)

    enriched = {
        **raw_event,
        "failure_analysis": {
            "node_type": _extract_node_type(node_id),
            "error_category": analysis["error_category"],
            "suggestion": analysis["suggestion"],
        },
    }
    return workflow_node_failed(enriched)
