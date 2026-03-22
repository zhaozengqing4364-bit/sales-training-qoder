"""
Unit tests for sales websocket router behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sales_bot.websocket import router as sales_router


@pytest.mark.asyncio
async def test_enhanced_connection_init_failure_does_not_fallback_to_simple(monkeypatch):
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    handler = MagicMock()
    handler.initialize = AsyncMock(return_value=False)

    monkeypatch.setattr(sales_router, "create_enhanced_sales_handler", lambda: handler)
    monkeypatch.setattr(sales_router, "_extract_user_id_from_token", lambda _token: "user-1")

    import common.db.session as db_session

    class DummyDbSessionContext:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(db_session, "AsyncSessionLocal", lambda: DummyDbSessionContext())

    await sales_router._handle_enhanced_connection(
        websocket=websocket,
        session_id="session-1",
        token="token",
        agent_id="agent-1",
        persona_id="persona-1",
    )

    handler.initialize.assert_awaited_once()
    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4502, reason="ENHANCED_INIT_FAILED")


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
async def test_handle_sales_websocket_rejects_non_owner_before_enhanced_connect(
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
    monkeypatch.setattr(sales_router, "_resolve_ws_token", lambda *_args, **_kwargs: "valid-token")
    monkeypatch.setattr(sales_router, "_extract_user_id_from_token", lambda _token: "outsider-user")
    monkeypatch.setattr(
        sales_router,
        "_resolve_session_owner_id",
        AsyncMock(return_value="owner-user"),
        raising=False,
    )

    handle_enhanced = AsyncMock()
    monkeypatch.setattr(sales_router, "_handle_enhanced_connection", handle_enhanced)

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
    websocket.close.assert_awaited_once_with(code=4003, reason="ACCESS_DENIED")
    handle_enhanced.assert_not_awaited()
