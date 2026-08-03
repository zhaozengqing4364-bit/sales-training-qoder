"""Deterministic, revisioned readiness policy; AI cannot change its result."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from typing import Literal

from competency_evidence.contracts import CompetencyEvidenceProjection
from competency_evidence.identifiers import STANDARD_COMPETENCIES
from readiness.contracts import (
    CompetencyReadinessProjection,
    ReadinessEligibility,
    ReadinessPolicyResult,
    ReadinessProjectionInput,
)


def readiness_policy_snapshot() -> dict[str, object]:
    return {
        "policy_key": "newcomer-foundation-readiness-v1",
        "revision": 1,
        "required_activity_rule": "all_required_completed",
        "competency_rule": "latest_valid_no_known_shortfall",
        "quality_rule": "degraded_or_low_confidence_cannot_stand_alone",
        "processing_rule": "no_required_activity_processing",
        "standard_competency_keys": [
            item.stable_key for item in STANDARD_COMPETENCIES
        ],
    }


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def evaluate_readiness(input_value: ReadinessProjectionInput) -> ReadinessPolicyResult:
    evidence_set_hash = canonical_hash(
        [
            {
                "evidence_id": item.evidence_id,
                "outcome_id": item.outcome_id,
                "outcome_version": item.outcome_version,
                "competency_revision_id": item.competency_revision_id,
                "validity": item.validity,
                "quality": item.quality,
                "result": item.observed_result,
                "score": item.observed_score,
                "confidence": item.confidence,
            }
            for item in sorted(input_value.evidence, key=lambda row: row.evidence_id)
        ]
    )
    current_evidence = _current_evidence(input_value.evidence)
    by_competency: dict[str, list[CompetencyEvidenceProjection]] = defaultdict(list)
    for item in current_evidence:
        by_competency[item.competency_key].append(item)

    projections = tuple(
        _project_competency(definition, by_competency[definition.stable_key])
        for definition in STANDARD_COMPETENCIES
    )
    missing_activities = tuple(
        item.activity_id
        for item in input_value.activities
        if item.required and item.status != "completed"
    )
    processing = tuple(
        item.activity_id
        for item in input_value.activities
        if item.required and item.processing
    )
    latest_by_source: dict[tuple[str, str], CompetencyEvidenceProjection] = {}
    for item in current_evidence:
        key = (item.source_activity_id, item.competency_key)
        current = latest_by_source.get(key)
        if current is None or (item.observed_at, item.outcome_version) > (
            current.observed_at,
            current.outcome_version,
        ):
            latest_by_source[key] = item
    quality_conflicts = tuple(
        item.evidence_id
        for item in latest_by_source.values()
        if item.validity in {"pending_review", "insufficient_quality"}
    )
    competency_gaps = tuple(
        item.competency_key
        for item in projections
        if not item.review_prerequisite_met
    )
    required_complete = not missing_activities
    competencies_sufficient = not competency_gaps
    no_processing = not processing
    no_quality_conflicts = not quality_conflicts
    reasons: list[str] = []
    if missing_activities:
        reasons.append("仍有必修训练活动未完成。")
    if competency_gaps:
        reasons.append("仍有基础能力缺少足够且有效的训练证据。")
    if processing:
        reasons.append("仍有训练结果正在处理。")
    if quality_conflicts:
        reasons.append("仍有录音质量、置信度或人工确认事项待处理。")
    eligible = (
        required_complete
        and competencies_sufficient
        and no_processing
        and no_quality_conflicts
    )
    eligibility = ReadinessEligibility(
        eligible=eligible,
        required_activities_complete=required_complete,
        competencies_sufficient=competencies_sufficient,
        no_blocking_tasks=no_processing,
        no_unresolved_quality_conflicts=no_quality_conflicts,
        missing_activity_ids=missing_activities,
        competency_gaps=competency_gaps,
        quality_conflict_evidence_ids=quality_conflicts,
        reasons=tuple(reasons),
    )
    critical = tuple(
        sorted(
            {
                flag
                for item in current_evidence
                if item.validity == "valid"
                for flag in item.critical_flags
            }
        )
    )
    risk_reasons = critical or tuple(reasons)
    risk_band = "high" if critical else "low" if eligible else "medium"
    return ReadinessPolicyResult(
        evidence_set_hash=evidence_set_hash,
        competencies=projections,
        eligibility=eligibility,
        risk_band=risk_band,
        risk_reasons=risk_reasons,
    )


def _current_evidence(
    evidence: Sequence[CompetencyEvidenceProjection],
) -> tuple[CompetencyEvidenceProjection, ...]:
    return tuple(
        item
        for item in evidence
        if item.validity not in {"superseded", "invalidated"}
    )


def _project_competency(
    definition: object,
    evidence: Sequence[CompetencyEvidenceProjection],
) -> CompetencyReadinessProjection:
    stable_key = str(getattr(definition, "stable_key"))
    title = str(getattr(definition, "title"))
    description = str(getattr(definition, "description"))
    minimum_valid = int(getattr(definition, "minimum_valid_evidence"))
    ordered = sorted(
        evidence,
        key=lambda item: (item.observed_at, item.outcome_version, item.evidence_id),
    )
    valid = [item for item in ordered if item.validity == "valid"]
    unresolved = [
        item
        for item in ordered
        if item.validity in {"pending_review", "insufficient_quality"}
    ]
    latest = ordered[-1] if ordered else None
    latest_valid = valid[-1] if valid else None
    known_shortfall = latest_valid is not None and (
        latest_valid.observed_result == "not_passed"
    )
    enough = len(valid) >= minimum_valid
    if unresolved and (latest is None or latest in unresolved):
        status = "quality_review"
        gap_reason = "最新训练结果仍需处理质量或人工确认事项。"
    elif not evidence:
        status = "missing"
        gap_reason = "尚无该能力的训练证据。"
    elif not enough:
        status = "gap"
        gap_reason = "有效训练证据数量不足。"
    elif known_shortfall:
        status = "gap"
        gap_reason = "最新有效结果仍未达到训练要求。"
    else:
        status = "sufficient"
        gap_reason = None
    return CompetencyReadinessProjection(
        competency_key=stable_key,
        title=title,
        description=description,
        status=status,
        latest_result=(latest.observed_result if latest is not None else None),
        latest_score=(latest.observed_score if latest is not None else None),
        latest_max_score=(
            latest.observed_max_score if latest is not None else None
        ),
        trend=_trend(valid),
        source_coverage=tuple(sorted({item.evidence_type for item in valid})),
        evidence_count=len(evidence),
        valid_evidence_count=len(valid),
        evidence_ids=tuple(item.evidence_id for item in ordered),
        gap_reason=gap_reason,
        review_prerequisite_met=status == "sufficient",
    )


Trend = Literal["improving", "declining", "stable", "insufficient_data"]


def _trend(
    evidence: Sequence[CompetencyEvidenceProjection],
) -> Trend:
    numeric = [
        (item.observed_score, item.observed_max_score)
        for item in evidence
        if item.observed_score is not None
        and item.observed_max_score is not None
        and item.observed_max_score > 0
    ]
    if len(numeric) < 2:
        return "insufficient_data"
    previous = float(numeric[-2][0]) / float(numeric[-2][1])
    current = float(numeric[-1][0]) / float(numeric[-1][1])
    if current > previous + 0.02:
        return "improving"
    if current < previous - 0.02:
        return "declining"
    return "stable"


__all__ = [
    "canonical_hash",
    "evaluate_readiness",
    "readiness_policy_snapshot",
]
