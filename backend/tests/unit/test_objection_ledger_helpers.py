from __future__ import annotations

from copy import deepcopy

from common.business_rules.defaults import (
    OBJECTION_LEDGER_RULES_KEY,
    get_default_business_rule_value,
)
from sales_bot.websocket.components.objection_ledger_helpers import (
    build_arbiter_override_context,
    resolve_objection_ledger_ruleset,
    resolve_turn_objection_ledger,
)


def test_default_ruleset_opens_and_closes_price_pressure_ledger() -> None:
    ledger = resolve_turn_objection_ledger(
        existing_ledger=None,
        user_text="客户觉得报价太贵，预算和折扣都有顾虑。",
        stage_context={"stage_name": "异议处理"},
        score_context={"dimension_scores": {"异议处理": 45.0}},
    )

    assert ledger is not None
    assert ledger["objection_family"] == "price_pressure"
    assert ledger["closure_state"] == "open"

    updated = resolve_turn_objection_ledger(
        existing_ledger=ledger,
        user_text="我们可以补充报价依据，三个版本差异和 20% 折扣边界。",
        stage_context={"stage_name": "异议处理"},
        score_context={"dimension_scores": {"异议处理": 45.0}},
    )

    assert updated is not None
    assert updated["closure_state"] == "evidence_provided"


def test_custom_ruleset_can_add_family_without_code_constant_edits() -> None:
    ruleset = get_default_business_rule_value(OBJECTION_LEDGER_RULES_KEY)
    ruleset = deepcopy(ruleset)
    ruleset["families"] = {
        "security_review": {
            "focus_dimension": "证据使用",
            "promised_proof": "补充安全审计报告",
            "next_expected_evidence": "给出权限审计和渗透测试结论",
            "detect_any": ["安全", "审计", "权限"],
            "evidence_any": ["安全", "审计", "权限", "报告"],
            "open_pressure_any": ["安全", "审计", "权限", "担心"],
            "open_pressure_requires_any": ["安全", "审计", "权限"],
        }
    }

    ledger = resolve_turn_objection_ledger(
        existing_ledger=None,
        user_text="客户担心安全权限审计没有证据。",
        stage_context={"stage_name": "异议处理"},
        score_context={"dimension_scores": {"证据使用": 40.0}},
        ruleset=ruleset,
    )

    assert ledger == {
        "objection_family": "security_review",
        "promised_proof": "补充安全审计报告",
        "next_expected_evidence": "给出权限审计和渗透测试结论",
        "closure_state": "open",
    }


def test_invalid_ruleset_falls_back_to_default_rules() -> None:
    resolved = resolve_objection_ledger_ruleset({"version": "broken"})

    assert resolved["version"] == "sales_objection_ledger_v1"

    ledger = resolve_turn_objection_ledger(
        existing_ledger=None,
        user_text="客户认为价格和预算风险很大。",
        stage_context={"stage_name": "异议处理"},
        score_context={"dimension_scores": {"异议处理": 45.0}},
        ruleset={"version": "broken"},
    )

    assert ledger is not None
    assert ledger["objection_family"] == "price_pressure"


def test_disabled_ruleset_degrades_without_opening_or_overriding() -> None:
    ruleset = get_default_business_rule_value(OBJECTION_LEDGER_RULES_KEY)
    ruleset["enabled"] = False

    ledger = resolve_turn_objection_ledger(
        existing_ledger=None,
        user_text="客户认为价格和预算风险很大。",
        stage_context={"stage_name": "异议处理"},
        score_context={"dimension_scores": {"异议处理": 45.0}},
        ruleset=ruleset,
    )

    assert ledger is None
    assert build_arbiter_override_context(
        objection_ledger={
            "objection_family": "price_pressure",
            "promised_proof": "补充报价依据和版本差异",
            "next_expected_evidence": "说明报价逻辑、预算回收或折扣边界",
            "closure_state": "open",
        },
        ruleset=ruleset,
    ) == (None, None)


def test_arbiter_override_uses_ruleset_synthetic_scores() -> None:
    _, score_context = build_arbiter_override_context(
        objection_ledger={
            "objection_family": "roi_proof",
            "promised_proof": "补充同类客户 ROI 案例",
            "next_expected_evidence": "给出 6 个月回本测算",
            "closure_state": "open",
        }
    )

    assert score_context is not None
    assert score_context["dimension_scores"]["证据使用"] == 48.0
    assert score_context["suggestions"] == ["给出 6 个月回本测算"]
