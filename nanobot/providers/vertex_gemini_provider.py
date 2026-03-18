"""Vertex AI Gemini provider — authenticates via service account JSON.

Uses google-genai SDK (same as opencreator-consumer). Preview models (Gemini 3.x)
require location='global'; GA models use the configured region.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest

# Preview models that require location='global' on Vertex AI
_PREVIEW_MODELS = {
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
}


def _is_preview_model(model: str) -> bool:
    return model in _PREVIEW_MODELS or "preview" in model.lower()


def _make_thought_part(thought_text: str, thought_signature_b64: str):
    """Reconstruct a Gemini thought Part with its thought_signature."""
    from google.genai.types import Part
    sig_bytes = base64.b64decode(thought_signature_b64)
    return Part(thought=True, text=thought_text, thought_signature=sig_bytes)


def _sig_map_from_thinking_blocks(thinking_blocks: list[dict]) -> dict[str, bytes]:
    """Build a {tool_name: thought_signature_bytes} map from stored thinking_blocks."""
    result = {}
    for block in thinking_blocks:
        if block.get("type") == "gemini_fc_signature":
            name = block.get("tool_name", "")
            sig_b64 = block.get("thought_signature", "")
            if name and sig_b64:
                try:
                    result[name] = base64.b64decode(sig_b64)
                except Exception:
                    pass
    return result


class VertexGeminiProvider(LLMProvider):
    """Vertex AI Gemini provider using google-genai SDK with service account credentials.

    Supported models (set in agents.defaults.model):
      gemini-2.0-flash
      gemini-2.0-flash-lite
      gemini-3-flash-preview   (auto-routes to location=global)
      gemini-3.1-pro-preview   (auto-routes to location=global)
      gemini-3.1-flash-lite-preview  (auto-routes to location=global)

    Config (~/.nanobot/config.json):
      {
        "providers": {
          "vertexGemini": {
            "ocJson": "<base64-encoded service account JSON>",
            "project": "my-gcp-project-id",
            "location": "us-central1"
          }
        },
        "agents": { "defaults": { "model": "gemini-2.0-flash" } }
      }
    """

    def __init__(
        self,
        oc_json_b64: str,
        project: str,
        location: str = "us-central1",
        default_model: str = "gemini-2.0-flash",
    ):
        super().__init__(api_key=None, api_base=None)
        self.default_model = default_model
        self._project = project
        self._location = location

        try:
            self._credentials_json = base64.b64decode(oc_json_b64).decode("utf-8")
            self._service_account_info = json.loads(self._credentials_json)
        except Exception as e:
            raise ValueError(
                f"Invalid ocJson: must be base64-encoded service account JSON — {e}"
            ) from e

    def get_default_model(self) -> str:
        return self.default_model

    def _make_client(self, preview: bool = False):
        """Create a google-genai Vertex AI client."""
        from google import genai
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials = service_account.Credentials.from_service_account_info(
            self._service_account_info, scopes=scopes
        )
        credentials.refresh(Request())

        location = "global" if preview else self._location
        return genai.Client(
            vertexai=True,
            credentials=credentials,
            project=self._project,
            location=location,
        )

    @lru_cache(maxsize=2)
    def _get_client(self, preview: bool):
        return self._make_client(preview=preview)

    def _messages_to_contents(self, messages: list[dict[str, Any]]) -> tuple[list, str | None]:
        """Convert OpenAI-style messages to google-genai Contents + system prompt."""
        from google.genai.types import Content, Part

        system_prompt = None
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                if isinstance(content, str):
                    system_prompt = (system_prompt or "") + content
                elif isinstance(content, list):
                    texts = [p["text"] for p in content if p.get("type") == "text"]
                    system_prompt = (system_prompt or "") + "\n".join(texts)
                continue

            genai_role = "model" if role == "assistant" else "user"

            parts = []
            if isinstance(content, str):
                if content:
                    parts.append(Part.from_text(text=content))
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        parts.append(Part.from_text(text=part["text"]))

            if role == "assistant" and msg.get("tool_calls"):
                # Build a {tool_name: thought_signature_bytes} lookup from thinking_blocks
                sig_map = _sig_map_from_thinking_blocks(msg.get("thinking_blocks") or [])
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    from google.genai.types import FunctionCall
                    fc_name = fn.get("name", "")
                    fc_part = Part(function_call=FunctionCall(name=fc_name, args=args))
                    # Restore thought_signature on the functionCall Part (Gemini 3.x requirement)
                    sig_bytes = sig_map.get(fc_name)
                    if sig_bytes:
                        try:
                            fc_part = Part(
                                function_call=FunctionCall(name=fc_name, args=args),
                                thought_signature=sig_bytes,
                            )
                        except Exception:
                            pass  # SDK version doesn't support it; send without
                    parts.append(fc_part)

            # Restore text thought parts saved from previous turns
            if role == "assistant" and msg.get("thinking_blocks"):
                for block in msg["thinking_blocks"]:
                    if block.get("type") == "gemini_thought":
                        thought_text = block.get("thinking", "")
                        thought_sig = block.get("thought_signature", "")
                        parts.insert(0, Part(
                            thought=True,
                            text=thought_text,
                        ) if not thought_sig else _make_thought_part(thought_text, thought_sig))

            if role == "tool":
                from google.genai.types import FunctionResponse
                try:
                    result = json.loads(content) if isinstance(content, str) else content
                except Exception:
                    result = {"result": str(content)}
                parts.append(
                    Part(
                        function_response=FunctionResponse(
                            name=msg.get("name", "tool"),
                            response=result if isinstance(result, dict) else {"result": result},
                        )
                    )
                )
                genai_role = "user"

            if parts:
                if contents and contents[-1].role == genai_role:
                    contents[-1].parts.extend(parts)
                else:
                    contents.append(Content(role=genai_role, parts=parts))

        return contents, system_prompt

    def _tools_to_genai(self, tools: list[dict[str, Any]]) -> list:
        """Convert OpenAI-style tools to google-genai FunctionDeclarations."""
        from google.genai.types import FunctionDeclaration, Tool as GenaiTool

        declarations = []
        for t in tools:
            fn = t.get("function", {})
            declarations.append(
                FunctionDeclaration(
                    name=fn.get("name", ""),
                    description=fn.get("description", ""),
                    parameters=fn.get("parameters", {}),
                )
            )
        return [GenaiTool(function_declarations=declarations)]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        from google.genai.types import GenerateContentConfig

        model_name = model or self.default_model
        preview = _is_preview_model(model_name)
        client = self._get_client(preview)

        contents, system_prompt = self._messages_to_contents(messages)

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if tools:
            config_kwargs["tools"] = self._tools_to_genai(tools)

        config = GenerateContentConfig(**config_kwargs)

        logger.debug(
            "VertexGemini {} (project={}, location={}, preview={})",
            model_name, self._project, "global" if preview else self._location, preview,
        )

        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate:
                return LLMResponse(content="", finish_reason="stop")

            tool_calls = []
            text_parts = []
            thinking_blocks = []
            for part in (candidate.content.parts or []):
                # Thought parts (text thinking) — preserved for completeness
                if getattr(part, "thought", False):
                    block: dict[str, Any] = {"type": "gemini_thought", "thinking": part.text or ""}
                    try:
                        sig = part.thought_signature  # bytes
                        if sig:
                            block["thought_signature"] = base64.b64encode(sig).decode()
                    except Exception:
                        pass
                    thinking_blocks.append(block)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append(ToolCallRequest(
                        id=f"call_{fc.name}",
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    ))
                    # Gemini 3.x: thought_signature lives ON the functionCall Part.
                    # Capture it so we can echo it back verbatim in subsequent turns.
                    try:
                        sig = part.thought_signature  # bytes | None
                        if sig:
                            thinking_blocks.append({
                                "type": "gemini_fc_signature",
                                "tool_name": fc.name,
                                "thought_signature": base64.b64encode(sig).decode(),
                            })
                    except Exception:
                        pass
                elif hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            finish_reason = "tool_calls" if tool_calls else "stop"
            content = "".join(text_parts)

            return LLMResponse(
                content=content,
                finish_reason=finish_reason,
                tool_calls=tool_calls,
                thinking_blocks=thinking_blocks or None,
            )

        except Exception as e:
            logger.error("VertexGemini error for {}: {}", model_name, e)
            return LLMResponse(
                content=f"Error calling Vertex Gemini: {e}",
                finish_reason="error",
            )
