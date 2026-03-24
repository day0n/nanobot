"""Tests for lazy provider exports from creato.providers."""

from __future__ import annotations

import importlib
import sys


def test_importing_providers_package_is_lazy(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "creato.providers", raising=False)
    monkeypatch.delitem(sys.modules, "creato.providers.litellm_provider", raising=False)
    monkeypatch.delitem(sys.modules, "creato.providers.openai_codex_provider", raising=False)
    monkeypatch.delitem(sys.modules, "creato.providers.azure_openai_provider", raising=False)
    monkeypatch.delitem(sys.modules, "creato.providers.openai_provider", raising=False)

    providers = importlib.import_module("creato.providers")

    assert "creato.providers.litellm_provider" not in sys.modules
    assert "creato.providers.openai_codex_provider" not in sys.modules
    assert "creato.providers.azure_openai_provider" not in sys.modules
    assert "creato.providers.openai_provider" not in sys.modules
    assert providers.__all__ == [
        "LLMProvider",
        "LLMResponse",
        "LiteLLMProvider",
        "OpenAICodexProvider",
        "AzureOpenAIProvider",
        "OpenAIProvider",
    ]


def test_explicit_provider_import_still_works(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "creato.providers", raising=False)
    monkeypatch.delitem(sys.modules, "creato.providers.litellm_provider", raising=False)

    namespace: dict[str, object] = {}
    exec("from creato.providers import LiteLLMProvider", namespace)

    assert namespace["LiteLLMProvider"].__name__ == "LiteLLMProvider"
    assert "creato.providers.litellm_provider" in sys.modules
