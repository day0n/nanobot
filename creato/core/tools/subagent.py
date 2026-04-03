"""SubagentTool — spawns a child agent via AgentFactory."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from loguru import logger

from creato.core.events import (
    AgentEvent,
    subagent_completed,
    subagent_message_delta,
    subagent_started,
    subagent_step_completed,
    subagent_step_started,
    subagent_tool_completed,
    subagent_tool_event,
    subagent_tool_started,
)
from creato.core.executor import AgentExecutor, ExecutorHooks
from creato.schemas.executor import ExecutorResult
from creato.schemas.tools import SubagentRequest, SubagentResult
from creato.core.prompt.runtime import build_runtime_context
from creato.core.request_context import (
    get_request_context,
    reset_request_context,
    set_request_context,
)
from creato.core.tools.base import ProgressAware, Tool

if __name__ != "__main__":
    from creato.core.profile import AgentProfile, ProfileRegistry


class SubagentTool(Tool, ProgressAware):
    """Tool that spawns a child agent with isolated tools and skills.

    Delegates all assembly logic to AgentFactory.build() — this tool
    only handles execution lifecycle, request context, and progress events.
    """

    def __init__(
        self,
        factory: Any,  # AgentFactory (lazy to avoid circular import)
        profile_registry: ProfileRegistry,
        provider: Any,  # LLMProvider
        parent_model: str,
        depth: int = 0,
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ):
        self._factory = factory
        self._registry = profile_registry
        self._provider = provider
        self._parent_model = parent_model
        self._depth = depth
        self._on_progress = on_progress

    def set_progress(self, callback: Callable[[AgentEvent], Awaitable[None]] | None) -> None:
        """Called by AgentLoop before each _run_agent_loop to wire up progress."""
        self._on_progress = callback

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def description(self) -> str:
        profiles = self._registry.subagent_profiles()
        if not profiles:
            return "Spawn a specialised subagent. No agent types are registered."
        lines = ["Spawn a specialised subagent. Available types:"]
        for p in profiles:
            lines.append(f"- {p.name}: {p.description}")
        return "\n".join(lines)

    @property
    def parameters(self) -> dict[str, Any]:
        names = [p.name for p in self._registry.subagent_profiles()]
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to perform.",
                },
              "agent_type": {
                    "type": "string",
                    "enum": names or ["workflow-editor"],
                    "description": "The type of subagent to spawn.",
                },
            },
            "required": ["task", "agent_type"],
        }

    async def execute(self, task: str, agent_type: str, **kwargs: Any) -> str:
        from creato.core.factory import _MAX_DEPTH

        # Validate input via Pydantic
        req = SubagentRequest(task=task, agent_type=agent_type)

        if self._depth >= _MAX_DEPTH:
            return f"Error: Maximum subagent depth ({_MAX_DEPTH}) reached."

        profile = self._registry.get(req.agent_type)
        if profile is None:
            available = ", ".join(p.name for p in self._registry.subagent_profiles()) or "(none)"
            return f"Error: Unknown agent type '{req.agent_type}'. Available: {available}"

        parent_ctx = get_request_context()
        token = set_request_context(parent_ctx)
        try:
            return await self._run_subagent(profile, req.task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Subagent '{}' failed", req.agent_type)
            return f"Error: Subagent '{req.agent_type}' failed: {exc}"
        finally:
            reset_request_context(token)

    async def _run_subagent(self, profile: AgentProfile, task: str) -> str:
        # Emit start event
        if self._on_progress:
            await self._on_progress(subagent_started(profile.name, task))

        # Build agent instance via factory (tools, skills, prompt — all isolated)
        child_hooks = self._build_child_hooks()
        instance = self._factory.build(
            profile,
            depth=self._depth + 1,
            on_progress=self._on_progress,
        )

        # Build messages
        runtime_ctx = build_runtime_context()
        workspace = self._factory.context.workspace
        user_message = f"{runtime_ctx}\n\nWorkspace: {workspace}\n\n{task}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": instance.system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Run executor
        executor = AgentExecutor(
            provider=self._provider,
            model=instance.model,
            tools=instance.tools,
            max_iterations=instance.max_iterations,
            hooks=child_hooks,
        )
        result: ExecutorResult = await executor.run(messages)

        # Build structured result
        subagent_result = SubagentResult(
            agent_type=profile.name,
            content=result.content or "(no output)",
            tools_used=result.tools_used,
            iterations=result.iterations,
        )

        # Emit completion event
        if self._on_progress:
            await self._on_progress(subagent_completed(
                agent_type=profile.name,
                tools_used=result.tools_used,
                result_preview=result.content or "",
            ))

        return subagent_result.to_tool_response()

    def _build_child_hooks(self) -> ExecutorHooks:
        """Create hooks that forward events to parent's progress callback."""
        progress = self._on_progress
        if not progress:
            return ExecutorHooks()

        async def on_text_delta(text: str) -> None:
            await progress(subagent_message_delta(text))

        async def on_tool_start(name: str, call_id: str, arguments: dict[str, Any]) -> None:
            await progress(subagent_tool_started(name, call_id, arguments))

        async def on_tool_end(name: str, call_id: str, duration_ms: int, error: str | None, args: dict[str, Any] | None = None, output: str = "") -> None:
            await progress(subagent_tool_completed(name, call_id, duration_ms, error))

        async def on_tool_event(event_name: str, data: dict[str, Any]) -> None:
            await progress(subagent_tool_event(event_name, data))

        async def on_step_start(step: int) -> None:
            await progress(subagent_step_started(step))

        async def on_step_end(step: int) -> None:
            await progress(subagent_step_completed(step))

        return ExecutorHooks(
            on_step_start=on_step_start,
            on_step_end=on_step_end,
            on_text_delta=on_text_delta,
            on_tool_start=on_tool_start,
            on_tool_end=on_tool_end,
            on_tool_event=on_tool_event,
        )
