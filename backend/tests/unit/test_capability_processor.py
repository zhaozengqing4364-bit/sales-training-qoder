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
    runner.capabilities = [
        SimpleNamespace(capability_id="sales_stage"),
        SimpleNamespace(capability_id="realtime_scoring"),
    ]
    runner.run_all = AsyncMock(
        return_value=[
            SimpleNamespace(
                success=True,
                data={
                    "current_stage": "closing",
                    "stage_name": "成交推进",
                    "key_actions": ["锁定动作"],
                    "guidance": "推动明确下一步",
                    "progress": 0.8,
                    "stage_changed": True,
                },
            ),
            SimpleNamespace(
                success=True,
                data={
                    "overall": 78.0,
                    "overall_score": 78.0,
                    "dimension_scores": {
                        "价值表达": 61.0,
                        "客户收益连接": 63.0,
                        "证据使用": 74.0,
                        "异议处理": 72.0,
                        "推进下一步": 65.0,
                    },
                    "dimensions": [
                        {"name": "价值表达", "score": 61.0},
                        {"name": "客户收益连接", "score": 63.0},
                        {"name": "证据使用", "score": 74.0},
                        {"name": "异议处理", "score": 72.0},
                        {"name": "推进下一步", "score": 65.0},
                    ],
                    "feedback": "继续补充更多上下文。",
                },
            ),
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

    assert analysis["sales_stage"] == "closing"
    assert analysis["ai_feedback"] == "明确试点、会议、报价或负责人确认中的一个动作。"

    sent_payloads = [call.args[1] for call in manager.send_json.await_args_list]
    sent_types = [payload["type"] for payload in sent_payloads]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")

    assert sent_types == ["stage_update", "score_update", "action_card"]
    assert action_card["data"] == {
        "issue": "对话快结束了，但下一步动作、时间点和责任人还没定下来。",
        "replacement": "明确试点、会议、报价或负责人确认中的一个动作。",
        "next_turn_rule": "下一轮先锁定动作、时间点和责任人，再结束本轮。",
    }


@pytest.mark.asyncio
async def test_realtime_scoring_action_card_uses_declining_dimension_from_raw_score_payload() -> None:
    runner = MagicMock()
    runner.capabilities = [
        SimpleNamespace(capability_id="sales_stage"),
        SimpleNamespace(capability_id="realtime_scoring"),
    ]
    runner.run_all = AsyncMock(
        return_value=[
            SimpleNamespace(
                success=True,
                data={
                    "current_stage": "objection",
                    "stage_name": "异议处理",
                    "key_actions": ["承接顾虑"],
                    "guidance": "围绕风险与证据回应",
                    "progress": 0.6,
                    "stage_changed": True,
                },
            ),
            SimpleNamespace(
                success=True,
                data={
                    "overall": 76.0,
                    "overall_score": 76.0,
                    "dimension_scores": {
                        "价值表达": 82.0,
                        "客户收益连接": 79.0,
                        "证据使用": 66.0,
                        "异议处理": 72.0,
                        "推进下一步": 78.0,
                    },
                    "dimensions": [
                        {"name": "证据使用", "score": 66.0, "delta": 1.0, "trend": "up"},
                        {"name": "异议处理", "score": 72.0, "delta": -9.0, "trend": "down"},
                    ],
                    "feedback": "继续回应客户顾虑。",
                },
            ),
        ]
    )

    processor = CapabilityProcessor(runner)
    context = SimpleNamespace(trace_id="trace-score-decline-1", turn_count=4)
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    analysis, _ = await processor.run_and_send_feedback(
        text="客户担心实施风险和价格。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert analysis["ai_feedback"] == "先复述价格、竞品或风险顾虑，再给收益与证据回应。"

    sent_payloads = [call.args[1] for call in manager.send_json.await_args_list]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")

    assert action_card["data"] == {
        "issue": "客户顾虑出现后，承接与重构回应还不够完整。",
        "replacement": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
        "next_turn_rule": "下一轮先复述顾虑，再回应证据，最后给低风险推进方案。",
    }


@pytest.mark.asyncio
async def test_score_guidance_beats_low_priority_fuzzy_detection_and_keeps_context_messages() -> None:
    runner = MagicMock()
    runner.capabilities = [
        SimpleNamespace(capability_id="fuzzy_detection"),
        SimpleNamespace(capability_id="sales_stage"),
        SimpleNamespace(capability_id="realtime_scoring"),
    ]
    runner.run_all = AsyncMock(
        return_value=[
            SimpleNamespace(
                success=True,
                data={
                    "detections": [
                        {
                            "category": "filler",
                            "matched": ["嗯"],
                            "suggestion": "减少填充词，保持表达流畅",
                            "severity": "low",
                        }
                    ]
                },
            ),
            SimpleNamespace(
                success=True,
                data={
                    "current_stage": "discovery",
                    "stage_name": "需求挖掘",
                    "key_actions": ["继续追问痛点"],
                    "guidance": "确认影响范围",
                    "progress": 0.4,
                    "stage_changed": True,
                },
            ),
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
                    "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
                },
            ),
        ]
    )

    processor = CapabilityProcessor(runner)
    context = SimpleNamespace(trace_id="trace-priority-1", turn_count=2)
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    analysis, _ = await processor.run_and_send_feedback(
        text="嗯，我们可以再介绍一下方案。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert analysis["ai_feedback"] == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"
    sent_payloads = [call.args[1] for call in manager.send_json.await_args_list]
    sent_types = [payload["type"] for payload in sent_payloads]

    assert sent_types == [
        "fuzzy_detection",
        "stage_update",
        "score_update",
        "action_card",
    ]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")
    assert action_card["data"] == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }


@pytest.mark.asyncio
async def test_duplicate_action_card_is_suppressed_for_same_turn_signature() -> None:
    runner = MagicMock()
    runner.capabilities = [SimpleNamespace(capability_id="realtime_scoring")]
    runner.run_all = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(
                    success=True,
                    data={
                        "overall_score": 82.0,
                        "dimension_scores": {
                            "价值表达": 84.0,
                            "客户收益连接": 80.0,
                            "证据使用": 61.0,
                            "异议处理": 76.0,
                            "推进下一步": 64.0,
                        },
                        "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
                    },
                )
            ],
            [
                SimpleNamespace(
                    success=True,
                    data={
                        "overall_score": 82.0,
                        "dimension_scores": {
                            "价值表达": 84.0,
                            "客户收益连接": 80.0,
                            "证据使用": 61.0,
                            "异议处理": 76.0,
                            "推进下一步": 64.0,
                        },
                        "feedback": "补上案例、数据或ROI证据，让价值主张更可信。",
                    },
                )
            ],
        ]
    )

    processor = CapabilityProcessor(runner)
    context = SimpleNamespace(trace_id="trace-duplicate-1", turn_count=3)
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    first_analysis, _ = await processor.run_and_send_feedback(
        text="我们可以用客户案例说明ROI。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )
    second_analysis, _ = await processor.run_and_send_feedback(
        text="我们可以用客户案例说明ROI。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert first_analysis["ai_feedback"] == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"
    assert "ai_feedback" not in second_analysis

    sent_payloads = [call.args[1] for call in manager.send_json.await_args_list]
    sent_types = [payload["type"] for payload in sent_payloads]
    assert sent_types == ["score_update", "action_card", "score_update"]


@pytest.mark.asyncio
async def test_open_objection_ledger_keeps_focus_on_same_gap_during_topic_drift() -> None:
    runner = MagicMock()
    runner.capabilities = [
        SimpleNamespace(capability_id="sales_stage"),
        SimpleNamespace(capability_id="realtime_scoring"),
    ]
    runner.run_all = AsyncMock(
        return_value=[
            SimpleNamespace(
                success=True,
                data={
                    "current_stage": "closing",
                    "stage_name": "成交推进",
                    "key_actions": ["锁定动作"],
                    "guidance": "推动明确下一步",
                    "progress": 0.8,
                    "stage_changed": True,
                },
            ),
            SimpleNamespace(
                success=True,
                data={
                    "overall_score": 79.0,
                    "dimension_scores": {
                        "价值表达": 84.0,
                        "客户收益连接": 82.0,
                        "证据使用": 88.0,
                        "异议处理": 81.0,
                        "推进下一步": 52.0,
                    },
                    "feedback": "明确试点、会议、报价或负责人确认中的一个动作。",
                },
            ),
        ]
    )

    processor = CapabilityProcessor(runner)
    processor._objection_ledger = {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }
    context = SimpleNamespace(trace_id="trace-objection-ledger-1", turn_count=5)
    websocket = AsyncMock()
    manager = MagicMock()
    manager.send_json = AsyncMock()
    db_lock = asyncio.Lock()

    analysis, _ = await processor.run_and_send_feedback(
        text="我们可以先聊一下后面的协同流程。",
        context=context,
        websocket=websocket,
        manager=manager,
        db_lock=db_lock,
    )

    assert analysis["objection_ledger"] == {
        "objection_family": "roi_proof",
        "promised_proof": "补充同类客户 ROI 案例",
        "next_expected_evidence": "给出 6 个月回本测算",
        "closure_state": "open",
    }
    assert analysis["ai_feedback"] == "在确认痛点后，补一个同类客户案例、数据或ROI区间。"

    sent_payloads = [call.args[1] for call in manager.send_json.await_args_list]
    action_card = next(payload for payload in sent_payloads if payload["type"] == "action_card")
    assert action_card["data"] == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
