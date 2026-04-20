from __future__ import annotations

from sales_bot.websocket.realtime_feedback_arbiter import (
    RealtimeFeedbackArbiter,
    RealtimeFeedbackPacingState,
)


def test_prioritizes_score_guidance_over_low_severity_fuzzy_detection() -> None:
    arbiter = RealtimeFeedbackArbiter()

    decision = arbiter.decide(
        turn_number=2,
        fuzzy_detections=[
            {
                "category": "filler",
                "matched": ["嗯"],
                "suggestion": "减少填充词，保持表达流畅",
                "severity": "low",
            }
        ],
        score_suggestions=["补上案例、数据或ROI证据，让价值主张更可信。"],
        stage_context={
            "current_stage": "discovery",
            "stage_name": "需求挖掘",
            "guidance": "继续追问痛点",
        },
        score_context={
            "overall_score": 82.0,
            "dimension_scores": {"证据使用": 61.0},
            "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
        },
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        prior_state=RealtimeFeedbackPacingState(),
    )

    assert decision.primary_source == "score"
    assert decision.action_card == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    assert decision.fuzzy_detections == [
        {
            "category": "filler",
            "matched": ["嗯"],
            "suggestion": "减少填充词，保持表达流畅",
            "severity": "low",
        }
    ]
    assert decision.stage_context == {
        "current_stage": "discovery",
        "stage_name": "需求挖掘",
        "guidance": "继续追问痛点",
    }
    assert decision.score_context == {
        "overall_score": 82.0,
        "dimension_scores": {"证据使用": 61.0},
        "suggestions": ["补上案例、数据或ROI证据，让价值主张更可信。"],
    }
    assert decision.duplicate_action_suppressed is False


def test_stage_context_can_change_score_primary_action_card() -> None:
    arbiter = RealtimeFeedbackArbiter()
    shared_score_context = {
        "overall_score": 78.0,
        "dimension_scores": {
            "价值表达": 61.0,
            "客户收益连接": 63.0,
            "证据使用": 74.0,
            "异议处理": 72.0,
            "推进下一步": 65.0,
        },
        "suggestions": ["继续补充更多上下文。"],
    }

    discovery_decision = arbiter.decide(
        turn_number=4,
        score_suggestions=["继续补充更多上下文。"],
        stage_context={
            "current_stage": "discovery",
            "stage_name": "需求挖掘",
            "guidance": "继续确认损失与目标",
        },
        score_context=shared_score_context,
        pass_flags={
            "pass_3min_flow": False,
            "pass_5turn_defense": True,
            "pass_4step_structure": True,
        },
        prior_state=RealtimeFeedbackPacingState(),
    )
    closing_decision = arbiter.decide(
        turn_number=4,
        score_suggestions=["继续补充更多上下文。"],
        stage_context={
            "current_stage": "closing",
            "stage_name": "成交推进",
            "guidance": "开始锁定行动与时间",
        },
        score_context=shared_score_context,
        pass_flags={
            "pass_3min_flow": False,
            "pass_5turn_defense": True,
            "pass_4step_structure": True,
        },
        prior_state=RealtimeFeedbackPacingState(),
    )

    assert discovery_decision.primary_source == "score"
    assert discovery_decision.action_card == {
        "issue": "需求还没被翻译成客户收益，客户暂时感受不到业务价值。",
        "replacement": "先追问现状损失或关键目标，再用一句话复述客户收益。",
        "next_turn_rule": "下一轮先问清现状损失或目标，再复述一个客户收益。",
    }
    assert closing_decision.primary_source == "score"
    assert closing_decision.action_card == {
        "issue": "对话快结束了，但下一步动作、时间点和责任人还没定下来。",
        "replacement": "明确试点、会议、报价或负责人确认中的一个动作。",
        "next_turn_rule": "下一轮先锁定动作、时间点和责任人，再结束本轮。",
    }


def test_declining_dimension_can_change_score_primary_action_card() -> None:
    arbiter = RealtimeFeedbackArbiter()
    stable_score_context = {
        "overall_score": 76.0,
        "dimension_scores": {
            "价值表达": 82.0,
            "客户收益连接": 79.0,
            "证据使用": 66.0,
            "异议处理": 72.0,
            "推进下一步": 78.0,
        },
        "suggestions": ["继续回应客户顾虑。"],
    }
    declining_score_context = {
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
        "suggestions": ["继续回应客户顾虑。"],
    }

    stable_decision = arbiter.decide(
        turn_number=5,
        score_suggestions=["继续回应客户顾虑。"],
        stage_context={
            "current_stage": "objection",
            "stage_name": "异议处理",
            "guidance": "承接价格与风险顾虑",
        },
        score_context=stable_score_context,
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": False,
            "pass_4step_structure": True,
        },
        prior_state=RealtimeFeedbackPacingState(),
    )
    declining_decision = arbiter.decide(
        turn_number=5,
        score_suggestions=["继续回应客户顾虑。"],
        stage_context={
            "current_stage": "objection",
            "stage_name": "异议处理",
            "guidance": "承接价格与风险顾虑",
        },
        score_context=declining_score_context,
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": False,
            "pass_4step_structure": True,
        },
        prior_state=RealtimeFeedbackPacingState(),
    )

    assert stable_decision.primary_source == "score"
    assert stable_decision.action_card == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    assert declining_decision.primary_source == "score"
    assert declining_decision.action_card == {
        "issue": "客户顾虑出现后，承接与重构回应还不够完整。",
        "replacement": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
        "next_turn_rule": "下一轮先复述顾虑，再回应证据，最后给低风险推进方案。",
    }


def test_suppresses_duplicate_action_card_for_same_turn_and_signature() -> None:
    arbiter = RealtimeFeedbackArbiter()

    first_decision = arbiter.decide(
        turn_number=3,
        score_suggestions=["补上案例、数据或ROI证据，让价值主张更可信。"],
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        prior_state=RealtimeFeedbackPacingState(),
    )
    second_decision = arbiter.decide(
        turn_number=3,
        score_suggestions=["补上案例、数据或ROI证据，让价值主张更可信。"],
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        prior_state=first_decision.state,
    )
    next_turn_decision = arbiter.decide(
        turn_number=4,
        score_suggestions=["补上案例、数据或ROI证据，让价值主张更可信。"],
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        prior_state=second_decision.state,
    )

    assert first_decision.action_card is not None
    assert second_decision.action_card is None
    assert second_decision.duplicate_action_suppressed is True
    assert next_turn_decision.action_card == first_decision.action_card
    assert next_turn_decision.duplicate_action_suppressed is False


def test_preserve_context_without_primary_action() -> None:
    arbiter = RealtimeFeedbackArbiter()

    decision = arbiter.decide(
        turn_number=5,
        stage_context={
            "current_stage": "qualification",
            "stage_name": "需求确认",
        },
        score_context={
            "overall_score": 79.0,
            "dimension_scores": {"价值表达": 79.0},
            "suggestions": [],
        },
        prior_state=RealtimeFeedbackPacingState(),
    )

    assert decision.primary_source is None
    assert decision.action_card is None
    assert decision.stage_context == {
        "current_stage": "qualification",
        "stage_name": "需求确认",
    }
    assert decision.score_context == {
        "overall_score": 79.0,
        "dimension_scores": {"价值表达": 79.0},
        "suggestions": [],
    }
    assert decision.duplicate_action_suppressed is False
