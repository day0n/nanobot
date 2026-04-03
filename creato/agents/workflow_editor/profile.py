"""Workflow-editor subagent profile — declarative definition."""

from __future__ import annotations

from creato.core.profile import AgentContext, AgentProfile
from creato.agents.workflow_editor.prompt import build_workflow_editor_system_prompt
from creato.core.tools.base import Tool


# ── Tool factories ──────────────────────────────────────────────────

def _get_workflow(ctx: AgentContext) -> Tool:
    from creato.core.tools.opencreator import GetWorkflowTool

    return GetWorkflowTool(workflow_dao=ctx.workflow_dao)


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
    name="workflow-editor",
    description=(
        "Workflow editor subagent — reads, plans, and edits "
        "OpenCreator workflows on the canvas"
    ),
    system_prompt=build_workflow_editor_system_prompt,
    tool_factories=(
        _get_workflow,
        _get_node_spec,
        _edit_workflow,
    ),
    inline_skills=("edit-workflow",),
    loadable_skills=(),
    max_iterations=20,
)
