"""Tests for SubagentTool — depth limiting, context propagation, error handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from creato.core.profile import AgentContext, AgentProfile, ProfileRegistry
from creato.core.factory import _MAX_DEPTH
from creato.core.tools.subagent import SubagentTool
from creato.core.tools.registry import ToolRegistry


def _make_registry() -> ProfileRegistry:
    registry = ProfileRegistry()
    registry.register(AgentProfile(
        name="researcher",
        description="test researcher",
        system_prompt="You are a test subagent.",
        tool_factories=(),
        max_iterations=2,
    ))
    return registry


def _make_factory(tmp_path):
    """Create a mock AgentFactory."""
    factory = MagicMock()
    factory.context = AgentContext(
        workspace=tmp_path,
        web_search_config=MagicMock(),
        web_proxy=None,
        api_config=MagicMock(),
        exec_config=MagicMock(),
        restrict_to_workspace=False,
    )
    return factory


class TestSubagentToolDepth:
    @pytest.mark.asyncio
    async def test_depth_limit_returns_error(self, tmp_path):
        tool = SubagentTool(
            factory=_make_factory(tmp_path),
            profile_registry=_make_registry(),
            provider=MagicMock(),
            parent_model="test-model",
            depth=_MAX_DEPTH,
        )
        result = await tool.execute(task="do something", agent_type="researcher")
        assert "Maximum subagent depth" in result

    @pytest.mark.asyncio
    async def test_unknown_type_returns_error(self, tmp_path):
        tool = SubagentTool(
            factory=_make_factory(tmp_path),
            profile_registry=_make_registry(),
            provider=MagicMock(),
            parent_model="test-model",
        )
        result = await tool.execute(task="do something", agent_type="nonexistent")
        assert "Unknown agent type" in result


class TestSubagentToolExecution:
    @pytest.mark.asyncio
    async def test_successful_execution(self, tmp_path):
        from creato.core.executor import ExecutorResult

        mock_result = ExecutorResult(
            content="research complete",
            tools_used=["web_search"],
            messages=[],
            tool_timings={},
            iterations=2,
        )

        factory = _make_factory(tmp_path)
        mock_instance = MagicMock()
        mock_instance.tools = ToolRegistry()
        mock_instance.system_prompt = "test prompt"
        mock_instance.model = "test-model"
        mock_instance.max_iterations = 2
        factory.build.return_value = mock_instance

        with patch("creato.core.tools.subagent.AgentExecutor") as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(return_value=mock_result)

            tool = SubagentTool(
                factory=factory,
                profile_registry=_make_registry(),
                provider=MagicMock(),
                parent_model="test-model",
            )
            result = await tool.execute(task="find info", agent_type="researcher")

        assert "research complete" in result
        assert "subagent:researcher" in result
        assert "2 iterations" in result

    @pytest.mark.asyncio
    async def test_exception_returns_error(self, tmp_path):
        factory = _make_factory(tmp_path)
        mock_instance = MagicMock()
        mock_instance.tools = ToolRegistry()
        mock_instance.system_prompt = "test prompt"
        mock_instance.model = "test-model"
        mock_instance.max_iterations = 2
        factory.build.return_value = mock_instance

        with patch("creato.core.tools.subagent.AgentExecutor") as MockExecutor:
            MockExecutor.return_value.run = AsyncMock(side_effect=RuntimeError("boom"))

            tool = SubagentTool(
                factory=factory,
                profile_registry=_make_registry(),
                provider=MagicMock(),
                parent_model="test-model",
            )
            result = await tool.execute(task="fail", agent_type="researcher")

        assert "Error" in result
        assert "boom" in result
