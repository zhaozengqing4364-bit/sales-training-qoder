"""Unit tests for presentation websocket runtime routing in main.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.auth.service import JWTError

import main


@pytest.mark.asyncio
async def test_presentation_ws_uses_persisted_legacy_mode_and_registers_session() -> None:
    session_id = str(uuid.uuid4())
    websocket = MagicMock()
    websocket.headers = {}
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    legacy_handler = MagicMock()
    legacy_handler.handle_connection = AsyncMock()
    stepfun_handler = MagicMock()
    stepfun_handler.handle_connection = AsyncMock()

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    with (
        patch(
            "main._resolve_presentation_runtime",
            new=AsyncMock(return_value=("presentation", "legacy")),
        ),
        patch(
            "main._is_presentation_kb_lock_unbound_session",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.PresentationWebSocketHandler",
            return_value=legacy_handler,
        ),
        patch(
            "presentation_coach.websocket.presentation_stepfun_realtime_handler.PresentationStepFunRealtimeHandler",
            return_value=stepfun_handler,
        ),
        patch(
            "common.websocket.session_manager.get_session_manager",
            return_value=session_manager,
        ),
        patch("common.auth.service.verify_token", return_value={"sub": "user-123"}),
    ):
        await main._handle_presentation_websocket(
            websocket=websocket,
            session_id=session_id,
            token="query-token",
            voice_mode="stepfun_realtime",
        )

    session_manager.register_session.assert_awaited_once_with(
        session_id,
        legacy_handler,
        user_id="user-123",
    )
    legacy_handler.handle_connection.assert_awaited_once_with(
        websocket,
        session_id,
        "query-token",
        trace_id=None,
    )
    stepfun_handler.handle_connection.assert_not_called()
    session_manager.unregister_session.assert_awaited_once_with(session_id)


@pytest.mark.asyncio
async def test_presentation_ws_uses_persisted_stepfun_mode() -> None:
    session_id = str(uuid.uuid4())
    websocket = MagicMock()
    websocket.headers = {}
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    legacy_handler = MagicMock()
    legacy_handler.handle_connection = AsyncMock()
    stepfun_handler = MagicMock()
    stepfun_handler.handle_connection = AsyncMock()

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    with (
        patch(
            "main._resolve_presentation_runtime",
            new=AsyncMock(return_value=("presentation", "stepfun_realtime")),
        ),
        patch(
            "main._is_presentation_kb_lock_unbound_session",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.PresentationWebSocketHandler",
            return_value=legacy_handler,
        ),
        patch(
            "presentation_coach.websocket.presentation_stepfun_realtime_handler.PresentationStepFunRealtimeHandler",
            return_value=stepfun_handler,
        ),
        patch(
            "common.websocket.session_manager.get_session_manager",
            return_value=session_manager,
        ),
        patch("common.auth.service.verify_token", return_value={"user_id": "u-456"}),
    ):
        await main._handle_presentation_websocket(
            websocket=websocket,
            session_id=session_id,
            token="query-token",
            voice_mode="legacy",
        )

    session_manager.register_session.assert_awaited_once_with(
        session_id,
        stepfun_handler,
        user_id="u-456",
    )
    stepfun_handler.handle_connection.assert_awaited_once_with(
        websocket,
        session_id,
        "query-token",
        trace_id=None,
    )
    legacy_handler.handle_connection.assert_not_called()
    session_manager.unregister_session.assert_awaited_once_with(session_id)


@pytest.mark.asyncio
async def test_presentation_ws_rejects_scenario_mismatch() -> None:
    session_id = str(uuid.uuid4())
    websocket = MagicMock()
    websocket.headers = {}
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    with (
        patch(
            "main._resolve_presentation_runtime",
            new=AsyncMock(return_value=("sales", "legacy")),
        ),
        patch(
            "main._is_presentation_kb_lock_unbound_session",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "common.websocket.session_manager.get_session_manager",
            return_value=session_manager,
        ),
    ):
        await main._handle_presentation_websocket(
            websocket=websocket,
            session_id=session_id,
            token="query-token",
            voice_mode="legacy",
        )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4409,
        reason="SESSION_SCENARIO_MISMATCH",
    )
    session_manager.register_session.assert_not_called()
    session_manager.unregister_session.assert_not_called()


@pytest.mark.asyncio
async def test_presentation_ws_rejects_when_kb_lock_unbound() -> None:
    session_id = str(uuid.uuid4())
    websocket = MagicMock()
    websocket.headers = {}
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    with (
        patch(
            "main._resolve_presentation_runtime",
            new=AsyncMock(return_value=("presentation", "legacy")),
        ),
        patch(
            "main._is_presentation_kb_lock_unbound_session",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "common.websocket.session_manager.get_session_manager",
            return_value=session_manager,
        ),
    ):
        await main._handle_presentation_websocket(
            websocket=websocket,
            session_id=session_id,
            token="query-token",
            voice_mode="legacy",
        )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(
        code=4410,
        reason="KB_LOCK_UNBOUND",
    )
    session_manager.register_session.assert_not_called()
    session_manager.unregister_session.assert_not_called()


@pytest.mark.asyncio
async def test_presentation_ws_rejects_invalid_token_before_registering_session() -> None:
    session_id = str(uuid.uuid4())
    websocket = MagicMock()
    websocket.headers = {}
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    legacy_handler = MagicMock()
    legacy_handler.handle_connection = AsyncMock()

    session_manager = MagicMock()
    session_manager.register_session = AsyncMock()
    session_manager.unregister_session = AsyncMock()

    with (
        patch(
            "main._resolve_presentation_runtime",
            new=AsyncMock(return_value=("presentation", "legacy")),
        ),
        patch(
            "main._is_presentation_kb_lock_unbound_session",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "presentation_coach.websocket.presentation_handler.PresentationWebSocketHandler",
            return_value=legacy_handler,
        ),
        patch(
            "common.websocket.session_manager.get_session_manager",
            return_value=session_manager,
        ),
        patch("common.auth.service.verify_token", side_effect=JWTError("invalid token")),
    ):
        await main._handle_presentation_websocket(
            websocket=websocket,
            session_id=session_id,
            token="invalid-token",
            voice_mode="legacy",
        )

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")
    session_manager.register_session.assert_not_called()
    session_manager.unregister_session.assert_not_called()
    legacy_handler.handle_connection.assert_not_called()
