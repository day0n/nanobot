"""System-prompt builder for the main agent.

Extracts the assembly logic that previously lived inside
``PromptBuilder.build_system_prompt()`` so that it can be called as a
plain function from the ``AgentProfile.system_prompt`` callable.
"""

from __future__ import annotations

from creato.core.prompt.identity import build_identity
from creato.core.skills import SkillsLoader


def build_main_system_prompt(
    skills_loader: SkillsLoader | None = None,
    tool_names: list[str] | None = None,
) -> str:
    """Assemble the full system prompt for the main agent.

    Mirrors the logic of ``PromptBuilder.build_system_prompt()`` but as a
    standalone function suitable for use as ``AgentProfile.system_prompt``.
    """
    skills = skills_loader or SkillsLoader()

    parts = [build_identity(tool_names=tool_names)]

    # Always-on skills
    always_skills = skills.get_always_skills()
    if always_skills:
        always_content = skills.load_skills_for_context(always_skills)
        if always_content:
            parts.append(f"# Active Skills\n\n{always_content}")

    # Skills summary (progressive loading)
    skills_summary = skills.build_skills_summary()
    if skills_summary:
        parts.append(
            "# Skills\n\n"
            "The following skills extend your capabilities. "
            "To use a skill, call the `load_skill` tool with the skill name.\n"
            'Skills with available="false" need dependencies installed first '
            "- you can try installing them with apt/brew.\n\n"
            + skills_summary
        )

    return "\n\n---\n\n".join(parts)
