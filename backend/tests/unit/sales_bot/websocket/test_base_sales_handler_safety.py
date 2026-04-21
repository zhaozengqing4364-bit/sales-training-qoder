"""Safety tests for the shared sales websocket handler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from sales_bot.websocket.base_sales_handler import BaseSalesHandler


@pytest.mark.asyncio
async def test_launch_response_task_rejects_parallel_pipeline():
    """Only one background response pipeline may be active at a time."""
    handler = BaseSalesHandler()
    release = asyncio.Event()

    async def fake_process_user_text_safe(text: str) -> None:
        await release.wait()

    handler._process_user_text_safe = fake_process_user_text_safe
    handler._send_error = AsyncMock()

    first = await handler._launch_response_task("first", source="test")
    second = await handler._launch_response_task("second", source="test")

    assert first is True
    assert second is False
    handler._send_error.assert_awaited_once_with(
        "[RESPONSE_BUSY]",
        "系统正在处理上一轮回复，请稍后再试。",
    )

    release.set()
    await handler._response_task
