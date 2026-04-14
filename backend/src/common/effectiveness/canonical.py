"""Canonical evaluation schema, kernel builders, and compatibility readers.

T01 defined the shared vocabulary for S03. T02 turns that vocabulary into one
runtime/read-model builder so realtime scoring, report, replay, history, and
admin can all project the same scenario-aware kernel while legacy readers keep
returning the old field shapes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal


CanonicalScenarioType = Literal["sales", "presentation"]
CanonicalRollupId = Literal["logic", "accuracy", "completeness"]
SurfaceMode = Literal["canonical_source", "canonical_consumer", "compat_mirror"]

CANONICAL_EVALUATION_KERNEL_VERSION = "evaluation_kernel_v1"
CANONICAL_ROLLUP_IDS: tuple[CanonicalRollupId, ...] = (
    "logic",
    "accuracy",
    "completeness",
)

_ROLLUP_LABELS: dict[CanonicalRollupId, str] = {
    "logic": "逻辑性",
    "accuracy": "准确性",
    "completeness": "完整性",
}


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
            "sales_methodology_rubric_v1",
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
            "sales_methodology_rubric_v1",
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
            "sales_methodology_rubric_v1",
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
            "sales_methodology_rubric_v1",
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
            "sales_methodology_rubric_v1",
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


def _normalize_scenario_type(value: str | CanonicalScenarioType) -> CanonicalScenarioType:
    normalized = str(value or "sales").strip().lower()
    return "presentation" if normalized == "presentation" else "sales"


def _infer_surface_id(
    *,
    scenario_type: CanonicalScenarioType,
    surface_id: str | None,
    source_reader_id: str | None,
) -> str:
    if isinstance(surface_id, str) and surface_id.strip():
        return surface_id.strip()
    reader_id = str(source_reader_id or "").strip().lower()
    if "realtime" in reader_id:
        return "realtime"
    if "presentation_review" in reader_id:
        return "report" if scenario_type == "presentation" else "realtime"
    if "comprehensive" in reader_id:
        return "comprehensive_report"
    return "report"


def _coerce_score(value: Any, fallback: float = 0.0) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = float(fallback)
    return round(max(0.0, min(100.0, normalized)), 2)


def _resolve_dimension_details_map(
    dimension_details: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    details_map: dict[str, dict[str, Any]] = {}
    if not isinstance(dimension_details, list):
        return details_map

    for item in dimension_details:
        if not isinstance(item, dict):
            continue
        keys = []
        for field in ("dimension_id", "label", "name"):
            raw = item.get(field)
            if isinstance(raw, str) and raw.strip():
                keys.append(raw.strip())
        for key in keys:
            details_map[key] = item
    return details_map


def get_canonical_dimension_definitions(
    scenario_type: CanonicalScenarioType | str,
) -> tuple[CanonicalDimensionDefinition, ...]:
    normalized_scenario = _normalize_scenario_type(scenario_type)
    if normalized_scenario == "sales":
        return _SALES_DIMENSIONS
    return _PRESENTATION_DIMENSIONS



def get_surface_reader_plan(
    *,
    surface_id: str,
    scenario_type: CanonicalScenarioType | str,
) -> SurfaceReaderPlan:
    normalized_scenario = _normalize_scenario_type(scenario_type)
    try:
        return _SURFACE_READER_PLANS[(surface_id, normalized_scenario)]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported evaluation surface plan: {surface_id}/{normalized_scenario}"
        ) from exc



def _resolve_dimension_weight(definition: CanonicalDimensionDefinition) -> float:
    total = sum(max(0.0, float(part.weight)) for part in definition.rollup_contributions)
    return round(total if total > 0 else 1.0, 4)



def _resolve_legacy_rollup_map(
    *,
    logic_score: float | None,
    accuracy_score: float | None,
    completeness_score: float | None,
    overall_score: float | None,
) -> dict[str, float]:
    rollups: dict[str, float] = {}
    if logic_score is not None:
        rollups["logic"] = _coerce_score(logic_score)
    if accuracy_score is not None:
        rollups["accuracy"] = _coerce_score(accuracy_score)
    if completeness_score is not None:
        rollups["completeness"] = _coerce_score(completeness_score)
    if overall_score is not None:
        rollups["overall"] = _coerce_score(overall_score)
    return rollups



def _resolve_explicit_dimension_score(
    definition: CanonicalDimensionDefinition,
    explicit_dimension_scores: dict[str, Any] | None,
) -> float | None:
    if not isinstance(explicit_dimension_scores, dict):
        return None

    candidates = (
        definition.dimension_id,
        definition.label,
        *definition.source_aliases,
    )
    for candidate in candidates:
        value = explicit_dimension_scores.get(candidate)
        if isinstance(value, (int, float)):
            return _coerce_score(value)
    return None



def _resolve_rollup_backfill_score(
    definition: CanonicalDimensionDefinition,
    legacy_rollups: dict[str, float],
) -> float | None:
    collected: list[float] = []
    for contribution in definition.rollup_contributions:
        rollup_value = legacy_rollups.get(contribution.rollup_id)
        if rollup_value is None:
            continue
        collected.append(_coerce_score(rollup_value))
    if not collected:
        return None
    return round(sum(collected) / len(collected), 2)



def _build_dimension_payloads(
    *,
    scenario_type: CanonicalScenarioType,
    overall_score: float,
    explicit_dimension_scores: dict[str, Any] | None,
    dimension_details: list[dict[str, Any]] | None,
    legacy_rollups: dict[str, float],
) -> list[dict[str, Any]]:
    detail_map = _resolve_dimension_details_map(dimension_details)
    payloads: list[dict[str, Any]] = []
    sales_rubric_map: dict[str, list[str]] = {}
    if scenario_type == "sales":
        from .methodology import build_sales_dimension_rubric_map

        sales_rubric_map = build_sales_dimension_rubric_map()

    for definition in get_canonical_dimension_definitions(scenario_type):
        detail = (
            detail_map.get(definition.dimension_id)
            or detail_map.get(definition.label)
            or {}
        )
        explicit_score = _resolve_explicit_dimension_score(
            definition,
            explicit_dimension_scores,
        )
        rollup_backfill = _resolve_rollup_backfill_score(definition, legacy_rollups)
        resolved_score = explicit_score
        if resolved_score is None:
            resolved_score = rollup_backfill
        if resolved_score is None:
            resolved_score = legacy_rollups.get("overall", overall_score)
        weight = detail.get("weight")
        description = detail.get("description")
        payload = {
            "dimension_id": definition.dimension_id,
            "label": definition.label,
            "score": _coerce_score(resolved_score, overall_score),
            "weight": round(
                float(weight)
                if isinstance(weight, (int, float))
                else _resolve_dimension_weight(definition),
                4,
            ),
            "rollup_contributions": [
                {"rollup_id": part.rollup_id, "weight": round(float(part.weight), 4)}
                for part in definition.rollup_contributions
            ],
            "source_aliases": list(definition.source_aliases),
            "legacy_field_aliases": list(definition.legacy_field_aliases),
        }
        if isinstance(description, str) and description.strip():
            payload["description"] = description.strip()
        if scenario_type == "sales":
            payload["methodology_rubric_ids"] = list(
                sales_rubric_map.get(definition.dimension_id, [])
            )
        payloads.append(payload)

    return payloads



def _derive_rollups_from_dimensions(
    dimension_payloads: list[dict[str, Any]],
) -> dict[str, float]:
    weighted_totals: dict[str, float] = {rollup_id: 0.0 for rollup_id in CANONICAL_ROLLUP_IDS}
    weight_totals: dict[str, float] = {rollup_id: 0.0 for rollup_id in CANONICAL_ROLLUP_IDS}

    for payload in dimension_payloads:
        score = _coerce_score(payload.get("score"))
        contributions = payload.get("rollup_contributions")
        if not isinstance(contributions, list):
            continue
        for item in contributions:
            if not isinstance(item, dict):
                continue
            rollup_id = str(item.get("rollup_id") or "").strip()
            if rollup_id not in CANONICAL_ROLLUP_IDS:
                continue
            weight = max(0.0, float(item.get("weight") or 0.0))
            weighted_totals[rollup_id] += score * weight
            weight_totals[rollup_id] += weight

    resolved: dict[str, float] = {}
    for rollup_id in CANONICAL_ROLLUP_IDS:
        total_weight = weight_totals[rollup_id]
        if total_weight <= 0:
            resolved[rollup_id] = 0.0
            continue
        resolved[rollup_id] = round(weighted_totals[rollup_id] / total_weight, 2)
    return resolved



def build_canonical_evaluation_kernel(
    *,
    scenario_type: CanonicalScenarioType | str,
    surface_id: str | None = None,
    source_reader_id: str | None = None,
    overall_score: float | None = None,
    dimension_scores: dict[str, Any] | None = None,
    dimension_details: list[dict[str, Any]] | None = None,
    logic_score: float | None = None,
    accuracy_score: float | None = None,
    completeness_score: float | None = None,
    methodology_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_scenario = _normalize_scenario_type(scenario_type)
    inferred_surface_id = _infer_surface_id(
        scenario_type=normalized_scenario,
        surface_id=surface_id,
        source_reader_id=source_reader_id,
    )
    surface_plan = get_surface_reader_plan(
        surface_id=inferred_surface_id,
        scenario_type=normalized_scenario,
    )
    selected_source_reader_id = source_reader_id or surface_plan.primary_reader_id

    legacy_rollups = _resolve_legacy_rollup_map(
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        overall_score=overall_score,
    )
    resolved_overall = _coerce_score(
        overall_score,
        fallback=(
            sum(
                value
                for key, value in legacy_rollups.items()
                if key in CANONICAL_ROLLUP_IDS
            )
            / max(
                1,
                len([key for key in legacy_rollups if key in CANONICAL_ROLLUP_IDS]),
            )
        ),
    )
    dimension_payloads = _build_dimension_payloads(
        scenario_type=normalized_scenario,
        overall_score=resolved_overall,
        explicit_dimension_scores=dimension_scores,
        dimension_details=dimension_details,
        legacy_rollups=legacy_rollups,
    )
    derived_rollups = _derive_rollups_from_dimensions(dimension_payloads)
    resolved_rollups = {
        "logic": _coerce_score(legacy_rollups.get("logic"), derived_rollups["logic"]),
        "accuracy": _coerce_score(
            legacy_rollups.get("accuracy"),
            derived_rollups["accuracy"],
        ),
        "completeness": _coerce_score(
            legacy_rollups.get("completeness"),
            derived_rollups["completeness"],
        ),
    }
    resolved_overall_score = _coerce_score(
        overall_score,
        fallback=sum(resolved_rollups.values()) / len(CANONICAL_ROLLUP_IDS),
    )

    kernel = {
        "schema_version": CANONICAL_EVALUATION_KERNEL_VERSION,
        "scenario_type": normalized_scenario,
        "surface_id": inferred_surface_id,
        "source_reader_id": selected_source_reader_id,
        "primary_reader_id": surface_plan.primary_reader_id,
        "mode": surface_plan.mode,
        "rollups": {
            rollup_id: {
                "label": _ROLLUP_LABELS[rollup_id],
                "score": resolved_rollups[rollup_id],
            }
            for rollup_id in CANONICAL_ROLLUP_IDS
        },
        "overall_score": resolved_overall_score,
        "dimensions": dimension_payloads,
        "compatibility_reader_ids": list(surface_plan.compatibility_reader_ids),
        "downstream_surfaces": list(surface_plan.downstream_surfaces),
    }
    if normalized_scenario == "sales":
        from .methodology import build_sales_methodology_summary

        kernel["methodology"] = build_sales_methodology_summary(
            canonical_kernel=kernel,
            surface_id=inferred_surface_id,
            current_stage=(methodology_context or {}).get("current_stage"),
            main_issue=(methodology_context or {}).get("main_issue"),
            next_goal=(methodology_context or {}).get("next_goal"),
            claim_truth=(methodology_context or {}).get("claim_truth"),
        )
    return kernel



def _build_dimension_score_map_from_kernel(
    kernel: dict[str, Any],
) -> dict[str, float]:
    dimension_scores: dict[str, float] = {}
    for item in kernel.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        dimension_scores[label] = _coerce_score(item.get("score"))
    return dimension_scores



def _build_rollup_fields_payload(kernel: dict[str, Any]) -> dict[str, float]:
    rollups = kernel.get("rollups") if isinstance(kernel, dict) else None
    if not isinstance(rollups, dict):
        rollups = {}
    return {
        "logic_score": _coerce_score((rollups.get("logic") or {}).get("score")),
        "accuracy_score": _coerce_score((rollups.get("accuracy") or {}).get("score")),
        "completeness_score": _coerce_score(
            (rollups.get("completeness") or {}).get("score")
        ),
        "overall_score": _coerce_score(kernel.get("overall_score")),
    }



def build_compatibility_readers(
    *,
    canonical_kernel: dict[str, Any],
    surface_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(canonical_kernel, dict):
        return {}

    scenario_type = _normalize_scenario_type(canonical_kernel.get("scenario_type", "sales"))
    resolved_surface_id = _infer_surface_id(
        scenario_type=scenario_type,
        surface_id=surface_id,
        source_reader_id=canonical_kernel.get("source_reader_id"),
    )
    surface_plan = get_surface_reader_plan(
        surface_id=resolved_surface_id,
        scenario_type=scenario_type,
    )
    rollup_fields = _build_rollup_fields_payload(canonical_kernel)
    dimension_score_map = _build_dimension_score_map_from_kernel(canonical_kernel)
    dimensions = canonical_kernel.get("dimensions") if isinstance(canonical_kernel, dict) else None
    if not isinstance(dimensions, list):
        dimensions = []

    readers: dict[str, Any] = {}
    reader_ids = tuple(
        dict.fromkeys(
            (surface_plan.primary_reader_id, *surface_plan.compatibility_reader_ids)
        )
    )
    for reader_id in reader_ids:
        if reader_id == "practice_session_rollup_fields_v1":
            readers[reader_id] = dict(rollup_fields)
        elif reader_id in {"sales_realtime_score_snapshot_v1", "legacy_score_update_v1"}:
            readers[reader_id] = {
                "overall_score": rollup_fields["overall_score"],
                "dimension_scores": dict(dimension_score_map),
            }
        elif reader_id == "effectiveness_snapshot_v1":
            readers[reader_id] = {
                **rollup_fields,
                "dimension_scores": dict(dimension_score_map),
            }
        elif reader_id == "presentation_review_dimensions_v1":
            readers[reader_id] = {
                "overall_score": rollup_fields["overall_score"],
                "dimension_scores": [
                    {
                        "name": item.get("label"),
                        "score": _coerce_score(item.get("score")),
                        "weight": float(item.get("weight") or 1.0),
                        **(
                            {"description": item.get("description")}
                            if isinstance(item.get("description"), str)
                            and item.get("description", "").strip()
                            else {}
                        ),
                    }
                    for item in dimensions
                    if isinstance(item, dict) and isinstance(item.get("label"), str)
                ],
            }
        elif reader_id == "comprehensive_sales_report_v1":
            readers[reader_id] = {
                "overall_score": rollup_fields["overall_score"],
                "dimension_scores": [
                    {
                        "name": item.get("label"),
                        "score": _coerce_score(item.get("score")),
                        "weight": float(item.get("weight") or 1.0),
                    }
                    for item in dimensions
                    if isinstance(item, dict) and isinstance(item.get("label"), str)
                ],
            }
        elif reader_id == "sales_methodology_rubric_v1":
            methodology = canonical_kernel.get("methodology")
            readers[reader_id] = deepcopy(methodology) if isinstance(methodology, dict) else {}
        else:
            readers[reader_id] = dict(rollup_fields)

    return readers



def build_canonical_views(
    *,
    scenario_type: CanonicalScenarioType | str,
    surface_id: str,
    source_reader_id: str | None = None,
    overall_score: float | None = None,
    dimension_scores: dict[str, Any] | None = None,
    dimension_details: list[dict[str, Any]] | None = None,
    logic_score: float | None = None,
    accuracy_score: float | None = None,
    completeness_score: float | None = None,
    methodology_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    kernel = build_canonical_evaluation_kernel(
        scenario_type=scenario_type,
        surface_id=surface_id,
        source_reader_id=source_reader_id,
        overall_score=overall_score,
        dimension_scores=dimension_scores,
        dimension_details=dimension_details,
        logic_score=logic_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        methodology_context=methodology_context,
    )
    return kernel, build_compatibility_readers(
        canonical_kernel=kernel,
        surface_id=surface_id,
    )


__all__ = [
    "CANONICAL_EVALUATION_KERNEL_VERSION",
    "CANONICAL_ROLLUP_IDS",
    "CanonicalDimensionDefinition",
    "CanonicalRollupId",
    "CanonicalScenarioType",
    "RollupContribution",
    "SurfaceMode",
    "SurfaceReaderPlan",
    "build_canonical_evaluation_kernel",
    "build_canonical_views",
    "build_compatibility_readers",
    "get_canonical_dimension_definitions",
    "get_surface_reader_plan",
]
