"""Canonical evaluation schema and compatibility reader inventory.

T01 defines the shared schema vocabulary that S03 will use to collapse report,
replay, history, admin, and realtime scoring onto one scenario-aware kernel.
This module is intentionally read-model focused: it declares the canonical
rollup contract, the per-scenario dimension catalogs, and which existing
surfaces are canonical consumers versus temporary compatibility mirrors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CanonicalScenarioType = Literal["sales", "presentation"]
CanonicalRollupId = Literal["logic", "accuracy", "completeness"]
SurfaceMode = Literal["canonical_source", "canonical_consumer", "compat_mirror"]

CANONICAL_EVALUATION_KERNEL_VERSION = "evaluation_kernel_v1"
CANONICAL_ROLLUP_IDS: tuple[CanonicalRollupId, ...] = (
    "logic",
    "accuracy",
    "completeness",
)


@dataclass(frozen=True)
class RollupContribution:
    rollup_id: CanonicalRollupId
    weight: float


@dataclass(frozen=True)
class CanonicalDimensionDefinition:
    dimension_id: str
    label: str
    scenario_type: CanonicalScenarioType
    rollup_contributions: tuple[RollupContribution, ...]
    source_aliases: tuple[str, ...] = ()
    legacy_field_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SurfaceReaderPlan:
    surface_id: str
    scenario_type: CanonicalScenarioType
    mode: SurfaceMode
    primary_reader_id: str
    compatibility_reader_ids: tuple[str, ...]
    downstream_surfaces: tuple[str, ...] = ()


_SALES_DIMENSIONS: tuple[CanonicalDimensionDefinition, ...] = (
    CanonicalDimensionDefinition(
        dimension_id="value_expression",
        label="价值表达",
        scenario_type="sales",
        rollup_contributions=(RollupContribution("logic", 0.6),),
        source_aliases=("价值表达", "value_expression", "value_articulation"),
        legacy_field_aliases=("logic_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="customer_benefit_connection",
        label="客户收益连接",
        scenario_type="sales",
        rollup_contributions=(
            RollupContribution("logic", 0.4),
            RollupContribution("accuracy", 0.45),
        ),
        source_aliases=("客户收益连接", "customer_benefit", "benefit_linkage"),
        legacy_field_aliases=("logic_score", "accuracy_score"),
    ),
    CanonicalDimensionDefinition(
        dimension_id="evidence_usage",
        label="证据使用",
        scenario_type="sales",
        rollup_contributions=(RollupContribution("accuracy", 0.55),),
        source_aliases=("证据使用", "evidence_usage", "proof_usage"),
        legacy_field_aliases=("accuracy_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="objection_handling",
        label="异议处理",
        scenario_type="sales",
        rollup_contributions=(RollupContribution("completeness", 0.6),),
        source_aliases=("异议处理", "objection_handling", "objection_response"),
        legacy_field_aliases=("completeness_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="next_step_commitment",
        label="推进下一步",
        scenario_type="sales",
        rollup_contributions=(RollupContribution("completeness", 0.4),),
        source_aliases=("推进下一步", "next_step", "advance_next_step"),
        legacy_field_aliases=("completeness_score",),
    ),
)

_PRESENTATION_DIMENSIONS: tuple[CanonicalDimensionDefinition, ...] = (
    CanonicalDimensionDefinition(
        dimension_id="fluency_coherence",
        label="流畅连贯性",
        scenario_type="presentation",
        rollup_contributions=(RollupContribution("logic", 1.0),),
        source_aliases=("流畅连贯性",),
        legacy_field_aliases=("logic_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="factual_accuracy",
        label="准确性",
        scenario_type="presentation",
        rollup_contributions=(RollupContribution("accuracy", 1.0),),
        source_aliases=("准确性",),
        legacy_field_aliases=("accuracy_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="professionalism",
        label="专业性",
        scenario_type="presentation",
        rollup_contributions=(RollupContribution("completeness", 0.25),),
        source_aliases=("专业性",),
        legacy_field_aliases=("completeness_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="vividness",
        label="生动性",
        scenario_type="presentation",
        rollup_contributions=(RollupContribution("completeness", 0.25),),
        source_aliases=("生动性",),
        legacy_field_aliases=("completeness_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="qa_handling",
        label="互动问答",
        scenario_type="presentation",
        rollup_contributions=(RollupContribution("completeness", 0.25),),
        source_aliases=("互动问答",),
        legacy_field_aliases=("completeness_score",),
    ),
    CanonicalDimensionDefinition(
        dimension_id="overall_presence",
        label="其他表现",
        scenario_type="presentation",
        rollup_contributions=(RollupContribution("completeness", 0.25),),
        source_aliases=("其他表现",),
        legacy_field_aliases=("completeness_score",),
    ),
)

_SURFACE_READER_PLANS: dict[tuple[str, CanonicalScenarioType], SurfaceReaderPlan] = {
    (
        "realtime",
        "sales",
    ): SurfaceReaderPlan(
        surface_id="realtime",
        scenario_type="sales",
        mode="canonical_source",
        primary_reader_id="sales_realtime_score_snapshot_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "effectiveness_snapshot_v1",
            "legacy_score_update_v1",
        ),
    ),
    (
        "realtime",
        "presentation",
    ): SurfaceReaderPlan(
        surface_id="realtime",
        scenario_type="presentation",
        mode="canonical_source",
        primary_reader_id="presentation_review_dimensions_v1",
        compatibility_reader_ids=("practice_session_rollup_fields_v1",),
    ),
    (
        "report",
        "sales",
    ): SurfaceReaderPlan(
        surface_id="report",
        scenario_type="sales",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "effectiveness_snapshot_v1",
            "sales_realtime_score_snapshot_v1",
            "comprehensive_sales_report_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "replay",
        "sales",
    ): SurfaceReaderPlan(
        surface_id="replay",
        scenario_type="sales",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "effectiveness_snapshot_v1",
            "sales_realtime_score_snapshot_v1",
            "comprehensive_sales_report_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "history",
        "sales",
    ): SurfaceReaderPlan(
        surface_id="history",
        scenario_type="sales",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "effectiveness_snapshot_v1",
            "sales_realtime_score_snapshot_v1",
            "comprehensive_sales_report_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "admin",
        "sales",
    ): SurfaceReaderPlan(
        surface_id="admin",
        scenario_type="sales",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "effectiveness_snapshot_v1",
            "sales_realtime_score_snapshot_v1",
            "comprehensive_sales_report_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "report",
        "presentation",
    ): SurfaceReaderPlan(
        surface_id="report",
        scenario_type="presentation",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "presentation_review_dimensions_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "replay",
        "presentation",
    ): SurfaceReaderPlan(
        surface_id="replay",
        scenario_type="presentation",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "presentation_review_dimensions_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "history",
        "presentation",
    ): SurfaceReaderPlan(
        surface_id="history",
        scenario_type="presentation",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "presentation_review_dimensions_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "admin",
        "presentation",
    ): SurfaceReaderPlan(
        surface_id="admin",
        scenario_type="presentation",
        mode="canonical_consumer",
        primary_reader_id="session_evidence_projection_v1",
        compatibility_reader_ids=(
            "practice_session_rollup_fields_v1",
            "presentation_review_dimensions_v1",
        ),
        downstream_surfaces=("report", "replay", "history", "admin"),
    ),
    (
        "comprehensive_report",
        "sales",
    ): SurfaceReaderPlan(
        surface_id="comprehensive_report",
        scenario_type="sales",
        mode="compat_mirror",
        primary_reader_id="comprehensive_sales_report_v1",
        compatibility_reader_ids=("session_evidence_projection_v1",),
    ),
}


def get_canonical_dimension_definitions(
    scenario_type: CanonicalScenarioType,
) -> tuple[CanonicalDimensionDefinition, ...]:
    if scenario_type == "sales":
        return _SALES_DIMENSIONS
    return _PRESENTATION_DIMENSIONS


def get_surface_reader_plan(
    *,
    surface_id: str,
    scenario_type: CanonicalScenarioType,
) -> SurfaceReaderPlan:
    try:
        return _SURFACE_READER_PLANS[(surface_id, scenario_type)]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported evaluation surface plan: {surface_id}/{scenario_type}"
        ) from exc


__all__ = [
    "CANONICAL_EVALUATION_KERNEL_VERSION",
    "CANONICAL_ROLLUP_IDS",
    "CanonicalDimensionDefinition",
    "CanonicalRollupId",
    "CanonicalScenarioType",
    "RollupContribution",
    "SurfaceMode",
    "SurfaceReaderPlan",
    "get_canonical_dimension_definitions",
    "get_surface_reader_plan",
]
