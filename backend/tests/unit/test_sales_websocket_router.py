"""
Unit tests for sales websocket router behavior.
"""

from __future__ import annotations

import importlib.util
from unittest.mock import AsyncMock, MagicMock

import pytest

from common.services.runtime_gate import RuntimeAdmissionDecision
from sales_bot.websocket import router as sales_router


def test_sales_websocket_auth_policy_marks_query_token_as_compatibility_only() -> None:
    assert sales_router.SALES_WS_AUTH_POLICY["formal"] == [
        "authorization_bearer",
        "session_cookie",
    ]
    assert sales_router.SALES_WS_AUTH_POLICY["compatibility"] == ["query_token"]


def test_sales_legacy_handler_modules_stay_deleted() -> None:
    assert importlib.util.find_spec("sales_bot.websocket.base_sales_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.enhanced_handler") is None
    assert importlib.util.find_spec("sales_bot.websocket.simple_handler") is None


def patch_kb_lock_gate(
    monkeypatch: pytest.MonkeyPatch, *, is_unbound: bool
) -> AsyncMock:
    kb_lock_gate = AsyncMock(return_value=is_unbound)
    monkeypatch.setattr(
        sales_router,
        "_is_kb_lock_unbound_session",
        kb_lock_gate,
    )
    return kb_lock_gate


def sales_admission_ok() -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=True,
        runtime_type="sales",
        classification="voluntary",
    )


def sales_admission_blocked(
    code: str,
    close_code: int,
) -> RuntimeAdmissionDecision:
    return RuntimeAdmissionDecision(
        allowed=False,
        runtime_type="sales",
        classification="terminal",
        code=code,
        close_code=close_code,
        close_reason=code,
        mark_runtime_failed=True,
    )


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_when_kb_lock_unbound(monkeypatch):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    mark_runtime_failed = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "stepfun_realtime", None, None)),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_blocked("KB_LOCK_UNBOUND", 4410)),
    )
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
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
    mark_runtime_failed.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        failure_code="KB_LOCK_UNBOUND",
        source="sales_websocket_reject",
    )
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_kb_lock_unbound_session_uses_runtime_gate_authority(monkeypatch):
    """Sales websocket KB-lock enforcement stays on the shared RuntimeGate seam."""

    class DummyDbSessionContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db_context = DummyDbSessionContext()
    gate_calls: list[object] = []

    class DummyRuntimeGate:
        def __init__(self, db):
            gate_calls.append(db)

        async def is_kb_lock_unbound_for_session_id(self, session_id: str) -> bool:
            assert session_id == "session-1"
            return True

    monkeypatch.setattr(sales_router, "AsyncSessionLocal", lambda: db_context)
    monkeypatch.setattr(sales_router, "RuntimeGate", DummyRuntimeGate)

    is_unbound = await sales_router._is_kb_lock_unbound_session("session-1")

    assert is_unbound is True
    assert gate_calls == [db_context]


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
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_ok()),
    )
    monkeypatch.setattr(sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "invalid-token")
    monkeypatch.setattr(sales_router, "_extract_user_id_from_token", lambda _token: None)
    mark_runtime_failed = AsyncMock()
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )

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
    mark_runtime_failed.assert_not_awaited()
    handle_stepfun.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sales_websocket_rejects_legacy_mode_before_runtime_connect(
    monkeypatch,
):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    mark_runtime_failed = AsyncMock()

    monkeypatch.setattr(
        sales_router,
        "_resolve_session_runtime",
        AsyncMock(return_value=("sales", "legacy", "agent-1", "persona-1")),
    )
    monkeypatch.setattr(
        sales_router,
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_ok()),
    )
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
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
    mark_runtime_failed.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111",
        failure_code="LEGACY_SALES_RUNTIME_DISABLED",
        source="sales_websocket_reject",
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
        "_resolve_sales_admission_decision",
        AsyncMock(return_value=sales_admission_ok()),
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
    mark_runtime_failed = AsyncMock()
    monkeypatch.setattr(
        sales_router,
        "mark_session_runtime_failed",
        mark_runtime_failed,
    )

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
    mark_runtime_failed.assert_not_awaited()
    handle_stepfun.assert_not_awaited()
