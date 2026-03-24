"""PromptBuilder — assembles system prompt and messages for the agent.

Prompt assembly order:
1. Identity layer     — build_identity() from identity.py
2. Guidelines layer   — TOOL_GUIDELINES from guidelines.py
3. Skills layer       — always-on skills + skills summary from SkillsLoader
4. (future) Memory layer — long-term memory injection point

The runtime context (time, channel, flow_id) is NOT in the system prompt.
It is prepended to the user message via build_runtime_context().
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from nanobot.agent.prompt.identity import build_identity
from nanobot.agent.prompt.guidelines import TOOL_GUIDELINES
from nanobot.agent.prompt.runtime import build_runtime_context
from nanobot.agent.skills import SkillsLoader
from nanobot.utils.helpers import build_assistant_message, detect_image_mime


class PromptBuilder:
    """Builds the system prompt and message list for the agent."""

    def __init__(self, workspace: Path, skills_loader: SkillsLoader | None = None):
        self.workspace = workspace
        self.skills = skills_loader or SkillsLoader()
        self._tool_names: list[str] | None = None

    def set_tool_names(self, names: list[str]) -> None:
        """Set the currently registered tool names (called by AgentLoop after tool registration)."""
        self._tool_names = names

    def build_system_prompt(self) -> str:
        """Build the full system prompt. This output is cacheable (no time-varying data)."""
        workspace_path = str(self.workspace.expanduser().resolve())
        parts = [build_identity(workspace_path, tool_names=self._tool_names)]

        parts.append(TOOL_GUIDELINES)

        # Always-on skills (injected into every request)
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        # Skills summary (progressive loading — agent loads full skill via load_skill tool)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(
                "# Skills\n\n"
                "The following skills extend your capabilities. "
                "To use a skill, call the `load_skill` tool with the skill name.\n"
                "Skills with available=\"false\" need dependencies installed first "
                "- you can try installing them with apt/brew.\n\n"
                + skills_summary
            )

        return "\n\n---\n\n".join(parts)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        current_role: str = "user",
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call."""
        runtime_ctx = build_runtime_context(channel, chat_id, metadata)
        user_content = self._build_user_content(current_message, media)

        # Merge runtime context and user content into a single user message
        # to avoid consecutive same-role messages that some providers reject.
        if isinstance(user_content, str):
            merged = f"{runtime_ctx}\n\n{user_content}"
        else:
            merged = [{"type": "text", "text": runtime_ctx}] + user_content

        return [
            {"role": "system", "content": self.build_system_prompt()},
            *history,
            {"role": current_role, "content": merged},
        ]

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            # Detect real MIME type from magic bytes; fallback to filename guess
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "_meta": {"path": str(p)},
            })

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    @staticmethod
    def add_tool_result(
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages

    @staticmethod
    def add_assistant_message(
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        messages.append(build_assistant_message(
            content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        ))
        return messages
