"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.events import (
    AgentEvent,
    WORKFLOW_EVENT_MAP,
    message_delta,
    step_completed,
    step_started,
    tool_completed,
    tool_event,
    tool_failed,
    tool_started,
    workflow_started,
)
from nanobot.agent.request_context import reset_request_context, set_request_context
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.base import ToolResult, WorkflowExecution
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.opencreator import EditWorkflowTool, GetWorkflowTool, RunWorkflowTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanobot.config.schema import ApiServerConfig, ChannelsConfig, ExecToolConfig, WebSearchConfig
    from nanobot.cron.service import CronService


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history and skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 16_000

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        context_window_tokens: int = 65_536,
        web_search_config: WebSearchConfig | None = None,
        web_proxy: str | None = None,
        api_config: ApiServerConfig | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        summary_model: str | None = None,
        summary_api_key: str | None = None,
    ):
        from nanobot.config.schema import ApiServerConfig, ExecToolConfig, WebSearchConfig

        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self._summary_model = summary_model
        self._summary_api_key = summary_api_key
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.api_config = api_config or ApiServerConfig()
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace

        self.context = ContextBuilder(workspace)
        if session_manager is None:
            raise ValueError("session_manager is required (must not be None)")
        self.sessions = session_manager
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            web_search_config=self.web_search_config,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._processing_lock = asyncio.Lock()
        self._pending_traces: list[dict] = []  # tool traces accumulated during _save_turn
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        extra_read = [BUILTIN_SKILLS_DIR] if allowed_dir else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir, extra_allowed_dirs=extra_read))
        # Disabled for chatbot-only rollout: do not expose workspace mutation tools.
        # for cls in (WriteFileTool, EditFileTool, ListDirTool):
        #     self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        # Disabled for chatbot-only rollout: do not expose shell execution.
        # self.tools.register(ExecTool(
        #     working_dir=str(self.workspace),
        #     timeout=self.exec_config.timeout,
        #     restrict_to_workspace=self.restrict_to_workspace,
        #     path_append=self.exec_config.path_append,
        # ))
        self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        # Disabled for chatbot-only rollout: replies return through the normal outbound path.
        # self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        # Disabled for chatbot-only rollout: scheduled actions are out of scope.
        # if self.cron_service:
        #     self.tools.register(CronTool(self.cron_service))
        self.tools.register(GetWorkflowTool(api_base=self.api_config.internal_api_base))
        self.tools.register(EditWorkflowTool(
            api_base=self.api_config.internal_api_base,
            internal_api_key=self.api_config.internal_api_key,
            editor_base=self.api_config.editor_base,
        ))

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        # Disabled for the restricted chatbot rollout: do not register dynamic MCP tools.
        return

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    tool.set_context(channel, chat_id, *([message_id] if name == "message" else [])) # type: ignore

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict], dict[str, dict]]:
        """Run the agent iteration loop.

        Returns:
            (final_content, tools_used, messages, tool_timings)
            tool_timings maps tool_call_id -> {name, args, started_at, completed_at, duration_ms, error}
        """
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        tool_timings: dict[str, dict] = {}

        while iteration < self.max_iterations:
            iteration += 1
            if on_progress:
                await on_progress(step_started(iteration))

            tool_defs = self.tools.get_definitions()

            # --- Stream LLM response ---
            accumulated_content = ""
            all_tool_calls: list = []
            finish_reason = "stop"
            thinking_blocks = None
            reasoning_content = None
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
                        if on_progress:
                            await on_progress(message_delta(chunk.text_delta))
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

            # Reconstruct LLMResponse from accumulated chunks
            response = LLMResponse(
                content=accumulated_content or None,
                tool_calls=all_tool_calls,
                finish_reason=finish_reason,
                usage=usage,
                reasoning_content=reasoning_content,
                thinking_blocks=thinking_blocks,
            )

            if response.has_tool_calls:
                tool_call_dicts = [
                    tc.to_openai_tool_call()
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])

                    if on_progress:
                        await on_progress(tool_started(tool_call.name, tool_call.id, tool_call.arguments))

                    from datetime import datetime as _dt
                    started_at = _dt.now()
                    error_msg = None
                    result_obj: str | ToolResult | WorkflowExecution
                    try:
                        result_obj = await self.tools.execute(tool_call.name, tool_call.arguments)
                    except Exception as e:
                        error_msg = str(e)
                        result_obj = f"Error: {e}"
                    completed_at = _dt.now()
                    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                    # Handle WorkflowExecution — consume event stream, emit workflow.* SSE events
                    if isinstance(result_obj, WorkflowExecution):
                        if on_progress:
                            await on_progress(workflow_started({
                                "flow_task_id": result_obj.flow_task_id,
                                "run_id": result_obj.run_id,
                                "ws_id": result_obj.ws_id,
                            }))
                        result_str = "Workflow completed successfully"
                        try:
                            async for raw_event in result_obj.event_stream:
                                et = raw_event.get("event_type")
                                constructor = WORKFLOW_EVENT_MAP.get(et)
                                if constructor and on_progress:
                                    await on_progress(constructor(raw_event))
                                # select → stop consuming, return control to LLM
                                if et == "node_status" and raw_event.get("status") == "select":
                                    node_id = raw_event.get("node_id", "unknown")
                                    result_str = f"Workflow paused: node {node_id} needs user selection on the canvas."
                                    break
                                if et == "node_status" and raw_event.get("status") == "failed":
                                    error_msg = raw_event.get("error_msg", "Node execution failed")
                                    result_str = f"Workflow failed: {error_msg}"
                                    break
                                if et in ("finish_flow", "flow_killed"):
                                    break
                        except Exception as stream_err:
                            logger.error("Workflow event stream error: {}", stream_err)
                            error_msg = str(stream_err)
                            result_str = f"Error consuming workflow events: {stream_err}"
                        # Recalculate duration after stream consumption
                        completed_at = _dt.now()
                        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                    # Extract ToolResult events and emit them
                    elif isinstance(result_obj, ToolResult):
                        for evt in result_obj.events:
                            if on_progress:
                                await on_progress(tool_event(evt.get("name", "tool.output"), evt.get("data", {})))
                        result_str = result_obj.content
                    else:
                        result_str = result_obj

                    if on_progress:
                        if error_msg:
                            await on_progress(tool_failed(tool_call.id, error_msg))
                        else:
                            await on_progress(tool_completed(tool_call.id, duration_ms))

                    tool_timings[tool_call.id] = {
                        "name": tool_call.name,
                        "args": tool_call.arguments,
                        "started_at": started_at,
                        "completed_at": completed_at,
                        "duration_ms": duration_ms,
                        "error": error_msg,
                        "raw_output": result_str,
                    }

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result_str
                    )
            else:
                clean = self._strip_think(response.content)
                # Don't persist error responses to session history — they can
                # poison the context and cause permanent 400 loops (#1303).
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

            if on_progress:
                await on_progress(step_completed(iteration))

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages, tool_timings

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.warning("Error consuming inbound message: {}, continuing...", e)
                continue

            cmd = msg.content.strip().lower()
            if cmd == "/stop":
                await self._handle_stop(msg)
            elif cmd == "/restart":
                await self._handle_restart(msg)
            else:
                task = asyncio.create_task(self._dispatch(msg))
                self._active_tasks.setdefault(msg.session_key, []).append(task)
                task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    async def _handle_stop(self, msg: InboundMessage) -> None:
        """Cancel all active tasks and subagents for the session."""
        tasks = self._active_tasks.pop(msg.session_key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(msg.session_key)
        total = cancelled + sub_cancelled
        content = f"Stopped {total} task(s)." if total else "No active task to stop."
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=content,
        ))

    async def _handle_restart(self, msg: InboundMessage) -> None:
        """Restart the process in-place via os.execv."""
        await self.bus.publish_outbound(OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content="Restarting...",
        ))

        async def _do_restart():
            await asyncio.sleep(1)
            # Use -m nanobot instead of sys.argv[0] for Windows compatibility
            # (sys.argv[0] may be just "nanobot" without full path on Windows)
            os.execv(sys.executable, [sys.executable, "-m", "nanobot"] + sys.argv[1:])

        asyncio.create_task(_do_restart())

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message under the global lock."""
        async with self._processing_lock:
            try:
                response = await self._process_message(msg)
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    async def close_mcp(self) -> None:
        """Drain pending background archives, then close MCP connections."""
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def _schedule_background(self, coro) -> None:
        """Schedule a coroutine as a tracked background task (drained on shutdown)."""
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(self._background_tasks.remove)

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
        private_context: dict[str, Any] | None = None,
        user_id: str = "",
        workflow_id: str | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        ctx = dict(private_context or {})
        request_ctx_token = set_request_context(ctx)
        # System messages: parse origin from chat_id ("channel:chat_id")
        try:
            if msg.channel == "system":
                channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                    else ("cli", msg.chat_id))
                logger.info("Processing system message from {}", msg.sender_id)
                key = f"{channel}:{chat_id}"
                session = await self.sessions.get_or_create(
                    key, user_id=user_id, workflow_id=workflow_id, channel=channel,
                )
                self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
                history = session.get_history(max_messages=0)
                # Subagent results should be assistant role, other system messages use user role
                current_role = "assistant" if msg.sender_id == "subagent" else "user"
                messages = self.context.build_messages(
                    history=history,
                    current_message=msg.content, channel=channel, chat_id=chat_id,
                    metadata=msg.metadata,
                    current_role=current_role,
                )
                final_content, _, all_msgs, tool_timings = await self._run_agent_loop(messages)
                self._save_turn(session, all_msgs, 1 + len(history), tool_timings)
                await self.sessions.save(session, tool_traces=self._pending_traces)
                self._pending_traces = []
                self._maybe_generate_summary(session)
                return OutboundMessage(channel=channel, chat_id=chat_id,
                                      content=final_content or "Background task completed.")

            preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
            logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)
            logger.info(
                "Inbound message payload channel={} sender_id={} session_key={} content={}",
                msg.channel,
                msg.sender_id,
                session_key or msg.session_key,
                msg.content,
            )

            key = session_key or msg.session_key
            session = await self.sessions.get_or_create(
                key, user_id=user_id, workflow_id=workflow_id, channel=msg.channel,
            )

            # Slash commands
            cmd = msg.content.strip().lower()
            if cmd == "/new":
                session.clear()
                await self.sessions.save(session)
                await self.sessions.invalidate(session.session_id)

                return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                      content="New session started.")
            if cmd == "/help":
                lines = [
                    "🐈 nanobot commands:",
                    "/new — Start a new conversation",
                    "/stop — Stop the current task",
                    "/restart — Restart the bot",
                    "/help — Show available commands",
                ]
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content="\n".join(lines),
                )

            self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
            if message_tool := self.tools.get("message"):
                if isinstance(message_tool, MessageTool):
                    message_tool.start_turn()

            history = session.get_history(max_messages=0)
            initial_messages = self.context.build_messages(
                history=history,
                current_message=msg.content,
                media=msg.media if msg.media else None,
                channel=msg.channel, chat_id=msg.chat_id,
                metadata=msg.metadata,
            )

            async def _bus_progress(event: AgentEvent) -> None:
                meta = dict(msg.metadata or {})
                meta["_progress"] = True
                content = event.data.get("content", "")
                if event.event == "tool.started":
                    meta["_tool_hint"] = True
                    content = event.data.get("tool_name", "")
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
                ))

            final_content, _, all_msgs, tool_timings = await self._run_agent_loop(
                initial_messages, on_progress=on_progress or _bus_progress,
            )

            if final_content is None:
                final_content = "I've completed processing but have no response to give."

            self._save_turn(session, all_msgs, 1 + len(history), tool_timings)
            await self.sessions.save(session, tool_traces=self._pending_traces)
            self._pending_traces = []
            self._maybe_generate_summary(session)

            if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
                return None

            preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
            logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)
            logger.info(
                "Outbound message payload channel={} sender_id={} session_key={} content={}",
                msg.channel,
                msg.sender_id,
                key,
                final_content,
            )
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=final_content,
                metadata=msg.metadata or {},
            )
        finally:
            reset_request_context(request_ctx_token)

    def _save_turn(self, session: Session, messages: list[dict], skip: int, tool_timings: dict[str, dict] | None = None) -> None:
        """Save new-turn messages into session, splitting into display/LLM/trace roles.

        Roles written to session.messages:
          - "user"      — user message (display + LLM context)
          - "agent"     — final assistant reply (display + LLM context, mapped to "assistant" for LLM)
          - "assistant" — intermediate assistant with tool_calls (LLM context only)
          - "tool"      — tool result (LLM context only, truncated)

        Also builds tool_traces list into self._pending_traces for SessionManager.save().
        """
        from datetime import datetime

        tool_timings = tool_timings or {}
        turn = session.turn_count + 1
        tool_hints: list[str] = []
        display_count = 0

        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")

            # Skip empty assistant messages — they poison session context
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue

            # --- User message cleanup ---
            if role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = []
                    for c in content:
                        if c.get("type") == "text" and isinstance(c.get("text"), str) and c["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                            continue
                        if (c.get("type") == "image_url"
                                and c.get("image_url", {}).get("url", "").startswith("data:image/")):
                            path = (c.get("_meta") or {}).get("path", "")
                            placeholder = f"[image: {path}]" if path else "[image]"
                            filtered.append({"type": "text", "text": placeholder})
                        else:
                            filtered.append(c)
                    if not filtered:
                        continue
                    entry["content"] = filtered
                entry["turn"] = turn
                display_count += 1

            # --- Assistant with tool_calls (intermediate, LLM context only) ---
            elif role == "assistant" and entry.get("tool_calls"):
                # Accumulate tool hints for the final agent message
                for tc in entry.get("tool_calls") or []:
                    func = tc.get("function", {})
                    name = func.get("name", "unknown")
                    tool_hints.append(f"{name}()")
                entry["turn"] = turn

            # --- Assistant without tool_calls (final reply → rename to "agent") ---
            elif role == "assistant" and not entry.get("tool_calls"):
                entry["role"] = "agent"
                entry["turn"] = turn
                if tool_hints:
                    entry["tool_hints"] = list(tool_hints)
                display_count += 1
                # Update session preview
                if isinstance(entry.get("content"), str):
                    session.last_message_preview = entry["content"][:120]

            # --- Tool result (LLM context only, truncated) ---
            elif role == "tool":
                if isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                    entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
                entry["turn"] = turn

                # Build tool trace document
                tcid = entry.get("tool_call_id", "")
                timing = tool_timings.get(tcid, {})
                if timing:
                    raw_output = timing.get("raw_output", content)
                    output_str = raw_output if isinstance(raw_output, str) else str(raw_output)
                    self._pending_traces.append({
                        "session_id": session.session_id,
                        "turn": turn,
                        "tool_call_id": tcid,
                        "tool_name": timing.get("name", entry.get("name", "unknown")),
                        "input": timing.get("args", {}),
                        "output": output_str[:65536],  # cap at 64KB
                        "output_size_bytes": len(output_str.encode("utf-8", errors="replace")),
                        "status": "error" if timing.get("error") else "success",
                        "error": timing.get("error"),
                        "duration_ms": timing.get("duration_ms", 0),
                        "started_at": timing.get("started_at"),
                        "completed_at": timing.get("completed_at"),
                    })

            entry.setdefault("created_at", datetime.now().isoformat())
            session.messages.append(entry)

        # Update session counters
        session.message_count += display_count
        session.turn_count = turn
        session.updated_at = datetime.now()

    _SUMMARY_PROMPT = (
        "Summarize this conversation in one short sentence (no more than 15 words). "
        "Reply with ONLY the sentence, no quotes or extra punctuation. "
        "Use the same language as the user's message."
    )

    def _maybe_generate_summary(self, session: Session) -> None:
        """Schedule async summary generation if this is the first turn and no summary exists."""
        if session.summary or len(session.messages) < 2:
            return
        self._schedule_background(self._generate_summary(session))

    async def _generate_summary(self, session: Session) -> None:
        """Generate a summary title for the session via a lightweight LLM (background task)."""
        try:
            # Extract first user message and first assistant response
            first_user = first_assistant = None
            for m in session.messages:
                role = m.get("role")
                content = m.get("content")
                if role == "user" and not first_user and isinstance(content, str):
                    first_user = content[:500]
                elif role in ("assistant", "agent") and not first_assistant and isinstance(content, str):
                    first_assistant = content[:500]
                if first_user and first_assistant:
                    break

            if not first_user:
                return

            context = f"User: {first_user}"
            if first_assistant:
                context += f"\nAssistant: {first_assistant}"

            # Use dedicated summary model (gpt-4o-mini) if configured,
            # otherwise fall back to the main provider.
            if self._summary_model and self._summary_api_key:
                from litellm import acompletion

                resp = await acompletion(
                    model=self._summary_model,
                    messages=[
                        {"role": "system", "content": self._SUMMARY_PROMPT},
                        {"role": "user", "content": context},
                    ],
                    max_tokens=50,
                    temperature=0.7,
                    api_key=self._summary_api_key,
                )
                summary = (resp.choices[0].message.content or "").strip()
            else:
                response = await self.provider.chat_with_retry(
                    messages=[
                        {"role": "system", "content": self._SUMMARY_PROMPT},
                        {"role": "user", "content": context},
                    ],
                    model=self.model,
                    max_tokens=50,
                    temperature=0.7,
                )
                summary = (response.content or "").strip()

            if summary:
                session.summary = summary
                await self.sessions.save_summary(session.session_id, summary)
                logger.debug("Generated summary for session {}: {}", session.session_id, summary)
        except Exception:
            logger.warning("Failed to generate summary for session {}", session.session_id)

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
        metadata: dict[str, Any] | None = None,
        private_context: dict[str, Any] | None = None,
        user_id: str = "",
        workflow_id: str | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage)."""
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            metadata=metadata or {},
        )
        response = await self._process_message(
            msg,
            session_key=session_key,
            on_progress=on_progress,
            private_context=private_context,
            user_id=user_id,
            workflow_id=workflow_id,
        )
        return response.content if response else ""
