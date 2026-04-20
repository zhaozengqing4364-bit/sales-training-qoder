"""Sales-baseline tests for effectiveness snapshot and realtime score rollups."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from common.api.practice import _apply_sales_realtime_score_snapshot_to_session
from common.effectiveness import evaluate_effectiveness_snapshot


@pytest.mark.asyncio
async def test_apply_sales_realtime_score_snapshot_to_session_maps_sales_rollups():
    session = SimpleNamespace(
        logic_score=None,
        accuracy_score=None,
        completeness_score=None,
        effectiveness_snapshot={"stale": True},
    )

    applied = _apply_sales_realtime_score_snapshot_to_session(
        session,
        {
            "overall_score": 84.0,
            "dimension_scores": {
                "价值表达": 90.0,
                "客户收益连接": 84.0,
                "证据使用": 62.0,
                "异议处理": 78.0,
                "推进下一步": 88.0,
            },
        },
    )

    assert applied is True
    assert session.logic_score == pytest.approx(87.6)
    assert session.accuracy_score == pytest.approx(71.9)
    assert session.completeness_score == pytest.approx(82.0)
    assert session.effectiveness_snapshot is None


def test_evaluate_effectiveness_snapshot_prioritizes_value_translation_gap():
    snapshot = evaluate_effectiveness_snapshot(
        metrics={
            "value_expression_score": 52.0,
            "customer_benefit_score": 58.0,
            "evidence_usage_score": 74.0,
            "objection_handling_score": 80.0,
            "next_step_score": 76.0,
            "value_articulation_rollup": 54.4,
            "evidence_benefit_rollup": 66.8,
            "objection_progress_rollup": 78.4,
        },
        main_capability_passed=False,
        evaluable=True,
    )

    assert snapshot["pass_flags"] == {
        "pass_3min_flow": False,
        "pass_5turn_defense": True,
        "pass_4step_structure": True,
    }
    assert snapshot["main_issue"]["issue_type"] == "value_translation_gap"
    assert "客户收益" in snapshot["main_issue"]["issue_text"]
    assert snapshot["next_goal"]["goal_type"] == "value_to_benefit_translation"
    assert "产品价值" in snapshot["next_goal"]["goal_text"]



def test_evaluate_effectiveness_snapshot_preserves_sales_not_evaluable_fallback():
    snapshot = evaluate_effectiveness_snapshot(
        metrics={
            "value_articulation_rollup": 0.0,
            "evidence_benefit_rollup": 0.0,
            "objection_progress_rollup": 0.0,
        },
        main_capability_passed=False,
        evaluable=False,
        not_evaluable_reason="INSUFFICIENT_TURN_DATA",
    )

    assert snapshot["evaluable"] is False
    assert snapshot["not_evaluable_reason"] == "INSUFFICIENT_TURN_DATA"
    assert snapshot["overall_result"] == "fail"
    assert snapshot["main_issue"]["issue_type"] == "insufficient_sales_evidence"
    assert "价值表达" in snapshot["main_issue"]["issue_text"]
    assert snapshot["next_goal"]["goal_type"] == "collect_sales_evidence"
    assert "异议" in snapshot["next_goal"]["goal_text"]
