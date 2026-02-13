"""Unit tests for sales capability processor stage update behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from sales_bot.websocket.components.capability_processor import CapabilityProcessor


@pytest.mark.asyncio
async def test_stage_update_emits_once_for_unchanged_stage() -> None:
    runner = MagicMock()
    runner.capabilities = [SimpleNamespace(capability_id="sales_stage")]
    runner.run_all = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(
                    success=True,
                    data={
                        "current_stage": "opening",
                        "stage_name": "开场破冰",
                        "key_actions": ["建立信任"],
                        "guidance": "保持自然开场",
                        "progress": 0.2,
                        "stage_changed": False,
                    },
                )
            ],
            [
                SimpleNamespace(
                    success=True,
                    data={
                        "current_stage": "opening",
                        "stage_name": "开场破冰",
                        "key_actions": ["建立信任"],
                        "guidance": "保持自然开场",
                        "progress": 0.2,
                        "stage_changed": False,
                    },
                )
            ],
        ]
    )

    processor = CapabilityProcessor(runner)
    context = SimpleNamespace(trace_id="trace-stage-1")
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    first_analysis, _ = await processor.run_and_send_feedback(
        text="你好，我们先简单认识一下。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )
    second_analysis, _ = await processor.run_and_send_feedback(
        text="继续介绍公司背景。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert first_analysis["sales_stage"] == "opening"
    assert second_analysis["sales_stage"] == "opening"
    manager.send_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_stage_update_emits_again_when_stage_changed() -> None:
    runner = MagicMock()
    runner.capabilities = [SimpleNamespace(capability_id="sales_stage")]
    runner.run_all = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(
                    success=True,
                    data={
                        "current_stage": "opening",
                        "stage_name": "开场破冰",
                        "key_actions": ["建立信任"],
                        "guidance": "保持自然开场",
                        "progress": 0.2,
                        "stage_changed": False,
                    },
                )
            ],
            [
                SimpleNamespace(
                    success=True,
                    data={
                        "current_stage": "discovery",
                        "stage_name": "需求挖掘",
                        "key_actions": ["深入痛点"],
                        "guidance": "多问开放问题",
                        "progress": 0.4,
                        "stage_changed": True,
                        "previous_stage": "opening",
                    },
                )
            ],
        ]
    )

    processor = CapabilityProcessor(runner)
    context = SimpleNamespace(trace_id="trace-stage-2")
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    await processor.run_and_send_feedback(
        text="你好，我们先聊聊现状。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )
    second_analysis, _ = await processor.run_and_send_feedback(
        text="你们目前最大的业务挑战是什么？",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert second_analysis["sales_stage"] == "discovery"
    assert manager.send_json.await_count == 2
