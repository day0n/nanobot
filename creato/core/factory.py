"""AgentFactory — materializes an AgentProfile into a runnable AgentInstance.

This is the SINGLE place where agent assembly happens. Both AgentLoop
(for the main agent) and SubagentTool (for child agents) use this factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from creato.core.profile import AgentContext, AgentInstance, AgentProfile, ProfileRegistry
from creato.core.skills import SkillsLoader
from creato.core.tools.registry import ToolRegistry
from creato.providers.base import LLMProvider

if TYPE_CHECKING:
    from creato.core.events import AgentEvent

_MAX_DEPTH = 3


class AgentFactory:
    """Builds a runnable AgentInstance from an AgentProfile.

    The factory holds shared infrastructure (context, skills, provider)
    and produces fresh, isolated tool registries for each build() call.
    """

    def __init__(
        self,
        context: AgentContext,
        skills_loader: SkillsLoader,
        provider: LLMProvider,
        default_model: str,
        profile_registry: ProfileRegistry,
    ) -> None:
        self._context = context
        self._skills_loader = skills_loader
        self._provider = provider
        self._default_model = default_model
        self._registry = profile_registry

    @property
    def profile_registry(self) -> ProfileRegistry:
        return self._registry

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    @property
    def default_model(self) -> str:
        return self._default_model

    @property
    def context(self) -> AgentContext:
        return self._context

    def build(
        self,
        profile: AgentProfile,
        depth: int = 0,
        on_progress: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ) -> AgentInstance:
        """Materialize a profile into a runnable agent instance.

        Args:
            profile: The agent profile to build.
            depth: Current nesting depth (for subagent recursion limiting).
            on_progress: Progress callback forwarded to SubagentTool.
        """
        # 1. Fresh ToolRegistry from factories
        tools = ToolRegistry()
        for factory in profile.tool_factories:
            tools.register(factory(self._context))

        # 2. Filter skills to only what this profile declares
        allowed_skills = list(profile.inline_skills) + list(profile.loadable_skills)
        if allowed_skills:
            filtered_skills = self._skills_loader.filtered(allowed_skills)
        else:
            filtered_skills = self._skills_loader.filtered([])

        # 3. Register LoadSkillTool if profile has loadable skills
        if profile.loadable_skills:
            from creato.core.tools.filesystem import LoadSkillTool
            tools.register(LoadSkillTool(skills_loader=filtered_skills))

        # 4. Register SubagentTool if depth allows
        subagent_profiles = self._registry.subagent_profiles()
        if subagent_profiles and depth < _MAX_DEPTH:
            from creato.core.tools.subagent import SubagentTool
            # Build a sub-registry containing only subagent profiles
            sub_registry = ProfileRegistry()
            for sp in subagent_profiles:
                sub_registry.register(sp)
            tools.register(SubagentTool(
                factory=self,
                profile_registry=sub_registry,
                provider=self._provider,
                parent_model=profile.model or self._default_model,
                depth=depth,
                on_progress=on_progress,
            ))

        # 5. Build system prompt
        if callable(profile.system_prompt):
            system_prompt = profile.system_prompt(
                skills_loader=filtered_skills,
                tool_names=tools.tool_names,
            )
        else:
            system_prompt = profile.system_prompt

        # 6. Resolve model
        model = profile.model or self._default_model

        return AgentInstance(
            tools=tools,
            system_prompt=system_prompt,
            model=model,
            max_iterations=profile.max_iterations,
        )
