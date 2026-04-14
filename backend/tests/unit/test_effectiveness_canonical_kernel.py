from __future__ import annotations

from common.conversation.session_evidence import describe_projection_kernel_contract
from common.effectiveness import (
    CANONICAL_EVALUATION_KERNEL_VERSION,
    get_canonical_dimension_definitions,
    get_surface_reader_plan,
)


def test_canonical_dimension_definitions_share_rollups_across_sales_and_presentation() -> None:
    sales_dimensions = get_canonical_dimension_definitions("sales")
    presentation_dimensions = get_canonical_dimension_definitions("presentation")

    assert CANONICAL_EVALUATION_KERNEL_VERSION == "evaluation_kernel_v1"
    assert [item.dimension_id for item in sales_dimensions] == [
        "value_expression",
        "customer_benefit_connection",
        "evidence_usage",
        "objection_handling",
        "next_step_commitment",
    ]
    assert [item.dimension_id for item in presentation_dimensions] == [
        "fluency_coherence",
        "factual_accuracy",
        "professionalism",
        "vividness",
        "qa_handling",
        "overall_presence",
    ]

    sales_rollups = {
        item.dimension_id: [(part.rollup_id, part.weight) for part in item.rollup_contributions]
        for item in sales_dimensions
    }
    presentation_rollups = {
        item.dimension_id: [(part.rollup_id, part.weight) for part in item.rollup_contributions]
        for item in presentation_dimensions
    }

    assert sales_rollups["customer_benefit_connection"] == [
        ("logic", 0.4),
        ("accuracy", 0.45),
    ]
    assert presentation_rollups["fluency_coherence"] == [("logic", 1.0)]
    assert presentation_rollups["overall_presence"] == [("completeness", 0.25)]


def test_surface_reader_plan_marks_canonical_consumers_and_compat_mirrors() -> None:
    report_plan = get_surface_reader_plan(surface_id="report", scenario_type="sales")
    admin_plan = get_surface_reader_plan(surface_id="admin", scenario_type="presentation")
    legacy_plan = get_surface_reader_plan(
        surface_id="comprehensive_report",
        scenario_type="sales",
    )

    assert report_plan.mode == "canonical_consumer"
    assert report_plan.primary_reader_id == "session_evidence_projection_v1"
    assert admin_plan.mode == "canonical_consumer"
    assert admin_plan.primary_reader_id == "session_evidence_projection_v1"
    assert legacy_plan.mode == "compat_mirror"
    assert legacy_plan.primary_reader_id == "comprehensive_sales_report_v1"


def test_projection_kernel_contract_exposes_shared_kernel_metadata() -> None:
    sales_contract = describe_projection_kernel_contract("sales")
    presentation_contract = describe_projection_kernel_contract("presentation")

    assert sales_contract == {
        "schema_version": "evaluation_kernel_v1",
        "surface": "session_evidence_projection",
        "scenario_type": "sales",
        "primary_reader_id": "session_evidence_projection_v1",
        "mode": "canonical_consumer",
        "dimension_ids": [
            "value_expression",
            "customer_benefit_connection",
            "evidence_usage",
            "objection_handling",
            "next_step_commitment",
        ],
        "rollup_ids": ["logic", "accuracy", "completeness"],
        "compatibility_reader_ids": [
            "practice_session_rollup_fields_v1",
            "effectiveness_snapshot_v1",
            "sales_realtime_score_snapshot_v1",
            "comprehensive_sales_report_v1",
        ],
        "downstream_surfaces": ["report", "replay", "history", "admin"],
    }
    assert presentation_contract == {
        "schema_version": "evaluation_kernel_v1",
        "surface": "session_evidence_projection",
        "scenario_type": "presentation",
        "primary_reader_id": "session_evidence_projection_v1",
        "mode": "canonical_consumer",
        "dimension_ids": [
            "fluency_coherence",
            "factual_accuracy",
            "professionalism",
            "vividness",
            "qa_handling",
            "overall_presence",
        ],
        "rollup_ids": ["logic", "accuracy", "completeness"],
        "compatibility_reader_ids": [
            "practice_session_rollup_fields_v1",
            "presentation_review_dimensions_v1",
        ],
        "downstream_surfaces": ["report", "replay", "history", "admin"],
    }
