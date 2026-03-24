"""Tests for the direct OpenAI provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from creato.providers.openai_provider import (
    OpenAIProvider,
    _is_reasoning_model,
    _uses_max_completion_tokens,
)


# ---------------------------------------------------------------------------
# _is_reasoning_model / _uses_max_completion_tokens
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model,expected", [
    ("o3", True),
    ("o3-mini", True),
    ("o4-mini", True),
    ("o1-preview", True),
    ("openai/o3", True),
    ("gpt-5", False),
    ("gpt-4.1", False),
    ("gpt-4o", False),
    ("claude-3.5-sonnet", False),
])
def test_is_reasoning_model(model, expected):
    assert _is_reasoning_model(model) is expected


@pytest.mark.parametrize("model,expected", [
    ("o3", True),
    ("o4-mini", True),
    ("gpt-5", True),
    ("gpt-5-turbo", True),
    ("gpt-4.1", True),
    ("gpt-4.1-mini", True),
    ("gpt-4o", False),       # legacy model, uses max_tokens
    ("gpt-4-turbo", False),  # legacy model
])
def test_uses_max_completion_tokens(model, expected):
    assert _uses_max_completion_tokens(model) is expected


# ---------------------------------------------------------------------------
# _strip_provider_prefix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model,expected", [
    ("openai/o3", "o3"),
    ("openai/gpt-4.1", "gpt-4.1"),
    ("o3", "o3"),
    ("gpt-4o", "gpt-4o"),
])
def test_strip_provider_prefix(model, expected):
    assert OpenAIProvider._strip_provider_prefix(model) == expected


# ---------------------------------------------------------------------------
# _build_kwargs
# ---------------------------------------------------------------------------

def test_build_kwargs_standard_model():
    provider = OpenAIProvider(api_key="sk-test", default_model="gpt-4o")
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None, model=None, max_tokens=2048,
        temperature=0.5, reasoning_effort=None, tool_choice=None,
    )
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["max_tokens"] == 2048
    assert kwargs["temperature"] == 0.5
    assert "max_completion_tokens" not in kwargs


def test_build_kwargs_gpt5_uses_max_completion_tokens():
    """GPT-5 uses max_completion_tokens but still supports temperature."""
    provider = OpenAIProvider(api_key="sk-test", default_model="gpt-5")
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None, model=None, max_tokens=8192,
        temperature=0.1, reasoning_effort=None, tool_choice=None,
    )
    assert kwargs["model"] == "gpt-5"
    assert kwargs["max_completion_tokens"] == 8192
    assert kwargs["temperature"] == 0.1  # GPT-5 supports temperature
    assert "max_tokens" not in kwargs


def test_build_kwargs_gpt41_uses_max_completion_tokens():
    """GPT-4.1 uses max_completion_tokens but still supports temperature."""
    provider = OpenAIProvider(api_key="sk-test", default_model="gpt-4.1-mini")
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None, model=None, max_tokens=4096,
        temperature=0.3, reasoning_effort=None, tool_choice=None,
    )
    assert kwargs["max_completion_tokens"] == 4096
    assert kwargs["temperature"] == 0.3
    assert "max_tokens" not in kwargs


def test_build_kwargs_reasoning_model():
    provider = OpenAIProvider(api_key="sk-test", default_model="o3")
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None, model=None, max_tokens=4096,
        temperature=0.7, reasoning_effort=None, tool_choice=None,
    )
    assert kwargs["model"] == "o3"
    assert kwargs["max_completion_tokens"] == 4096
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs  # reasoning models skip temperature


def test_build_kwargs_with_reasoning_effort():
    provider = OpenAIProvider(api_key="sk-test", default_model="gpt-4.1")
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None, model="gpt-4.1", max_tokens=4096,
        temperature=0.7, reasoning_effort="high", tool_choice=None,
    )
    assert kwargs["reasoning_effort"] == "high"
    assert "temperature" not in kwargs  # reasoning_effort implies reasoning mode
    assert kwargs["max_completion_tokens"] == 4096


def test_build_kwargs_strips_openai_prefix():
    provider = OpenAIProvider(api_key="sk-test", default_model="openai/gpt-4.1")
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None, model=None, max_tokens=1024,
        temperature=0.3, reasoning_effort=None, tool_choice=None,
    )
    assert kwargs["model"] == "gpt-4.1"  # prefix stripped


def test_build_kwargs_with_tools():
    provider = OpenAIProvider(api_key="sk-test")
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    kwargs = provider._build_kwargs(
        messages=[{"role": "user", "content": "weather?"}],
        tools=tools, model="gpt-4.1", max_tokens=1024,
        temperature=0.5, reasoning_effort=None, tool_choice=None,
    )
    assert kwargs["tools"] == tools
    assert kwargs["tool_choice"] == "auto"


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------

def _mock_chat_response(content="Hello!", finish_reason="stop", tool_calls=None, usage=None):
    """Build a mock OpenAI ChatCompletion response."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
        reasoning_content=None,
    )
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    u = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15) if usage is None else usage
    return SimpleNamespace(choices=[choice], usage=u)


@pytest.mark.asyncio
async def test_chat_success():
    provider = OpenAIProvider(api_key="sk-test", default_model="gpt-4.1")
    mock_response = _mock_chat_response(content="Hi there!")

    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.chat([{"role": "user", "content": "hello"}])

    assert result.content == "Hi there!"
    assert result.finish_reason == "stop"
    assert result.usage["total_tokens"] == 15


@pytest.mark.asyncio
async def test_chat_with_tool_calls():
    tc = SimpleNamespace(
        id="call_abc",
        function=SimpleNamespace(name="get_weather", arguments='{"city": "SF"}'),
    )
    mock_response = _mock_chat_response(content=None, finish_reason="tool_calls", tool_calls=[tc])

    provider = OpenAIProvider(api_key="sk-test")
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.chat(
            [{"role": "user", "content": "weather?"}],
            tools=[{"type": "function", "function": {"name": "get_weather", "parameters": {}}}],
        )

    assert result.finish_reason == "tool_calls"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "get_weather"
    assert result.tool_calls[0].arguments == {"city": "SF"}


@pytest.mark.asyncio
async def test_chat_empty_choices():
    provider = OpenAIProvider(api_key="sk-test")
    mock_response = SimpleNamespace(choices=[], usage=None)

    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_response):
        result = await provider.chat([{"role": "user", "content": "hi"}])

    assert result.finish_reason == "error"
    assert "empty choices" in result.content


@pytest.mark.asyncio
async def test_chat_api_error():
    provider = OpenAIProvider(api_key="sk-test")

    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock, side_effect=Exception("rate limit")):
        result = await provider.chat([{"role": "user", "content": "hi"}])

    assert result.finish_reason == "error"
    assert "rate limit" in result.content


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

def test_registry_matches_openai_models():
    from creato.providers.registry import find_by_model

    for model in ("gpt-4.1", "gpt-4o", "gpt-5", "o3", "o3-mini", "o4-mini", "o1-preview"):
        spec = find_by_model(model)
        assert spec is not None, f"{model} should match a provider"
        assert spec.name == "openai", f"{model} should match openai, got {spec.name}"
        assert spec.is_direct is True
