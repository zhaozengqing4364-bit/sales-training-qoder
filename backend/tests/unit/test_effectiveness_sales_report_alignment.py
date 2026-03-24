"""Focused tests for stage-aware sales report alignment from persisted evidence."""
from __future__ import annotations

from typing import Any, Callable

import common.effectiveness as effectiveness
from common.effectiveness import evaluate_effectiveness_snapshot


Resolver = Callable[..., dict[str, Any]]


def _resolve_alignment(**kwargs: Any) -> dict[str, Any]:
    resolver = getattr(effectiveness, "resolve_sales_report_alignment", None)
    assert resolver is not None, "resolve_sales_report_alignment should be exported from common.effectiveness"
    result = resolver(**kwargs)
    assert isinstance(result, dict)
    return result


def test_resolve_sales_report_alignment_for_discovery_evidence_gap() -> None:
    aligned = _resolve_alignment(
        sales_stage="discovery",
        score_snapshot={
            "overall_score": 82.0,
            "dimension_scores": {
                "价值表达": 84.0,
                "客户收益连接": 80.0,
                "证据使用": 58.0,
                "异议处理": 76.0,
                "推进下一步": 72.0,
            },
        },
        fallback_snapshot=None,
    )

    assert aligned["alignment_used"] is True
    assert aligned["stage_key"] == "discovery"
    assert aligned["focus_type"] == "evidence_gap"
    assert aligned["fallback_reason"] is None
    assert aligned["main_issue"]["issue_type"] == "evidence_gap"
    assert aligned["next_goal"]["goal_type"] == "evidence_backing"



def test_resolve_sales_report_alignment_for_objection_handling_gap() -> None:
    aligned = _resolve_alignment(
        sales_stage="objection",
        score_snapshot={
            "overall_score": 74.0,
            "dimension_scores": {
                "价值表达": 76.0,
                "客户收益连接": 74.0,
                "证据使用": 70.0,
                "异议处理": 54.0,
                "推进下一步": 69.0,
            },
        },
        fallback_snapshot=None,
    )

    assert aligned["alignment_used"] is True
    assert aligned["stage_key"] == "objection"
    assert aligned["focus_type"] == "objection_handling_gap"
    assert aligned["main_issue"]["issue_type"] == "objection_handling_gap"
    assert aligned["next_goal"]["goal_type"] == "objection_reframe"



def test_resolve_sales_report_alignment_for_closing_next_step_gap() -> None:
    aligned = _resolve_alignment(
        sales_stage="closing",
        score_snapshot={
            "overall_score": 78.0,
            "dimension_scores": {
                "价值表达": 82.0,
                "客户收益连接": 80.0,
                "证据使用": 74.0,
                "异议处理": 76.0,
                "推进下一步": 56.0,
            },
        },
        fallback_snapshot=None,
    )

    assert aligned["alignment_used"] is True
    assert aligned["stage_key"] == "closing"
    assert aligned["focus_type"] == "next_step_gap"
    assert aligned["main_issue"]["issue_type"] == "next_step_gap"
    assert aligned["next_goal"]["goal_type"] == "next_step_commitment"



def test_resolve_sales_report_alignment_falls_back_for_insufficient_sales_evidence() -> None:
    fallback_snapshot = evaluate_effectiveness_snapshot(
        metrics={
            "value_articulation_rollup": 0.0,
            "evidence_benefit_rollup": 0.0,
            "objection_progress_rollup": 0.0,
        },
        main_capability_passed=False,
        evaluable=False,
        not_evaluable_reason="INSUFFICIENT_TURN_DATA",
    )

    aligned = _resolve_alignment(
        sales_stage="discovery",
        score_snapshot={"overall_score": 81.0},
        fallback_snapshot=fallback_snapshot,
    )

    assert aligned["alignment_used"] is False
    assert aligned["stage_key"] == "discovery"
    assert aligned["focus_type"] is None
    assert aligned["fallback_reason"] == "missing_dimension_scores"
    assert aligned["main_issue"]["issue_type"] == "insufficient_sales_evidence"
    assert aligned["next_goal"]["goal_type"] == "collect_sales_evidence"
