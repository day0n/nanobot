"""Agent profile — declarative capability definition.

An AgentProfile declares what an agent can do (tools, skills, prompt, model).
Both the main agent and subagents use the same structure.
The AgentFactory materializes a profile into a runnable AgentInstance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from creato.core.tools.base import Tool
from creato.core.tools.registry import ToolRegistry


@dataclass
class AgentContext:
    """Runtime configuration passed to tool factories when building an agent."""

    workspace: Path
    web_search_config: Any  # WebSearchConfig
    web_proxy: str | None
    api_config: Any  # ApiServerConfig
    exec_config: Any  # ExecToolConfig
    restrict_to_workspace: bool
    workflow_dao: Any = None  # WorkflowDAO (optional for non-API mode)
    workflow_engine: Any = None  # WorkflowEngine (optional, requires deploy_id)


@dataclass(frozen=True)
class AgentProfile:
    """Immutable, declarative definition of an agent's capabilities.

    Both main agent and subagents are described by this same structure.
    The difference in lifecycle (session, memory, SSE) is handled by
    the runtime layer (AgentLoop vs SubagentTool), not by the profile.
    """

    name: str
    description: str
    system_prompt: str | Callable[..., str]
    tool_factories: tuple[Callable[[AgentContext], Tool], ...]
    inline_skills: tuple[str, ...] = ()
    loadable_skills: tuple[str, ...] = ()
    model: str | None = None
    max_iterations: int = 40


@dataclass
class AgentInstance:
    """The output of AgentFactory.build() — a fully assembled, runnable agent."""

    tools: ToolRegistry
    system_prompt: str
    model: str
    max_iterations: int


class ProfileRegistry:
    """Registry of named AgentProfiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, AgentProfile] = {}

    def register(self, profile: AgentProfile) -> None:
        self._profiles[profile.name] = profile

    def get(self, name: str) -> AgentProfile | None:
        return self._profiles.get(name)

    def list_profiles(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    @property
    def names(self) -> list[str]:
        return list(self._profiles.keys())

    def subagent_profiles(self) -> list[AgentProfile]:
        """Return all profiles except 'main' (i.e., profiles available as subagents)."""
        return [p for p in self._profiles.values() if p.name != "main"]
