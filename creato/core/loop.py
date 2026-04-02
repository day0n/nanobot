"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import OrderedDict
from contextlib import AsyncExitStack, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from creato.sentry import SafeSpan, SafeTransaction, set_sentry_context

from creato.posthog import (
    capture_span,
    capture_trace,
    posthog_timer,
    reset_posthog_context,
    set_posthog_context,
    update_context_properties,
)

from creato.core.context.compressor import ContextCompressor
from creato.core.context.token_counter import count_message, count_text
from creato.core.prompt import PromptBuilder
from creato.core.prompt.runtime import RUNTIME_CONTEXT_TAG
from creato.core.events import (
    AgentEvent,
    message_delta,
    step_completed,
    step_started,
    tool_completed,
    tool_event,
    tool_failed,
    tool_started,
    workflow_started,
)
from creato.core.request_context import reset_request_context, set_request_context
from creato.core.memory import MemoryProvider
from creato.core.executor import AgentExecutor, ExecutorHooks
from creato.core.profile import AgentProfile, AgentContext, ProfileRegistry
from creato.core.factory import AgentFactory
from creato.core.tools.base import ContextAware, ProgressAware, Tool, TurnAware
from creato.core.tools.registry import ToolRegistry
from creato.bus.events import InboundMessage, OutboundMessage
from creato.providers.base import LLMProvider
from creato.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from creato.config.schema import ApiServerConfig, ChannelsConfig, ExecToolConfig, WebSearchConfig


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
        provider: LLMProvider,
        workspace: Path,
        profile: AgentProfile | None = None,
        factory: AgentFactory | None = None,
        model: str | None = None,
        max_iterations: int = 40,
        context_window_tokens: int = 65_536,
        web_search_config: WebSearchConfig | None = None,
        web_proxy: str | None = None,
        api_config: ApiServerConfig | None = None,
        exec_config: ExecToolConfig | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        summary_provider: LLMProvider | None = None,
        memory: MemoryProvider | None = None,
        max_output_tokens: int = 8192,
    ):
        from creato.config.schema import ApiServerConfig, ExecToolConfig, WebSearchConfig

        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self._summary_provider = summary_provider
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.max_output_tokens = max_output_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.api_config = api_config or ApiServerConfig()
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self.memory = memory
        self._compressor = ContextCompressor(
            provider=summary_provider or provider,
        )

        if session_manager is None:
            raise ValueError("session_manager is required (must not be None)")
        self.sessions = session_manager

        # Build agent instance from profile via factory
        if profile and factory:
            instance = factory.build(profile)
            self.tools = instance.tools
            self.model = instance.model
            self.max_iterations = instance.max_iterations
            self.context = PromptBuilder(workspace, system_prompt_override=instance.system_prompt)
        else:
            # Fallback: no profile provided (legacy path)
            self.tools = ToolRegistry()
            self.context = PromptBuilder(workspace)

        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._background_tasks: list[asyncio.Task] = []
        self._session_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        # CREATO_MAX_CONCURRENT_REQUESTS: <=0 means unlimited; default 3.
        _max = int(os.environ.get("CREATO_MAX_CONCURRENT_REQUESTS", "3"))
        self._concurrency_gate: asyncio.Semaphore | None = (
            asyncio.Semaphore(_max) if _max > 0 else None
        )
        self._pending_traces: list[dict] = []  # tool traces accumulated during _save_turn

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        # Disabled for the restricted chatbot rollout: do not register dynamic MCP tools.
        return

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None, session_key: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        for tool in self.tools.get_by_protocol(ContextAware):
            tool.set_routing_context(channel, chat_id, message_id)

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
        """Run the agent iteration loop via AgentExecutor."""
        # Wire up progress callback to tools that need it
        for tool in self.tools.get_by_protocol(ProgressAware):
            tool.set_progress(on_progress)

        hooks = self._build_hooks(on_progress)

        _agent_span = SafeSpan("gen_ai.invoke_agent", "invoke_agent opencreator_agent")
        _agent_span.set_data("gen_ai.agent.name", "opencreator_agent")
        _agent_span.set_data("gen_ai.request.model", self.model)
        _agent_span.__enter__()

        try:
            executor = AgentExecutor(
                provider=self.provider,
                model=self.model,
                tools=self.tools,
                max_iterations=self.max_iterations,
                hooks=hooks,
            )
            result = None
            result = await executor.run(initial_messages)
        finally:
            _agent_span.set_data("gen_ai.response.text", (result.content or "")[:4096] if result else "")
            _agent_span.__exit__(None, None, None)

        return result.content, result.tools_used, result.messages, result.tool_timings

    def _build_hooks(self, on_progress: Callable[[AgentEvent], Awaitable[None]] | None) -> ExecutorHooks:
        """Build ExecutorHooks that inject Sentry, PostHog, and SSE dispatch."""

        # Collect workflow events for persistence in _save_turn
        self._pending_workflow_events: list[dict[str, Any]] = []

        async def _on_step_start(step: int) -> None:
            if on_progress:
                await on_progress(step_started(step))

        async def _on_step_end(step: int) -> None:
            if on_progress:
                await on_progress(step_completed(step))

        async def _on_text_delta(text: str) -> None:
            if on_progress:
                await on_progress(message_delta(text))

        async def _on_tool_start(name: str, call_id: str, args: dict) -> None:
            if on_progress:
                await on_progress(tool_started(name, call_id, args))

        async def _on_tool_end(name: str, call_id: str, duration_ms: int, error: str | None, args: dict = None, output: str = "") -> None:
            capture_span(
                span_id=call_id, name=name, input_data=args or {}, output_data=output,
                latency=duration_ms / 1000.0, is_error=bool(error), error=error,
            )
            if on_progress:
                if error:
                    await on_progress(tool_failed(call_id, error))
                else:
                    await on_progress(tool_completed(call_id, duration_ms))

        async def _on_tool_event(event_name: str, data: dict) -> None:
            if on_progress:
                await on_progress(tool_event(event_name, data))

        async def _on_workflow_start(data: dict) -> None:
            evt = workflow_started(data)
            if on_progress:
                await on_progress(evt)
            self._pending_workflow_events.append(evt.to_dict())

        async def _on_workflow_event(sse_event: Any) -> None:
            """Forward tool-produced AgentEvent directly to SSE and collect for persistence."""
            if on_progress and sse_event:
                await on_progress(sse_event)
            if sse_event and hasattr(sse_event, "to_dict"):
                self._pending_workflow_events.append(sse_event.to_dict())

        return ExecutorHooks(
            on_step_start=_on_step_start,
            on_step_end=_on_step_end,
            on_text_delta=_on_text_delta,
            on_tool_start=_on_tool_start,
            on_tool_end=_on_tool_end,
            on_tool_event=_on_tool_event,
            on_workflow_start=_on_workflow_start,
            on_workflow_event=_on_workflow_event,
        )

    async def _locked_process(self, msg: InboundMessage, *, session_key: str | None = None, **kwargs) -> OutboundMessage | None:
        """Process a message with per-session lock + global concurrency gate.

        Args:
            session_key: The real session key to lock on. Falls back to msg.session_key
                         if not provided (e.g. subagent results that carry the real key
                         in their chat_id).
        """
        key = session_key or msg.session_key
        if key in self._session_locks:
            self._session_locks.move_to_end(key)
        lock = self._session_locks.setdefault(key, asyncio.Lock())
        # Evict oldest locks to prevent unbounded growth
        while len(self._session_locks) > 1000:
            self._session_locks.popitem(last=False)
        gate = self._concurrency_gate or nullcontext()
        async with lock, gate:
            return await self._process_message(msg, session_key=key, **kwargs)

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

        # PostHog LLM Analytics context
        import uuid as _uuid
        _posthog_trace_id = _uuid.uuid4().hex
        _posthog_token = set_posthog_context(
            trace_id=_posthog_trace_id,
            session_id=session_key or msg.session_key,
            distinct_id=user_id,
        )
        _posthog_start = posthog_timer()
        _posthog_final_content: str | None = None

        # Start a Sentry transaction manually — SSE streaming runs in create_task,
        # so the FastAPI auto-transaction is already closed by the time agent finishes.
        _txn = SafeTransaction("agent.chat", "agent.process_message")
        _txn.__enter__()
        set_sentry_context(
            user_id=user_id,
            tags={"channel": msg.channel, "session_key": session_key or msg.session_key},
        )

        # System messages: parse origin from chat_id ("channel:chat_id")
        try:
            if msg.channel == "system":
                channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                    else ("cli", msg.chat_id))
                logger.info("Processing system message from {}", msg.sender_id)
                # Use the real session_key (from session_key_override) if available,
                # otherwise fall back to the parsed channel:chat_id.
                key = session_key or msg.session_key
                session = await self.sessions.get_or_create(
                    key, user_id=user_id, workflow_id=workflow_id, channel=channel,
                )
                self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"), session_key=key)
                full_history = session.get_history(max_messages=0)
                # Retrieve long-term memory before budget calculation so its size is included
                memory_context = await self._retrieve_memory(user_id, msg.content)
                # Token-aware sliding window (includes all non-history token costs)
                fixed_tokens = self._estimate_fixed_tokens(msg.content, memory_context)
                history, dropped = self._trim_history(full_history, fixed_tokens, 0)
                # Compress dropped messages into a summary (injected as user message)
                context_summary: str | None = None
                if dropped:
                    context_summary = await self._compress_dropped(session, dropped)
                # Subagent results should be assistant role, other system messages use user role
                current_role = "assistant" if msg.sender_id == "subagent" else "user"
                messages = self.context.build_messages(
                    history=history,
                    current_message=msg.content, channel=channel, chat_id=chat_id,
                    metadata=msg.metadata,
                    current_role=current_role,
                    memory_context=memory_context,
                    context_summary=context_summary,
                )
                final_content, _, all_msgs, tool_timings = await self._run_agent_loop(messages)
                _posthog_final_content = final_content
                # skip = system(1) + dynamic context msg(0 or 1) + history
                _has_dynamic_ctx = bool(context_summary or memory_context)
                skip = 1 + int(_has_dynamic_ctx) + len(history)
                self._save_turn(session, all_msgs, skip, tool_timings, request_metadata=msg.metadata)
                await self.sessions.save(session, tool_traces=self._pending_traces)
                self._pending_traces = []
                self._maybe_generate_summary(session)
                self._store_memory_async(user_id, all_msgs, skip)
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
                    "🐈 creato commands:",
                    "/new — Start a new conversation",
                    "/help — Show available commands",
                ]
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id, content="\n".join(lines),
                )

            self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"), session_key=key)
            for tool in self.tools.get_by_protocol(TurnAware):
                tool.on_turn_start()

            full_history = session.get_history(max_messages=0)
            # Retrieve long-term memory before budget calculation so its size is included
            memory_context = await self._retrieve_memory(user_id, msg.content)
            # Token-aware sliding window (includes all non-history token costs)
            fixed_tokens = self._estimate_fixed_tokens(msg.content, memory_context)
            history, dropped = self._trim_history(full_history, fixed_tokens, 0)
            # Compress dropped messages into a summary (injected as user message)
            context_summary: str | None = None
            if dropped:
                context_summary = await self._compress_dropped(session, dropped)
            initial_messages = self.context.build_messages(
                history=history,
                current_message=msg.content,
                media=msg.media if msg.media else None,
                channel=msg.channel, chat_id=msg.chat_id,
                metadata=msg.metadata,
                memory_context=memory_context,
                context_summary=context_summary,
            )

            final_content, _, all_msgs, tool_timings = await self._run_agent_loop(
                initial_messages, on_progress=on_progress,
            )

            if final_content is None:
                final_content = "I've completed processing but have no response to give."
            _posthog_final_content = final_content

            # skip = system(1) + dynamic context msg(0 or 1) + history
            _has_dynamic_ctx = bool(context_summary or memory_context)
            skip = 1 + int(_has_dynamic_ctx) + len(history)
            self._save_turn(session, all_msgs, skip, tool_timings, request_metadata=msg.metadata)
            await self.sessions.save(session, tool_traces=self._pending_traces)
            self._pending_traces = []
            self._maybe_generate_summary(session)
            self._store_memory_async(user_id, all_msgs, skip)

            if any(t.on_turn_end() for t in self.tools.get_by_protocol(TurnAware)):
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
            _txn.__exit__(None, None, None)
            reset_request_context(request_ctx_token)
            # PostHog trace-level event (skip for slash commands that don't invoke LLM)
            if _posthog_final_content is not None:
                capture_trace(
                    input_state=msg.content[:2000] if msg.content else None,
                    output_state=_posthog_final_content[:2000],
                    latency=posthog_timer() - _posthog_start,
                    is_error=False,
                    name="agent_chat",
                )
            reset_posthog_context(_posthog_token)

    def _save_turn(self, session: Session, messages: list[dict], skip: int, tool_timings: dict[str, dict] | None = None, request_metadata: dict[str, Any] | None = None) -> None:
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
                if isinstance(content, str) and content.startswith(RUNTIME_CONTEXT_TAG):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = []
                    for c in content:
                        if c.get("type") == "text" and isinstance(c.get("text"), str) and c["text"].startswith(RUNTIME_CONTEXT_TAG):
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
                # Attach request metadata (files, etc.) to the user message
                # so the frontend can display attachments in chat history.
                if request_metadata:
                    entry["metadata"] = request_metadata
                    request_metadata = None  # only attach to the first user message
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

            # --- Tool result (LLM context only) ---
            elif role == "tool":
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

        # Append collected workflow events as workflow_event messages
        # These are display-only (not part of LLM context).
        wf_events = getattr(self, "_pending_workflow_events", [])
        if wf_events:
            now_iso = datetime.now().isoformat()
            for evt in wf_events:
                session.messages.append({
                    "role": "workflow_event",
                    "turn": turn,
                    "event": evt.get("event", ""),
                    "event_data": evt.get("data", {}),
                    "created_at": now_iso,
                })
            self._pending_workflow_events = []

    # --- Long-term memory helpers ---

    # --- Context window management ---

    def _estimate_fixed_tokens(
        self,
        current_message: str,
        memory_context: str | None = None,
    ) -> int:
        """Estimate tokens for everything except history messages.

        Includes: system prompt, memory injection, runtime context,
        current user message, and tool schema definitions.
        """
        tokens = count_text(self.context.build_system_prompt())

        # Memory injection (appended to system prompt in builder)
        if memory_context:
            tokens += count_text(memory_context) + 60  # header text overhead

        # Runtime context (prepended to user message in builder)
        tokens += 50  # timestamp + channel + chat_id lines

        # Current user message
        tokens += count_text(current_message) + 10  # role overhead

        # Tool schema definitions (sent alongside messages on every LLM call)
        tool_defs = self.tools.get_definitions()
        if tool_defs:
            import json as _json
            tokens += count_text(_json.dumps(tool_defs, ensure_ascii=False))

        # Reserve space for compression summary (injected into system prompt when
        # the sliding window drops messages). 300 max_tokens + ~50 formatting.
        tokens += 350

        return tokens

    def _trim_history(
        self,
        history: list[dict],
        fixed_tokens: int,
        _unused: int = 0,
    ) -> tuple[list[dict], list[dict]]:
        """Token-aware history trimming (sliding window).

        Keeps the most recent messages that fit within the token budget.
        Aligns the cut point to a legal tool-call boundary and ensures
        the result starts with a user message (never orphan assistant/tool).

        Returns:
            (trimmed_history, dropped_messages)
        """
        budget = self.context_window_tokens - fixed_tokens - self.max_output_tokens - 512

        if budget <= 0:
            logger.warning(
                "Token budget exhausted by fixed overhead alone "
                "(fixed={}, output={}, window={})",
                fixed_tokens, self.max_output_tokens, self.context_window_tokens,
            )
            return [], list(history)

        # Walk from newest to oldest, accumulate tokens
        total = 0
        cut_index = 0  # everything before this index gets dropped
        for i in range(len(history) - 1, -1, -1):
            msg_tokens = count_message(history[i])
            if total + msg_tokens > budget:
                cut_index = i + 1
                break
            total += msg_tokens

        if cut_index == 0:
            return history, []

        # Align to legal tool-call boundary
        trimmed = history[cut_index:]
        start = Session._find_legal_start(trimmed)
        if start:
            cut_index += start
            trimmed = history[cut_index:]

        # Ensure trimmed history starts with a user message.
        # If no user message exists in the trimmed slice, drop everything
        # (the compressor summary will provide context instead).
        found_user = False
        for i, m in enumerate(trimmed):
            if m.get("role") == "user":
                if i > 0:
                    cut_index += i
                    trimmed = trimmed[i:]
                found_user = True
                break
        if not found_user:
            return [], list(history)

        dropped = history[:cut_index]

        if dropped:
            logger.info(
                "Sliding window: dropped {} messages ({} kept, budget={})",
                len(dropped), len(trimmed), budget,
            )

        return trimmed, dropped

    async def _compress_dropped(
        self, session: Session, dropped: list[dict],
    ) -> str | None:
        """Compress dropped messages into a summary for context injection.

        The summary is cached in session.metadata keyed by the number of
        dropped messages. It is only regenerated when the drop count changes
        (i.e. the sliding window has moved further).
        """
        if not dropped:
            return None

        # Cache key: number of dropped messages.
        # This stays stable across turns as long as the window doesn't move.
        drop_count = len(dropped)
        cached = session.metadata.get("context_summary")
        cached_drop_count = session.metadata.get("_ctx_summary_drop_count", 0)

        if cached and cached_drop_count == drop_count:
            return cached

        # Generate new summary
        try:
            summary = await self._compressor.compress(dropped)
            if summary:
                formatted = (
                    "[Earlier conversation summary]\n\n"
                    f"{summary}\n\n"
                    "[End of summary \u2014 recent messages follow]"
                )
                session.metadata["context_summary"] = formatted
                session.metadata["_ctx_summary_drop_count"] = drop_count
                return formatted
        except Exception as e:
            logger.warning("Context compression failed: {}", e)

        return cached  # fallback to stale cache


    async def _retrieve_memory(self, user_id: str, query: str) -> str | None:
        """Retrieve relevant long-term memories for the user. Returns formatted text or None."""
        if not self.memory or not user_id:
            return None
        try:
            entries = await self.memory.retrieve(user_id, query)
            if not entries:
                return None
            return "\n".join(f"- {e.content}" for e in entries)
        except Exception as e:
            logger.warning("Memory retrieve failed for user {}: {}", user_id, e)
            return None

    def _store_memory_async(self, user_id: str, all_msgs: list[dict], skip: int) -> None:
        """Schedule async memory extraction from the current turn (non-blocking)."""
        if not self.memory or not user_id:
            return
        turn_messages = [
            m for m in all_msgs[skip:]
            if m.get("role") in ("user", "agent")
            and isinstance(m.get("content"), str)
            and m.get("content", "").strip()
        ]
        if turn_messages:
            self._schedule_background(self.memory.store(user_id, turn_messages))

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

            # Use dedicated summary provider if available,
            # otherwise fall back to the main provider.
            target = self._summary_provider or self.provider
            response = await target.chat(
                messages=[
                    {"role": "system", "content": self._SUMMARY_PROMPT},
                    {"role": "user", "content": context},
                ],
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
        session_key: str = "api:direct",
        channel: str = "api",
        chat_id: str = "direct",
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
        metadata: dict[str, Any] | None = None,
        private_context: dict[str, Any] | None = None,
        user_id: str = "",
        workflow_id: str | None = None,
    ) -> str:
        """Process a message directly (for API/SSE usage).

        Uses per-session lock so different users run concurrently while
        messages within the same session remain serialised.
        """
        await self._connect_mcp()
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            metadata=metadata or {},
        )
        response = await self._locked_process(
            msg,
            session_key=session_key,
            on_progress=on_progress,
            private_context=private_context,
            user_id=user_id,
            workflow_id=workflow_id,
        )
        return response.content if response else ""
