"""Tests for current session storage and reset semantics."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from creato.bus.events import InboundMessage
from creato.providers.base import LLMResponse
from creato.session.manager import Session, SessionManager


def create_session_with_messages(key: str, count: int, role: str = "user") -> Session:
    """Create a session populated with predictable message content."""
    session = Session(key=key)
    for i in range(count):
        session.add_message(role, f"msg{i}")
    return session


def _write_session_file(path: Path, key: str, messages: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"_type": "metadata", "key": key, "created_at": "2026-01-01T00:00:00"}) + "\n")
        for message in messages:
            handle.write(json.dumps(message) + "\n")


class TestSessionPersistence:
    def test_persistence_roundtrip(self, tmp_path) -> None:
        manager = SessionManager(Path(tmp_path))
        session1 = create_session_with_messages("test:persistence", 20)
        manager.save(session1)

        session2 = manager.get_or_create("test:persistence")
        assert len(session2.messages) == 20
        assert session2.messages[0]["content"] == "msg0"
        assert session2.messages[-1]["content"] == "msg19"

    def test_get_history_after_reload(self, tmp_path) -> None:
        manager = SessionManager(Path(tmp_path))
        session1 = create_session_with_messages("test:reload", 30)
        manager.save(session1)

        session2 = manager.get_or_create("test:reload")
        history = session2.get_history(max_messages=10)
        assert len(history) == 10
        assert history[0]["content"] == "msg20"
        assert history[-1]["content"] == "msg29"

    def test_clear_resets_session(self) -> None:
        session = create_session_with_messages("test:clear", 10)
        session.clear()
        assert session.messages == []


class TestUserScopedStorage:
    def test_api_sessions_are_saved_under_user_directory(self, tmp_path) -> None:
        manager = SessionManager(Path(tmp_path))
        session = create_session_with_messages("api:user-123:thread-1", 3)

        manager.save(session)

        assert (tmp_path / "sessions" / "user-123" / "api_user-123_thread-1.jsonl").exists()

    def test_api_flow_sessions_are_saved_under_user_directory(self, tmp_path) -> None:
        manager = SessionManager(Path(tmp_path))
        session = create_session_with_messages("api:user-123:flow:flow-456:thread-1", 3)

        manager.save(session)

        assert (
            tmp_path
            / "sessions"
            / "user-123"
            / "api_user-123_flow_flow-456_thread-1.jsonl"
        ).exists()

    def test_flat_workspace_session_migrates_to_user_directory(self, tmp_path) -> None:
        manager = SessionManager(Path(tmp_path))
        messages = [{"role": "user", "content": "hello", "timestamp": "2026-01-01T00:00:00"}]
        flat_path = tmp_path / "sessions" / "api_user-123_thread-1.jsonl"
        _write_session_file(flat_path, "api:user-123:thread-1", messages)

        session = manager.get_or_create("api:user-123:thread-1")

        assert session.messages == messages
        assert not flat_path.exists()
        assert (tmp_path / "sessions" / "user-123" / "api_user-123_thread-1.jsonl").exists()

    def test_legacy_global_session_migrates_to_user_directory(self, tmp_path, monkeypatch) -> None:
        legacy_dir = tmp_path / "legacy-sessions"
        monkeypatch.setattr("creato.session.manager.get_legacy_sessions_dir", lambda: legacy_dir)
        manager = SessionManager(Path(tmp_path))
        messages = [{"role": "user", "content": "hello", "timestamp": "2026-01-01T00:00:00"}]
        legacy_path = legacy_dir / "api_user-123_thread-2.jsonl"
        _write_session_file(legacy_path, "api:user-123:thread-2", messages)

        session = manager.get_or_create("api:user-123:thread-2")

        assert session.messages == messages
        assert not legacy_path.exists()
        assert (tmp_path / "sessions" / "user-123" / "api_user-123_thread-2.jsonl").exists()

    def test_list_sessions_reports_user_directory(self, tmp_path) -> None:
        manager = SessionManager(Path(tmp_path))
        manager.save(create_session_with_messages("api:user-123:thread-1", 1))
        manager.save(create_session_with_messages("cli:direct", 1))

        sessions = manager.list_sessions()
        by_key = {session["key"]: session for session in sessions}

        assert by_key["api:user-123:thread-1"]["user_id"] == "user-123"
        assert by_key["cli:direct"]["user_id"] == "_local"


class TestSessionRuntime:
    def test_get_history_does_not_mutate_messages(self) -> None:
        session = create_session_with_messages("test:history", 10)
        original = [message.copy() for message in session.messages]

        history = session.get_history(max_messages=4)

        assert len(history) == 4
        assert session.messages == original

    @staticmethod
    def _make_loop(tmp_path: Path):
        from creato.agent.loop import AgentLoop

        provider = MagicMock()
        provider.get_default_model.return_value = "test-model"
        provider.estimate_prompt_tokens.return_value = (10_000, "test")
        provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="ok", tool_calls=[]))

        loop = AgentLoop(
            provider=provider,
            workspace=tmp_path,
            model="test-model",
            context_window_tokens=1,
        )
        loop.tools.get_definitions = MagicMock(return_value=[])
        return loop

    @pytest.mark.asyncio
    async def test_new_clears_session_and_returns_confirmation(self, tmp_path: Path) -> None:
        loop = self._make_loop(tmp_path)
        session = loop.sessions.get_or_create("cli:test")
        for i in range(3):
            session.add_message("user", f"msg{i}")
            session.add_message("assistant", f"resp{i}")
        loop.sessions.save(session)

        response = await loop._process_message(
            InboundMessage(channel="cli", sender_id="user", chat_id="test", content="/new")
        )

        assert response is not None
        assert response.content == "New session started."
        assert loop.sessions.get_or_create("cli:test").messages == []

        await loop.close_mcp()
