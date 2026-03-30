"""Researcher subagent profile — declarative definition."""

from __future__ import annotations

from creato.core.profile import AgentContext, AgentProfile
from creato.agents.researcher.prompt import SYSTEM_PROMPT
from creato.core.tools.base import Tool


def _web_search(ctx: AgentContext) -> Tool:
    from creato.core.tools.web import WebSearchTool

    return WebSearchTool(config=ctx.web_search_config, proxy=ctx.web_proxy)


PROFILE = AgentProfile(
    name="researcher",
    description="Research subagent — searches the web to gather information",
    system_prompt=SYSTEM_PROMPT,
    tool_factories=(_web_search,),
    max_iterations=15,
)
