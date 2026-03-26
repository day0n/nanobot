"""SubagentTool — spawns a child agent loop with its own tools."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from loguru import logger

from creato.agent.events import AgentEvent, subagent_completed, subagent_started
from creato.agent.executor import ExecutorHooks, ExecutorResult
from creato.agent.request_context import (
    get_request_context,
    reset_request_context,
    set_request_context,
)
from creato.agent.skills import SkillsLoader
from creato.agent.subagents.prompt import (
    build_subagent_system_prompt,
    build_subagent_user_message,
)
from creato.agent.subagents.types import SubagentContext, SubagentTypeRegistry
from creato.agent.tools.base import Tool
from creato.agent.tools.registry import ToolRegistry
from creato.providers.base import LLMProvider

_MAX_DEPTH = 3


class SubagentTool(Tool):
    """Tool that spawns a child agent with a specialised tool set."""

    def __init__(
        self,
        type_registry: SubagentTypeRegistry,
        context: SubagentContext,
        skills_loader: SkillsLoader,
        provider: LLMProvider,
        parent_model: str,
        parent_tools: ToolRegistry,
        current_depth: int = 0,
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ):
        self._registry = type_registry
        self._context = context
        self._skills_loader = skills_loader
        self._provider = provider
        self._parent_model = parent_model
        self._parent_tools = parent_tools
        self._depth = current_depth
        self._on_progress = on_progress

    def set_progress(self, callback: Callable[[AgentEvent], Awaitable[None]]) -> None:
        """Called by AgentLoop before each iteration to wire up progress."""
        self._on_progress = callback

    # -- Tool interface -------------------------------------------------------

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def description(self) -> str:
        types = self._registry.list_types()
        if not types:
            return "Spawn a specialised subagent. No agent types are registered."
        lines = ["Spawn a specialised subagent. Available types:"]
        for t in types:
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to perform.",
                },
                "agent_type": {
                    "type": "string",
                    "enum": self._registry.names or ["researcher"],
                    "description": "The type of subagent to spawn.",
                },
            },
            "required": ["task", "agent_type"],
        }

    async def execute(self, task: str, agent_type: str, **kwargs: Any) -> str:
        if self._depth >= _MAX_DEPTH:
            return f"Error: Maximum subagent depth ({_MAX_DEPTH}) reached. Cannot spawn further subagents."

        sa_type = self._registry.get(agent_type)
        if sa_type is None:
            available = ", ".join(self._registry.names) or "(none)"
            return f"Error: Unknown agent type '{agent_type}'. Available: {available}"

        parent_ctx = get_request_context()
        token = set_request_context(parent_ctx)
        try:
            return await self._run_subagent(sa_type, task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Subagent '{}' failed", agent_type)
            return f"Error: Subagent '{agent_type}' failed: {exc}"
        finally:
            reset_request_context(token)

    # -- Internal -------------------------------------------------------------

    async def _run_subagent(self, sa_type: Any, task: str) -> str:
        from creato.agent.executor import AgentExecutor
        from creato.agent.tools.filesystem import LoadSkillTool

        # Emit start event
        if self._on_progress:
            await self._on_progress(subagent_started(sa_type.name, task))

        # Build fresh tool instances from factories
        tools = ToolRegistry()
        for factory in sa_type.tool_factories:
            tool = factory(self._context)
            tools.register(tool)

        # Add load_skill if there are loadable skills
        if sa_type.loadable_skills:
            tools.register(LoadSkillTool(self._skills_loader))

        # Allow nested subagents if depth permits
        if self._depth + 1 < _MAX_DEPTH:
            child_subagent = SubagentTool(
                type_registry=self._registry,
                context=self._context,
                skills_loader=self._skills_loader,
                provider=self._provider,
                parent_model=self._parent_model,
                parent_tools=self._parent_tools,
                current_depth=self._depth + 1,
                on_progress=self._on_progress,
            )
            tools.register(child_subagent)

        # Build prompts
        system_prompt = build_subagent_system_prompt(
            sa_type, self._skills_loader, tool_names=tools.tool_names,
        )
        user_message = build_subagent_user_message(task, self._context.workspace)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Build child hooks
        child_hooks = self._build_child_hooks()

        # Run executor
        model = sa_type.model or self._parent_model
        executor = AgentExecutor(
            provider=self._provider,
            model=model,
            tools=tools,
            max_iterations=sa_type.max_iterations,
            hooks=child_hooks,
        )
        result: ExecutorResult = await executor.run(messages)

        # Emit completion event
        if self._on_progress:
            await self._on_progress(subagent_completed(
                agent_type=sa_type.name,
                tools_used=result.tools_used,
                result_preview=result.content or "",
            ))

        # Format return
        tool_summary = ", ".join(sorted(set(result.tools_used))) if result.tools_used else "none"
        content = result.content or "(no output)"
        return f"[subagent:{sa_type.name} | {result.iterations} iterations | tools: {tool_summary}]\n\n{content}"

    def _build_child_hooks(self) -> ExecutorHooks:
        """Create hooks that forward events to the parent's progress callback."""
        progress = self._on_progress

        async def _noop(*args: Any) -> None:
            pass

        if not progress:
            return ExecutorHooks()

        async def on_text_delta(text: str) -> None:
            await progress(AgentEvent(event="subagent.message.delta", data={"content": text}))

        async def on_tool_start(name: str, call_id: str, arguments: dict) -> None:
            await progress(AgentEvent(
                event="subagent.tool.started",
                data={"tool_name": name, "tool_call_id": call_id, "arguments": arguments},
            ))

        async def on_tool_end(name: str, call_id: str, duration_ms: int, error: str | None, args: dict = None, output: str = "") -> None:
            data: dict[str, Any] = {"tool_name": name, "tool_call_id": call_id, "duration_ms": duration_ms}
            if error:
                data["error"] = error
            await progress(AgentEvent(event="subagent.tool.completed", data=data))

        async def on_tool_event(event_name: str, data: dict) -> None:
            await progress(AgentEvent(event="subagent.tool.event", data={"event_name": event_name, **data}))

        async def on_step_start(step: int) -> None:
            await progress(AgentEvent(event="subagent.step.started", data={"step": step}))

        async def on_step_end(step: int) -> None:
            await progress(AgentEvent(event="subagent.step.completed", data={"step": step}))

        return ExecutorHooks(
            on_step_start=on_step_start,
            on_step_end=on_step_end,
            on_text_delta=on_text_delta,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
            on_tool_event=on_tool_event,
        )
