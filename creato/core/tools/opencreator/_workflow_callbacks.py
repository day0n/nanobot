"""Shared callback builders for RunWorkflowTool and ContinueWorkflowTool.

These callbacks are injected into WorkflowExecution so that the executor
stays free of workflow-specific business logic.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from creato.core.events import (
    WORKFLOW_EVENT_MAP,
    AgentEvent,
    workflow_node_failed,
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
    "scriptSplit": "Text Splitter",
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


def _extract_node_type_raw(node_id: str) -> str:
    """Extract the raw node type prefix (e.g. 'splitText') from a node_id."""
    m = _NODE_ID_PREFIX_RE.match(node_id)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Failure analysis
# ---------------------------------------------------------------------------

_ERROR_ANALYSIS: list[tuple[Callable[[str, str], bool], str, str]] = [
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
# Select card helpers
# ---------------------------------------------------------------------------

def _count_outputs(node_outputs: dict[str, Any]) -> int:
    """Count total output items across all IO types in node_outputs."""
    total = 0
    for io_data in node_outputs.values():
        if isinstance(io_data, dict):
            outputs = io_data.get("outputs", [])
            if isinstance(outputs, list):
                total += len(outputs)
    return total


def _extract_model_names(node_outputs: dict[str, Any]) -> list[str]:
    """Extract model names from node_outputs."""
    models: list[str] = []
    for io_data in node_outputs.values():
        if isinstance(io_data, dict):
            for item in io_data.get("outputs", []):
                if isinstance(item, dict):
                    model = item.get("model", "")
                    if model and model not in models:
                        models.append(model)
    return models


def _build_select_card_info(
    flow_task_id: str,
    run_id: str,
    node_id: str,
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    """Build enriched card_info for workflow.select_card SSE event."""
    node_type_raw = _extract_node_type_raw(node_id)
    node_type_label = _extract_node_type(node_id)
    node_outputs = raw_event.get("node_outputs", {})
    option_count = _count_outputs(node_outputs)
    model_names = _extract_model_names(node_outputs)
    is_split = node_type_raw in ("splitText", "scriptSplit")

    if is_split:
        selection_mode = "multi"
        hint = f"Text was split into {option_count} segments. Select which segments to pass downstream."
        recommended_action = "Review segments and select all or specific ones"
    else:
        selection_mode = "multi"
        if model_names:
            models_str = ", ".join(model_names)
            hint = f"This node ran {option_count} model(s) ({models_str}). Compare the outputs and select the ones you want to keep."
        else:
            hint = f"This node produced {option_count} outputs. Compare and select the ones you want to keep."
        recommended_action = "Compare outputs and select one or more"

    return {
        "flow_task_id": flow_task_id,
        "run_id": run_id,
        "node_id": node_id,
        "node_type": node_type_label,
        "option_count": option_count,
        "selection_mode": selection_mode,
        "hint": hint,
        "recommended_action": recommended_action,
    }


# ---------------------------------------------------------------------------
# Callback builders
# ---------------------------------------------------------------------------

def build_interpret_event(
    flow_task_id: str,
    run_id: str,
    ws_id: str,
    stream_state: dict[str, Any] | None = None,
    initial_paused_nodes: set[str] | None = None,
) -> Callable[[dict[str, Any]], str | None]:
    """Build an ``interpret_event`` callback for WorkflowExecution.

    SSE stays open until finish_flow/flow_killed. SELECT never terminates
    the stream — it only captures data and emits a card event via make_sse_event.
    User selections come in via HTTP POST as synthetic _selection_resolved events.

    Also captures node_outputs into the RunSnapshot for continue.
    """
    failed_nodes: list[dict[str, Any]] = []
    running_nodes: set[str] = set()
    paused_nodes: set[str] = set(initial_paused_nodes) if initial_paused_nodes else set()

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
                store_paused_context(flow_task_id, {
                    "flow_run_id": run_id,
                    "ws_id": ws_id,
                    "node_id": node_id,
                })

            elif status == "failed":
                running_nodes.discard(node_id)
                failed_nodes.append({
                    "node_id": node_id,
                    "error_msg": raw_event.get("error_msg", ""),
                    "error_code": str(raw_event.get("error_code", "")),
                })

            return None  # never break on node_status

        # ── node timed out ────────────────────────────────────────────
        if et == "node_time_out":
            running_nodes.discard(raw_event.get("node_id", "unknown"))
            failed_nodes.append({
                "node_id": raw_event.get("node_id", "unknown"),
                "error_msg": "Node execution timed out",
                "error_code": "TIMEOUT",
            })
            return None

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


def build_make_sse_event(
    flow_task_id: str = "",
    run_id: str = "",
) -> Callable[[dict[str, Any]], AgentEvent | None]:
    """Build ``make_sse_event`` callback that converts Consumer events to AgentEvents.

    ``flow_task_id`` and ``run_id`` are injected into workflow.select_card
    events so the frontend has full context to submit selections via HTTP POST.
    """

    def make_sse_event(raw_event: dict[str, Any]) -> AgentEvent | None:
        et = raw_event.get("event_type")

        # select node → emit workflow.select_card with enriched card_info
        if et == "node_status" and raw_event.get("status") == "select":
            node_id = raw_event.get("node_id", "")
            event_run_id = raw_event.get("run_id", run_id)
            card_info = _build_select_card_info(
                flow_task_id, run_id, node_id, raw_event,
            )
            # Inject run_id into each node_outputs entry — frontend's
            # isNodeOutputs type guard requires it.
            patched_outputs = {}
            raw_outputs = raw_event.get("node_outputs", {})
            for io_type, io_data in raw_outputs.items():
                if isinstance(io_data, dict) and "run_id" not in io_data:
                    patched_outputs[io_type] = {**io_data, "run_id": event_run_id}
                else:
                    patched_outputs[io_type] = io_data
            card_data = {
                **raw_event,
                "flow_task_id": flow_task_id,
                "node_outputs": patched_outputs,
                "card_info": card_info,
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
