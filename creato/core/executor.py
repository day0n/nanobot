"""AgentExecutor — pure LLM/tool iteration engine.

This module contains NO product-level concerns (Sentry, PostHog, session
management).  All observability and side-effects are injected via
ExecutorHooks.  Both AgentLoop and SubagentTool use this as their backend.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

from loguru import logger

from creato.core.prompt.builder import add_assistant_message, add_tool_result
from creato.core.tools.base import ToolResult, WorkflowExecution
from creato.core.tools.registry import ToolRegistry
from creato.schemas.executor import ExecutorResult
from creato.schemas.messages import MessageList
from creato.providers.base import LLMProvider, LLMResponse

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>")


def _strip_think(text: str | None) -> str | None:
    """Remove ``<think>…</think>`` blocks that some models embed in content."""
    if not text:
        return None
    return _THINK_RE.sub("", text).strip() or None


# ---------------------------------------------------------------------------
# Hooks — optional callbacks for observability / side-effects
# ---------------------------------------------------------------------------

@dataclass
class ExecutorHooks:
    """Optional callbacks invoked at key points. None = silently skipped."""

    on_step_start: Callable[[int], Awaitable[None]] | None = None
    on_step_end: Callable[[int], Awaitable[None]] | None = None
    on_llm_start: Callable[[str, MessageList], Awaitable[None]] | None = None
    on_llm_end: Callable[[dict[str, int]], Awaitable[None]] | None = None
    on_text_delta: Callable[[str], Awaitable[None]] | None = None
    on_tool_start: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None = None
    on_tool_end: Callable[[str, str, int, str | None, dict[str, Any], str], Awaitable[None]] | None = None
    on_tool_event: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None
    on_workflow_start: Callable[[dict[str, Any]], Awaitable[None]] | None = None
    on_workflow_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None
    on_workflow_paused: Callable[[dict[str, Any]], Awaitable[None]] | None = None


# ---------------------------------------------------------------------------
# AgentExecutor
# ---------------------------------------------------------------------------

class AgentExecutor:
    """Pure LLM / tool iteration engine.

    No Sentry, no PostHog, no session management — those are injected
    through :class:`ExecutorHooks`.

    Parameters
    ----------
    provider:
        The LLM backend (OpenAI, Vertex, etc.).
    model:
        Model identifier forwarded to the provider.
    tools:
        Registry of available tools.
    max_iterations:
        Safety cap on the number of LLM round-trips.
    tool_result_max_chars:
        Truncation limit for tool output fed back to the LLM.
    hooks:
        Optional observability / side-effect callbacks.
    """

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        tools: ToolRegistry,
        max_iterations: int = 40,
        tool_result_max_chars: int = 16_000,
        hooks: ExecutorHooks | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.tools = tools
        self.max_iterations = max_iterations
        self.tool_result_max_chars = tool_result_max_chars
        self.hooks = hooks or ExecutorHooks()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, messages: MessageList) -> ExecutorResult:
        """Execute the LLM / tool loop until the model stops or we hit the cap.

        Parameters
        ----------
        messages:
            The full message list (system + history + current user message).

        Returns
        -------
        ExecutorResult
            Accumulated content, tool usage, updated messages, and timings.
        """
        iteration = 0
        final_content: str | None = None
        tools_used: list[str] = []
        tool_timings: dict[str, dict] = {}

        while iteration < self.max_iterations:
            iteration += 1

            if self.hooks.on_step_start:
                await self.hooks.on_step_start(iteration)

            tool_defs = self.tools.get_definitions()

            if self.hooks.on_llm_start:
                await self.hooks.on_llm_start(self.model, messages)

            # --- stream LLM response ---
            accumulated_content = ""
            all_tool_calls: list = []
            finish_reason = "stop"
            thinking_blocks: list[dict] | None = None
            reasoning_content: str | None = None
            usage: dict[str, int] = {}

            try:
                stream = self.provider.chat_stream_with_retry(
                    messages=messages,
                    tools=tool_defs,
                    model=self.model,
                )
                async for chunk in stream:
                    if chunk.text_delta:
                        accumulated_content += chunk.text_delta
                        if self.hooks.on_text_delta:
                            await self.hooks.on_text_delta(chunk.text_delta)
                    if chunk.completed_tool_calls:
                        all_tool_calls.extend(chunk.completed_tool_calls)
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason
                    if chunk.thinking_blocks:
                        thinking_blocks = chunk.thinking_blocks
                    if chunk.usage:
                        usage = chunk.usage
                    if chunk.error_content:
                        accumulated_content = chunk.error_content
                        finish_reason = "error"
            except asyncio.CancelledError:
                await stream.aclose()
                raise

            if self.hooks.on_llm_end:
                await self.hooks.on_llm_end(usage)

            # Reconstruct LLMResponse from accumulated chunks
            response = LLMResponse(
                content=accumulated_content or None,
                tool_calls=all_tool_calls,
                finish_reason=finish_reason,
                usage=usage,
                reasoning_content=reasoning_content,
                thinking_blocks=thinking_blocks,
            )

            # --- process tool calls ---
            if response.has_tool_calls:
                tool_call_dicts = [
                    tc.to_openai_tool_call() for tc in response.tool_calls
                ]
                messages = add_assistant_message(
                    messages,
                    response.content,
                    tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])

                    if self.hooks.on_tool_start:
                        await self.hooks.on_tool_start(
                            tool_call.name, tool_call.id, tool_call.arguments,
                        )

                    started_at = datetime.now()
                    error_msg: str | None = None
                    result_obj: str | ToolResult | WorkflowExecution

                    try:
                        result_obj = await self.tools.execute(
                            tool_call.name, tool_call.arguments,
                        )
                    except Exception as exc:
                        error_msg = str(exc)
                        result_obj = f"Error: {exc}"

                    completed_at = datetime.now()
                    duration_ms = int(
                        (completed_at - started_at).total_seconds() * 1000
                    )

                    # Normalize result to a plain string
                    result_str = await self._handle_tool_result(result_obj)

                    # WorkflowExecution streams can take a long time — recalculate
                    _is_wf = isinstance(result_obj, WorkflowExecution) or (
                        hasattr(result_obj, "event_stream")
                        and not isinstance(result_obj, (str, ToolResult))
                    )
                    if _is_wf:
                        completed_at = datetime.now()
                        duration_ms = int(
                            (completed_at - started_at).total_seconds() * 1000
                        )

                    if self.hooks.on_tool_end:
                        await self.hooks.on_tool_end(
                            tool_call.name, tool_call.id, duration_ms, error_msg,
                            tool_call.arguments, result_str,
                        )

                    tool_timings[tool_call.id] = {
                        "name": tool_call.name,
                        "args": tool_call.arguments,
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "duration_ms": duration_ms,
                        "error": error_msg,
                        "raw_output": result_str,
                    }

                    # Truncate oversized tool output before feeding back to LLM
                    if isinstance(result_str, str) and len(result_str) > self.tool_result_max_chars:
                        result_str = (
                            result_str[: self.tool_result_max_chars]
                            + f"\n\n[Truncated — {len(result_str)} chars total]"
                        )

                    messages = add_tool_result(
                        messages, tool_call.id, tool_call.name, result_str,
                    )

            else:
                # No tool calls — final assistant turn
                clean = _strip_think(response.content)

                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = (
                        clean or "Sorry, I encountered an error calling the AI model."
                    )
                    break

                messages = add_assistant_message(
                    messages,
                    clean,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

            if self.hooks.on_step_end:
                await self.hooks.on_step_end(iteration)

        # Safety: max iterations reached without a final answer
        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations "
                f"({self.max_iterations}) without completing the task. "
                "You can try breaking the task into smaller steps."
            )

        return ExecutorResult(
            content=final_content,
            tools_used=tools_used,
            messages=messages,
            tool_timings=tool_timings,
            iterations=iteration,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _handle_tool_result(
        self,
        result_obj: str | ToolResult | WorkflowExecution | Any,
    ) -> str:
        """Normalize a tool return value to a plain string.

        - ``WorkflowExecution`` (or duck-typed with ``event_stream``):
          consume the async event stream via :meth:`_consume_workflow_stream`.
        - ``ToolResult``: emit sub-events via the hook, return ``.content``.
        - ``str``: pass through.
        """
        # WorkflowExecution (or duck-typed equivalent)
        _is_wf = isinstance(result_obj, WorkflowExecution) or (
            hasattr(result_obj, "event_stream")
            and not isinstance(result_obj, (str, ToolResult))
        )
        if _is_wf:
            return await self._consume_workflow_stream(result_obj)

        if isinstance(result_obj, ToolResult):
            for evt in result_obj.events:
                if self.hooks.on_tool_event:
                    await self.hooks.on_tool_event(
                        evt.name,
                        evt.data,
                    )
            return result_obj.content

        return result_obj if isinstance(result_obj, str) else str(result_obj)

    async def _consume_workflow_stream(
        self,
        wf_exec: WorkflowExecution | Any,
    ) -> str:
        """Consume a WorkflowExecution event stream and return a summary string.

        Emits ``on_workflow_start`` and ``on_workflow_event`` hooks for each
        event so the product layer can forward them to the client.
        """
        if self.hooks.on_workflow_start:
            await self.hooks.on_workflow_start({
                "flow_task_id": wf_exec.flow_task_id,
                "run_id": wf_exec.run_id,
                "ws_id": wf_exec.ws_id,
            })

        result_str = "Workflow completed successfully"
        got_terminal = False

        try:
            # Track the consumer's real run_id from start_flow event —
            # it differs from wf_exec.run_id which is generated by the agent.
            _consumer_run_id = ""

            async for raw_event in wf_exec.event_stream:
                if self.hooks.on_workflow_event:
                    await self.hooks.on_workflow_event(raw_event)

                et = raw_event.get("event_type")

                # Capture consumer's actual run_id from start_flow event
                if et == "start_flow" and raw_event.get("run_id"):
                    _consumer_run_id = raw_event["run_id"]

                # select → pause, return control to LLM
                if et == "node_status" and raw_event.get("status") == "select":
                    node_id = raw_event.get("node_id", "unknown")
                    # Store paused context so continue_workflow can look it up.
                    # Use consumer's run_id (from start_flow event), NOT the
                    # agent-generated wf_exec.run_id — they are different values.
                    from creato.workflow.event_bridge import store_paused_context
                    store_paused_context(wf_exec.flow_task_id, {
                        "flow_run_id": _consumer_run_id or wf_exec.run_id,
                        "ws_id": wf_exec.ws_id,
                        "node_id": node_id,
                    })
                    if self.hooks.on_workflow_paused:
                        await self.hooks.on_workflow_paused({
                            "flow_task_id": wf_exec.flow_task_id,
                            "flow_run_id": wf_exec.run_id,
                            "ws_id": wf_exec.ws_id,
                            "node_id": node_id,
                        })
                    result_str = (
                        f"Workflow paused: node {node_id} entered select mode — "
                        f"it produced multiple outputs and the downstream node needs "
                        f"the user to choose which result to use.\n"
                        f"Paused workflow context: flow_task_id={wf_exec.flow_task_id}, "
                        f"flow_run_id={wf_exec.run_id}, ws_id={wf_exec.ws_id}\n"
                        f"Next step: call get_workflow_results to see the available "
                        f"outputs, then present the choices to the user."
                    )
                    got_terminal = True
                    break

                # node failed
                if et == "node_status" and raw_event.get("status") == "failed":
                    err = raw_event.get("error_msg", "Node execution failed")
                    result_str = f"Workflow failed: {err}"
                    got_terminal = True
                    break

                # node timed out
                if et == "node_time_out":
                    node_id = raw_event.get("node_id", "unknown")
                    result_str = f"Workflow failed: node {node_id} timed out"
                    got_terminal = True
                    break

                # normal completion or kill
                if et in ("finish_flow", "flow_killed"):
                    got_terminal = True
                    break

        except Exception as stream_err:
            logger.error("Workflow event stream error: {}", stream_err)
            result_str = f"Error consuming workflow events: {stream_err}"
            got_terminal = True

        # Stream ended without a terminal event — Consumer continues in background
        if not got_terminal:
            result_str = (
                "The workflow is still generating and may take a bit longer. "
                "Results will be saved automatically to your assets — nothing "
                "will be lost. You can leave or refresh the page, and check "
                "the assets page later. If generation fails, you will not be "
                "charged."
            )

        return result_str
