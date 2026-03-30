"""Main agent profile — declarative definition."""

from __future__ import annotations

from creato.core.profile import AgentContext, AgentProfile
from creato.agents.main.prompt import build_main_system_prompt
from creato.core.tools.base import Tool


# ── Tool factories ──────────────────────────────────────────────────

def _read_file(ctx: AgentContext) -> Tool:
    from creato.core.skills import BUILTIN_SKILLS_DIR
    from creato.core.tools.filesystem import ReadFileTool

    allowed_dir = ctx.workspace if ctx.restrict_to_workspace else None
    extra_read = [BUILTIN_SKILLS_DIR] if allowed_dir else None
    return ReadFileTool(
        workspace=ctx.workspace,
        allowed_dir=allowed_dir,
        extra_allowed_dirs=extra_read,
    )


def _web_search(ctx: AgentContext) -> Tool:
    from creato.core.tools.web import WebSearchTool

    return WebSearchTool(config=ctx.web_search_config, proxy=ctx.web_proxy)


def _web_fetch(ctx: AgentContext) -> Tool:
    from creato.core.tools.web import WebFetchTool

    return WebFetchTool(proxy=ctx.web_proxy)


def _get_workflow(ctx: AgentContext) -> Tool:
    from creato.core.tools.opencreator import GetWorkflowTool

    return GetWorkflowTool(workflow_dao=ctx.workflow_dao)


def _get_workflow_results(ctx: AgentContext) -> Tool:
    from creato.core.tools.opencreator import GetWorkflowResultsTool

    return GetWorkflowResultsTool(workflow_dao=ctx.workflow_dao)


def _get_node_spec(ctx: AgentContext) -> Tool:
    from creato.core.tools.opencreator import GetNodeSpecTool

    return GetNodeSpecTool()


def _edit_workflow(ctx: AgentContext) -> Tool:
    from creato.core.tools.opencreator import EditWorkflowTool

    return EditWorkflowTool(
        workflow_dao=ctx.workflow_dao,
        editor_base=ctx.api_config.editor_base,
    )


# ── Profile ─────────────────────────────────────────────────────────

PROFILE = AgentProfile(
    name="main",
    description="Primary conversational agent with full tool access",
    system_prompt=build_main_system_prompt,
    tool_factories=(
        _read_file,
        _web_search,
        _web_fetch,
        _get_workflow,
        _get_workflow_results,
        _get_node_spec,
        _edit_workflow,
    ),
    inline_skills=("edit-workflow",),
    loadable_skills=("weather", "summarize", "workflow-user-guide"),
    max_iterations=40,
)
