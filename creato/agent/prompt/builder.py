"""PromptBuilder — assembles system prompt and messages for the agent.

Prompt assembly order:
1. Identity + guidelines layer — build_identity() from identity.py
2. Skills layer                — always-on skills + skills summary from SkillsLoader

The system prompt contains ONLY static content (identity + skills) so that
provider-level prompt caching can hit on every request.

Dynamic per-request context is injected into the messages list instead:
- Runtime context (time, channel, flow_id) → prepended to the user message
- Context summary (compressed dropped history) → separate user message before history
- Long-term memory → separate user message before history
"""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from creato.agent.prompt.identity import build_identity
from creato.agent.prompt.runtime import build_runtime_context
from creato.agent.skills import SkillsLoader
from creato.utils.helpers import build_assistant_message, detect_image_mime


class PromptBuilder:
    """Builds the system prompt and message list for the agent."""

    def __init__(self, workspace: Path, skills_loader: SkillsLoader | None = None):
        self.workspace = workspace
        self.skills = skills_loader or SkillsLoader()
        self._tool_names: list[str] | None = None
        self._cached_system_prompt: str | None = None

    def set_tool_names(self, names: list[str]) -> None:
        """Set the currently registered tool names (called by AgentLoop after tool registration)."""
        self._tool_names = names
        self._cached_system_prompt = None  # invalidate cache

    def build_system_prompt(self) -> str:
        """Build the full system prompt. This output is cacheable (no time-varying data)."""
        if self._cached_system_prompt is not None:
            return self._cached_system_prompt

        parts = [build_identity(tool_names=self._tool_names)]

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

        self._cached_system_prompt = "\n\n---\n\n".join(parts)
        return self._cached_system_prompt

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
        memory_context: str | None = None,
        context_summary: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build the complete message list for an LLM call.

        Dynamic context (context_summary, memory_context) is injected as a
        separate user message BEFORE history, keeping the system prompt purely
        static so provider-level prompt caching hits reliably.
        """
        runtime_ctx = build_runtime_context(channel, chat_id, metadata)
        user_content = self._build_user_content(current_message, media)

        # Merge runtime context and user content into a single user message
        # to avoid consecutive same-role messages that some providers reject.
        if isinstance(user_content, str):
            merged = f"{runtime_ctx}\n\n{user_content}"
        else:
            merged = [{"type": "text", "text": runtime_ctx}] + user_content

        system = self.build_system_prompt()

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

        # Inject dynamic context as a separate user message before history.
        # This keeps the system prompt hash stable for prompt caching while
        # still giving the model access to conversation summary and user memory.
        dynamic_parts: list[str] = []
        if context_summary:
            dynamic_parts.append(
                "# Earlier Conversation Summary\n\n" + context_summary
            )
        if memory_context:
            dynamic_parts.append(
                "# What You Know About This User\n\n"
                "The following are facts you remember about this user "
                "from previous conversations. "
                "Use them to provide personalized, context-aware responses.\n\n"
                + memory_context
            )
        if dynamic_parts:
            messages.append({
                "role": "user",
                "content": "\n\n---\n\n".join(dynamic_parts),
            })

        messages.extend(history)
        messages.append({"role": current_role, "content": merged})
        return messages

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
