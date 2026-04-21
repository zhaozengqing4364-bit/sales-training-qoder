"""Focused tests for stage-aware sales coaching focus resolution."""
from __future__ import annotations

from common.effectiveness import build_action_card, resolve_sales_coaching_focus

DISCOVERY_STAGE = {
    "current_stage": "discovery",
    "stage_name": "需求挖掘",
    "key_actions": ["深入痛点", "确认需求"],
    "guidance": "深入挖掘客户需求和痛点",
    "progress": 0.4,
}

OBJECTION_STAGE = {
    "current_stage": "objection",
    "stage_name": "异议处理",
    "key_actions": ["处理疑虑", "提供证据"],
    "guidance": "耐心处理客户疑虑",
    "progress": 0.8,
}

CLOSING_STAGE = {
    "current_stage": "closing",
    "stage_name": "促成成交",
    "key_actions": ["推动决策", "行动号召"],
    "guidance": "推动客户做出决策",
    "progress": 1.0,
}


def test_resolve_sales_coaching_focus_for_discovery_evidence_gap() -> None:
    focus = resolve_sales_coaching_focus(
        stage_context=DISCOVERY_STAGE,
        score_context={
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 80.0,
                "证据使用": 58.0,
                "异议处理": 76.0,
                "推进下一步": 72.0,
            },
        },
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
    )

    assert focus == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }


def test_resolve_sales_coaching_focus_for_objection_handling_gap() -> None:
    focus = resolve_sales_coaching_focus(
        stage_context=OBJECTION_STAGE,
        score_context={
            "overall_score": 74.0,
            "dimension_scores": {
                "价值表达": 76.0,
                "客户收益连接": 74.0,
                "证据使用": 70.0,
                "异议处理": 54.0,
                "推进下一步": 69.0,
            },
        },
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": False,
            "pass_4step_structure": True,
        },
    )

    assert focus == {
        "issue": "客户顾虑出现后，承接与重构回应还不够完整。",
        "replacement": "先复述价格、竞品或风险顾虑，再给收益与证据回应。",
        "next_turn_rule": "下一轮先复述顾虑，再回应证据，最后给低风险推进方案。",
    }


def test_resolve_sales_coaching_focus_for_closing_next_step_gap() -> None:
    focus = resolve_sales_coaching_focus(
        stage_context=CLOSING_STAGE,
        score_context={
            "overall_score": 78.0,
            "dimension_scores": {
                "价值表达": 82.0,
                "客户收益连接": 80.0,
                "证据使用": 74.0,
                "异议处理": 76.0,
                "推进下一步": 56.0,
            },
        },
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
    )

    assert focus == {
        "issue": "对话快结束了，但下一步动作、时间点和责任人还没定下来。",
        "replacement": "明确试点、会议、报价或负责人确认中的一个动作。",
        "next_turn_rule": "下一轮先锁定动作、时间点和责任人，再结束本轮。",
    }


def test_build_action_card_weakest_dimension_changes_next_turn_rule() -> None:
    evidence_card = build_action_card(
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        stage_context=DISCOVERY_STAGE,
        score_context={
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 80.0,
                "证据使用": 58.0,
                "异议处理": 76.0,
                "推进下一步": 72.0,
            },
        },
    )
    value_card = build_action_card(
        pass_flags={
            "pass_3min_flow": True,
            "pass_5turn_defense": True,
            "pass_4step_structure": False,
        },
        stage_context=DISCOVERY_STAGE,
        score_context={
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 57.0,
                "证据使用": 74.0,
                "异议处理": 76.0,
                "推进下一步": 72.0,
            },
        },
    )

    assert evidence_card == {
        "issue": "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
        "replacement": "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
        "next_turn_rule": "下一轮先确认痛点影响，再补一个案例或ROI数据。",
    }
    assert value_card == {
        "issue": "需求还没被翻译成客户收益，客户暂时感受不到业务价值。",
        "replacement": "先追问现状损失或关键目标，再用一句话复述客户收益。",
        "next_turn_rule": "下一轮先问清现状损失或目标，再复述一个客户收益。",
    }
    assert evidence_card["next_turn_rule"] != value_card["next_turn_rule"]
