from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from common.effectiveness.scoring_rulesets import (
    SCORING_RULESET_SCHEMA_VERSION,
    SCORING_RULESET_SCORE_BASIS,
    ScoringDimensionRule,
    ScoringRulesetDefinition,
    ScoringRulesetService,
    ScoringRulesetView,
)


def _projection(*, complete: bool = True) -> SimpleNamespace:
    evidence_completeness = {
        "complete": complete,
        "session_scores": True,
        "message_count": 2,
        "message_scores": 1,
        "stage_evidence": 1,
        "missing_fields": [] if complete else ["message_scores"],
    }
    return SimpleNamespace(
        session_id="session-1",
        scenario_type="sales",
        logic_score=58.0,
        accuracy_score=72.0,
        completeness_score=88.0,
        overall_score=72.67,
        evidence_completeness=evidence_completeness,
        canonical_evaluation_kernel={
            "dimensions": [
                {"dimension_id": "value_expression", "label": "价值表达", "score": 50},
                {
                    "dimension_id": "customer_benefit_connection",
                    "label": "客户收益连接",
                    "score": 60,
                },
                {"dimension_id": "evidence_usage", "label": "证据使用", "score": 70},
                {
                    "dimension_id": "objection_handling",
                    "label": "异议处理",
                    "score": 90,
                },
                {
                    "dimension_id": "next_step_commitment",
                    "label": "推进下一步",
                    "score": 100,
                },
            ]
        },
    )


def _candidate_ruleset() -> ScoringRulesetView:
    default_definition = ScoringRulesetService.build_default_definition("sales")
    dimensions = []
    for dimension in default_definition.dimensions:
        dimensions.append(
            ScoringDimensionRule(
                dimension_id=dimension.dimension_id,
                label=dimension.label,
                weight=10.0 if dimension.dimension_id == "next_step_commitment" else 0.1,
                rollup_contributions=dimension.rollup_contributions,
            )
        )
    return ScoringRulesetView(
        ruleset_id="ruleset-v2",
        scenario_type="sales",
        version="sales-v2",
        display_name="Sales v2",
        description=None,
        status="draft",
        definition=ScoringRulesetDefinition(
            scenario_type="sales",
            score_basis=SCORING_RULESET_SCORE_BASIS,
            dimensions=dimensions,
        ),
        is_active=False,
        source="admin",
    )


def test_ruleset_definition_rejects_unknown_dimension_for_scenario() -> None:
    default_definition = ScoringRulesetService.build_default_definition("sales")
    bad_dimension = default_definition.dimensions[0].model_copy(
        update={"dimension_id": "ppt_only_dimension"}
    )

    with pytest.raises(ValueError, match="not valid for sales"):
        ScoringRulesetDefinition(
            scenario_type="sales",
            dimensions=[bad_dimension, *default_definition.dimensions[1:]],
        )


def test_ruleset_definition_accepts_governed_roleplay_metadata() -> None:
    default_definition = ScoringRulesetService.build_default_definition("sales")

    definition = ScoringRulesetDefinition(
        scenario_type="sales",
        dimensions=default_definition.dimensions,
        hidden_information_coverage=[
            {
                "key": "decision_chain",
                "name": "决策链",
                "expected_trigger": "询问谁负责、谁审批、谁参与推进",
                "evidence": "销售 VP 和 HR 培训负责人参与后续试点评审",
                "dimension": "evidence_usage",
            }
        ],
        deductions=["未确认客户现状就讲产品"],
        passing_score=70,
        rubric="先问清现状，再映射价值。",
        roleplay_contract_version="presales-cio-first-visit-roleplay-contract-v1",
    )

    payload = definition.model_dump(mode="json")

    assert payload["schema_version"] == SCORING_RULESET_SCHEMA_VERSION
    assert payload["hidden_information_coverage"][0]["key"] == "decision_chain"
    assert payload["deductions"] == ["未确认客户现状就讲产品"]
    assert payload["passing_score"] == 70
    assert (
        payload["roleplay_contract_version"]
        == "presales-cio-first-visit-roleplay-contract-v1"
    )


def test_view_from_model_falls_back_when_legacy_definition_is_invalid() -> None:
    row = SimpleNamespace(
        ruleset_id="legacy-ruleset-1",
        scenario_type="sales",
        version="legacy-freeform-v1",
        display_name="Legacy Freeform Ruleset",
        description="old freeform row",
        status="published",
        definition_json={"scenario_type": "sales"},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        published_at=datetime.now(UTC),
    )

    view = ScoringRulesetService.view_from_model(row)  # type: ignore[arg-type]

    assert view.ruleset_id == "legacy-ruleset-1"
    assert view.version == "legacy-freeform-v1"
    assert view.status == "published"
    assert view.is_active is True
    assert view.source == "admin"
    assert view.definition.schema_version == SCORING_RULESET_SCHEMA_VERSION
    assert view.definition.scenario_type == "sales"
    assert view.definition.dimensions


def test_dry_run_compare_uses_candidate_weights_without_mutating_history() -> None:
    baseline = ScoringRulesetService.score_projection(
        projection=_projection(),
        ruleset=ScoringRulesetService.build_default_view("sales"),
    )
    candidate = ScoringRulesetService.score_projection(
        projection=_projection(),
        ruleset=_candidate_ruleset(),
    )

    comparison = ScoringRulesetService.compare_scores(
        session_id="session-1",
        baseline=baseline,
        candidate=candidate,
    )

    assert comparison["mode"] == "dry_run"
    assert comparison["mutates_history"] is False
    assert comparison["baseline"]["ruleset_version"] == "session_evidence_projection_v1"
    assert comparison["candidate"]["ruleset_version"] == "sales-v2"
    assert comparison["candidate"]["overall_score"] > comparison["baseline"]["overall_score"]
    assert comparison["delta"]["overall_score"] == pytest.approx(
        comparison["candidate"]["overall_score"]
        - comparison["baseline"]["overall_score"]
    )


def test_dry_run_returns_reason_instead_of_fake_score_when_evidence_missing() -> None:
    projection = _projection(complete=False)
    projection.evidence_completeness.update(
        {
            "session_scores": False,
            "message_scores": 0,
        }
    )

    result = ScoringRulesetService.score_projection(
        projection=projection,
        ruleset=_candidate_ruleset(),
    )

    assert result["evaluable"] is False
    assert result["overall_score"] is None
    assert "缺少会话分数" in result["not_evaluable_reason"]
