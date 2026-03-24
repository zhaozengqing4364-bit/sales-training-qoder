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
        "issue": "当前轮次有1个关键改进点",
        "replacement": "补上案例、数据或ROI证据，让价值主张更可信。",
        "next_turn_rule": "下一轮先补案例或数据证据，并明确下一步动作。",
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
