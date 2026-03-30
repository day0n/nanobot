"""Agent core module.

Heavy imports (AgentLoop, PromptBuilder, SkillsLoader) are lazy —
lightweight consumers like profile discovery don't pay the cost.
"""


def __getattr__(name: str):
    if name == "AgentLoop":
        from creato.core.loop import AgentLoop
        return AgentLoop
    if name == "PromptBuilder":
        from creato.core.prompt import PromptBuilder
        return PromptBuilder
    if name == "SkillsLoader":
        from creato.core.skills import SkillsLoader
        return SkillsLoader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AgentLoop", "PromptBuilder", "SkillsLoader"]
