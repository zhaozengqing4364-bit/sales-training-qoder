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


@pytest.mark.asyncio
async def test_realtime_scoring_action_card_uses_sales_effectiveness_semantics() -> None:
    runner = MagicMock()
    runner.capabilities = [SimpleNamespace(capability_id="realtime_scoring")]
    runner.run_all = AsyncMock(
        return_value=[
            SimpleNamespace(
                success=True,
                data={
                    "overall": 82.0,
                    "overall_score": 82.0,
                    "dimension_scores": {
                        "价值表达": 84.0,
                        "客户收益连接": 80.0,
                        "证据使用": 61.0,
                        "异议处理": 76.0,
                        "推进下一步": 64.0,
                    },
                    "dimensions": [
                        {"name": "价值表达", "score": 84.0},
                        {"name": "客户收益连接", "score": 80.0},
                        {"name": "证据使用", "score": 61.0},
                        {"name": "异议处理", "score": 76.0},
                        {"name": "推进下一步", "score": 64.0},
                    ],
                    "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
                },
            )
        ]
    )

    processor = CapabilityProcessor(runner)
    context = SimpleNamespace(trace_id="trace-score-1", turn_count=2)
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    analysis, _ = await processor.run_and_send_feedback(
        text="我们可以继续介绍方案。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert analysis["ai_feedback"] == "补上案例、数据或ROI证据，让价值主张更可信。"

    sent_payloads = [call.args[1] for call in manager.send_json.await_args_list]
    score_update = next(payload for payload in sent_payloads if payload["type"] == "score_update")
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")

    assert score_update["data"]["overall_score"] == 82.0
    assert action_card["data"]["next_turn_rule"] == "下一轮先补案例或数据证据，并明确下一步动作。"
