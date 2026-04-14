"""Fail-first proof for the first methodology-aware sales rubric contract."""
from __future__ import annotations

from common import effectiveness


EXPECTED_RUBRIC_IDS = [
    "discovery_qualification",
    "value_story",
    "evidence_proof",
    "objection_reframe",
    "next_step_commitment",
]


def _rubrics_by_id(contract: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(item["rubric_id"]): item
        for item in contract["rubrics"]
        if isinstance(item, dict) and "rubric_id" in item
    }


def test_sales_methodology_contract_exposes_first_round_rubric_crosswalk() -> None:
    factory = getattr(effectiveness, "get_sales_methodology_contract", None)

    assert callable(factory)

    contract = factory()
    rubrics = _rubrics_by_id(contract)

    assert contract["contract_id"] == "sales_methodology_rubric_v1"
    assert contract["scenario_type"] == "sales"
    assert contract["canonical_kernel_version"] == "evaluation_kernel_v1"
    assert contract["supported_surface_ids"] == ["realtime", "report", "history", "admin"]
    assert list(rubrics.keys()) == EXPECTED_RUBRIC_IDS

    discovery = rubrics["discovery_qualification"]
    assert discovery["stage_ids"] == ["opening", "discovery"]
    assert discovery["canonical_dimension_ids"] == [
        "customer_benefit_connection",
        "value_expression",
    ]
    assert discovery["focus_type"] == "value_translation_gap"
    assert discovery["main_issue_type"] == "value_translation_gap"
    assert discovery["next_goal_type"] == "value_to_benefit_translation"
    assert "qualification" in discovery["shipped_boundary"]

    objection = rubrics["objection_reframe"]
    assert objection["stage_ids"] == ["objection", "closing"]
    assert objection["canonical_dimension_ids"] == [
        "objection_handling",
        "evidence_usage",
    ]
    assert objection["focus_type"] == "objection_handling_gap"
    assert objection["main_issue_type"] == "objection_handling_gap"
    assert objection["next_goal_type"] == "objection_reframe"


def test_sales_methodology_contract_reuses_canonical_surface_readers() -> None:
    contract = effectiveness.get_sales_methodology_contract()
    surfaces = {item["surface_id"]: item for item in contract["surface_contracts"]}

    realtime = surfaces["realtime"]
    assert realtime["primary_reader_id"] == "sales_realtime_score_snapshot_v1"
    assert realtime["compatibility_reader_ids"] == [
        "practice_session_rollup_fields_v1",
        "effectiveness_snapshot_v1",
        "legacy_score_update_v1",
    ]
    assert realtime["evidence_paths"] == [
        "canonical_evaluation_kernel.dimensions[]",
        "compatibility_readers.sales_realtime_score_snapshot_v1.dimension_scores",
        "dimensions[]",
    ]

    report = surfaces["report"]
    assert report["primary_reader_id"] == "session_evidence_projection_v1"
    assert report["compatibility_reader_ids"] == [
        "practice_session_rollup_fields_v1",
        "effectiveness_snapshot_v1",
        "sales_realtime_score_snapshot_v1",
        "comprehensive_sales_report_v1",
    ]
    assert report["evidence_paths"] == [
        "canonical_evaluation_kernel.dimensions[]",
        "effectiveness_snapshot.main_issue",
        "effectiveness_snapshot.next_goal",
        "effectiveness_snapshot.claim_truth",
    ]

    history = surfaces["history"]
    admin = surfaces["admin"]
    assert history["primary_reader_id"] == report["primary_reader_id"]
    assert admin["primary_reader_id"] == report["primary_reader_id"]
    assert history["manager_view"] == "cohort_trends"
    assert admin["manager_view"] == "intervention_queue"
