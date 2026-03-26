"""Provider router — model prefix dispatch, zero string matching.

Model format: "provider_prefix/model_name"
  - "openai/gpt-4.1"              → config.providers.openai      → OpenAIProvider
  - "vertex_gemini/gemini-3-pro"   → config.providers.vertex_gemini → VertexGeminiProvider

Adding a new provider:
  1. Add a config field to ProvidersConfig (schema.py).
  2. Write a Provider class that extends LLMProvider.
  3. If it needs special construction (like VertexGemini), add an isinstance branch below.
     Otherwise it's auto-handled as OpenAI-compatible via ProviderConfig.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from creato.config.schema import Config
    from creato.providers.base import LLMProvider


def resolve(model: str) -> tuple[str, str]:
    """Parse 'prefix/model_name' → (prefix, model_name).

    Pure split — no keyword matching, no heuristics.
    """
    if "/" not in model:
        raise ValueError(
            f"Model must include provider prefix: 'provider/model', got '{model}'"
        )
    return model.split("/", 1)


def create_provider(config: "Config", model: str | None = None) -> "LLMProvider":
    """Create a provider instance from config.

    Dispatch is by isinstance on the config object — not by string matching
    on the model name.
    """
    from creato.config.schema import VertexGeminiConfig
    from creato.providers.base import GenerationSettings

    model = model or config.agents.defaults.model
    prefix, model_name = resolve(model)

    provider_cfg = getattr(config.providers, prefix, None)
    if provider_cfg is None:
        available = sorted(
            f for f in config.providers.model_fields if f != "model_config"
        )
        raise ValueError(
            f"No provider config for '{prefix}'. Available: {available}"
        )

    # --- isinstance dispatch on config type ---

    if isinstance(provider_cfg, VertexGeminiConfig):
        from creato.providers.vertex_gemini_provider import VertexGeminiProvider

        if not provider_cfg.oc_json or not provider_cfg.project:
            raise ValueError("vertex_gemini requires oc_json and project")
        provider = VertexGeminiProvider(
            oc_json_b64=provider_cfg.oc_json,
            project=provider_cfg.project,
            location=provider_cfg.location,
            default_model=model_name,
        )
    else:
        # ProviderConfig → OpenAI-compatible
        from creato.providers.openai_provider import OpenAIProvider

        if not provider_cfg.api_key:
            raise ValueError(f"Provider '{prefix}' requires api_key")
        provider = OpenAIProvider(
            api_key=provider_cfg.api_key,
            api_base=provider_cfg.api_base,
            default_model=model_name,
            extra_headers=provider_cfg.extra_headers,
        )

    d = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=d.temperature,
        max_tokens=d.max_tokens,
        reasoning_effort=d.reasoning_effort,
    )
    return provider
