"""
Unit tests for sales websocket router behavior.
"""

from __future__ import annotations

import importlib.util
from unittest.mock import AsyncMock, MagicMock

import pytest

from sales_bot.websocket import router as sales_router


def test_sales_websocket_auth_policy_marks_query_token_as_compatibility_only() -> None:
    assert sales_router.SALES_WS_AUTH_POLICY["formal"] == [
        "authorization_bearer",
        "session_cookie",
    ]
    assert sales_router.SALES_WS_AUTH_POLICY["compatibility"] == ["query_token"]
    assert sales_router.SALES_WS_AUTH_POLICY["reject_close_codes"] == {
        "unauthorized": 4001,
        "owner_mismatch": 4003,
        "kb_lock_unbound": 4410,
        "agent_persona_required": 4411,
        "legacy_sales_runtime_disabled": 4412,
    }


def test_sales_legacy_handler_modules_stay_deleted() -> None:
    assert importlib.util.find_spec("sales_bot.websocket.base_sales_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.enhanced_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.simple_handler") is None


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_when_kb_lock_unbound(monkeypatch):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", None, None)),
    )
    monkeypatch.setattr(
        sales_router,
        "_is_kb_lock_unbound_session",
        AsyncMock(return_value=True),
    )

    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="token",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4410, reason="KB_LOCK_UNBOUND")
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_kb_lock_unbound_session_recomputes_effective_policy_when_snapshot_tampered(
    monkeypatch,
):
    """A persisted snapshot cannot disable connection-time KB-lock enforcement."""

    class DummySession:
        def __init__(self):
            self.voice_policy_snapshot = {
                "tool_policy": {"require_kb_grounding": False},
                "knowledge_base_ids": [],
            }
            self.agent_id = "agent-1"
            self.persona_id = "persona-1"
            self.voice_mode = "stepfun_realtime"
            self.voice_runtime_profile_id = "profile-1"

    session = DummySession()

    class DummyResult:
        def scalar_one_or_none(self):
            return session

    class DummyDbSessionContext:
        committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return DummyResult()

        async def commit(self):
            self.committed = True

    db_context = DummyDbSessionContext()

    class DummyPolicyService:
        def __init__(self, _db):
            pass

        async def resolve_effective_policy(self, **kwargs):
            assert kwargs == {
                "agent_id": "agent-1",
                "persona_id": "persona-1",
                "voice_mode_override": "stepfun_realtime",
                "runtime_profile_override": "profile-1",
            }
            return {
                "tool_policy": {"require_kb_grounding": True},
                "knowledge_base_ids": [],
            }

    monkeypatch.setattr(sales_router, "AsyncSessionLocal", lambda: db_context)
    monkeypatch.setattr(sales_router, "VoiceRuntimePolicyService", DummyPolicyService)

    is_unbound = await sales_router._is_kb_lock_unbound_session("session-1")

    assert is_unbound is True
    assert db_context.committed is True
    assert session.voice_policy_snapshot["tool_policy"]["require_kb_grounding"] is True


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_invalid_token_before_runtime_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_is_kb_lock_unbound_session",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "invalid-token")
    monkeypatch.setattr(sales_router, "_extract_user_id_from_token", lambda _token: None)

    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_legacy_mode_before_runtime_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "legacy", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_is_kb_lock_unbound_session",
        AsyncMock(return_value=False),
    )
    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="legacy",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4412,
        reason="LEGACY_SALES_RUNTIME_DISABLED",
    )
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_non_owner_before_stepfun_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_is_kb_lock_unbound_session",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "valid-token")
    monkeypatch.setattr(sales_router, "_extract_user_id_from_token", lambda _token: "outsider-user")
    monkeypatch.setattr(
        sales_router,
        "_resolve_session_owner_id",
        AsyncMock(return_value="owner-user"),
        raising=False,
    )
    monkeypatch.setattr(sales_router, "_is_admin_user_id", AsyncMock(return_value=False))

    handle_stepfun = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_stepfun_realtime_connection", handle_stepfun)

    await sales_router._handle_sales_websocket(
        websocket=websocket,
        session_id="11111111-1111-1111-1111-111111111111",
        token="",
        agent_id=None,
        persona_id=None,
        voice_mode="stepfun_realtime",
        trace_id="",
    )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4003, reason="ACCESS_DENIED")
    handle_stepfun.assert_not_awaited()
