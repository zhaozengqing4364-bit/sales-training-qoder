"""Unit tests for sales websocket message persistence component."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from common.error_handling.result import Result
from sales_bot.websocket.components.message_persistence import MessagePersistence


class _FakeSessionFactory:
    """Async context manager compatible with AsyncSessionLocal usage."""

    def __init__(self, db_object: object):
        self.db_object = db_object

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db_object

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_save_message_returns_message_id_on_success() -> None:
    persistence = MessagePersistence(session_id="session-sales-1")
    db_lock = asyncio.Lock()
    storage = Mock()
    storage.save_message = AsyncMock(
        return_value=Result.ok(SimpleNamespace(id="msg-sales-1"))
    )

    with (
        patch(
            "sales_bot.websocket.components.message_persistence.AsyncSessionLocal",
            _FakeSessionFactory(object()),
        ),
        patch(
            "sales_bot.websocket.components.message_persistence.MessageStorageService",
            return_value=storage,
        ),
    ):
        message_id = await persistence.save_message(
            turn_number=3,
            role="user",
            content="客户说预算偏高",
            db_lock=db_lock,
        )

    assert message_id == "msg-sales-1"
    storage.save_message.assert_awaited_once_with(
        session_id="session-sales-1",
        turn_number=3,
        role="user",
        content="客户说预算偏高",
    )


@pytest.mark.asyncio
async def test_save_message_returns_none_on_storage_failure() -> None:
    persistence = MessagePersistence(session_id="session-sales-2")
    db_lock = asyncio.Lock()
    storage = Mock()
    storage.save_message = AsyncMock(
        return_value=Result.fail("[MESSAGE_SAVE_FAILED]")
    )

    with (
        patch(
            "sales_bot.websocket.components.message_persistence.AsyncSessionLocal",
            _FakeSessionFactory(object()),
        ),
        patch(
            "sales_bot.websocket.components.message_persistence.MessageStorageService",
            return_value=storage,
        ),
    ):
        message_id = await persistence.save_message(
            turn_number=1,
            role="assistant",
            content="请继续介绍你的采购流程。",
            db_lock=db_lock,
        )

    assert message_id is None
    storage.save_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_analysis_passes_unpacked_fields() -> None:
    persistence = MessagePersistence(session_id="session-sales-3")
    db_lock = asyncio.Lock()
    storage = Mock()
    storage.update_analysis = AsyncMock(return_value=Result.ok(SimpleNamespace()))

    with (
        patch(
            "sales_bot.websocket.components.message_persistence.AsyncSessionLocal",
            _FakeSessionFactory(object()),
        ),
        patch(
            "sales_bot.websocket.components.message_persistence.MessageStorageService",
            return_value=storage,
        ),
    ):
        await persistence.update_analysis(
            message_id="msg-sales-3",
            analysis_data={
                "fuzzy_words": [{"matched": "可能"}],
                "sales_stage": "discovery",
                "score_snapshot": {"overall": 86},
                "ai_feedback": "建议量化价值点。",
            },
            db_lock=db_lock,
        )

    storage.update_analysis.assert_awaited_once_with(
        "msg-sales-3",
        fuzzy_words=[{"matched": "可能"}],
        sales_stage="discovery",
        score_snapshot={"overall": 86},
        ai_feedback="建议量化价值点。",
    )


@pytest.mark.asyncio
async def test_update_analysis_skips_when_empty_data() -> None:
    persistence = MessagePersistence(session_id="session-sales-4")
    db_lock = asyncio.Lock()
    async_session_local = Mock()

    with patch(
        "sales_bot.websocket.components.message_persistence.AsyncSessionLocal",
        async_session_local,
    ):
        await persistence.update_analysis(
            message_id="msg-sales-4",
            analysis_data={},
            db_lock=db_lock,
        )

    async_session_local.assert_not_called()
