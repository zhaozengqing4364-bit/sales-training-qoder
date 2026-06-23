from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, TypeAlias, TypedDict, assert_never

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = (
    JsonPrimitive | Mapping[str, "JsonValue"] | Sequence["JsonValue"]
)
JsonObject: TypeAlias = Mapping[str, JsonValue]
ReportProjectionRole: TypeAlias = Literal["learner", "admin", "supervisor", "ops"]

MIN_CONFIDENCE_WITHOUT_REVIEW: Final = 0.65
TOTAL_SCORE_TOLERANCE: Final = 0.01


@dataclass(frozen=True, slots=True)
class RubricItem:
    rubric_id: str
    display_name: str
    max_score: float


V1_RUBRIC: Final[tuple[RubricItem, ...]] = (
    RubricItem("opening_intent", "开场与来意", 15),
    RubricItem("current_state_discovery", "现状澄清", 20),
    RubricItem("risk_identification", "风险识别", 20),
    RubricItem("value_explanation", "价值说明", 20),
    RubricItem("credibility_response", "可信度回应", 15),
    RubricItem("next_step_advancement", "下一步推进", 10),
)
RUBRIC_BY_ID: Final[Mapping[str, RubricItem]] = {
    item.rubric_id: item for item in V1_RUBRIC
}
RUBRIC_TOTAL_SCORE: Final = sum(item.max_score for item in V1_RUBRIC)


@dataclass(frozen=True, slots=True)
class EvidenceQuote:
    quote_id: str
    speaker: str
    text: str
    turn_index: int


@dataclass(frozen=True, slots=True)
class RubricScore:
    rubric_id: str
    score: float
    evidence_quote_ids: tuple[str, ...]
    suggestion: str


@dataclass(frozen=True, slots=True)
class OfflineScoringDraft:
    total_score: float
    dimension_scores: tuple[RubricScore, ...]
    evidence_quotes: tuple[EvidenceQuote, ...]
    suggestions: tuple[str, ...]
    strengths: tuple[str, ...]
    confidence: float
    scoring_json: JsonObject
    state_card: JsonObject
    roleplay_contract_hash: str
    quality_flags: tuple[str, ...] = ()
    transcript: tuple[TranscriptTurn, ...] = ()
    ai_quality: JsonObject = field(default_factory=dict)
    ops_metrics: JsonObject = field(default_factory=dict)
    redacted_logs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AcceptedScoringReport:
    total_score: float
    dimension_scores: tuple[RubricScore, ...]
    evidence_quotes: tuple[EvidenceQuote, ...]
    suggestions: tuple[str, ...]
    strengths: tuple[str, ...]
    confidence: float
    manual_review_required: bool
    manual_review_reasons: tuple[str, ...]
    scoring_json: JsonObject
    state_card: JsonObject
    roleplay_contract_hash: str
    quality_flags: tuple[str, ...]
    transcript: tuple[TranscriptTurn, ...]
    ai_quality: JsonObject
    ops_metrics: JsonObject
    redacted_logs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RejectedScoringReport:
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoringValidationResult:
    accepted_report: AcceptedScoringReport | None
    rejected_report: RejectedScoringReport | None


class EvidenceProjection(TypedDict):
    quote_id: str
    speaker: str
    text: str
    turn_index: int


class DimensionProjection(TypedDict):
    rubric_id: str
    display_name: str
    score: float
    max_score: float
    suggestion: str
    evidence_quote_ids: tuple[str, ...]


class TranscriptTurn(TypedDict):
    speaker: str
    text: str
    turn_index: int


class LearnerReportProjection(TypedDict):
    total_score: float
    dimension_scores: tuple[DimensionProjection, ...]
    suggestions: tuple[str, ...]
    evidence: tuple[EvidenceProjection, ...]


class AdminReportProjection(TypedDict):
    total_score: float
    dimension_scores: tuple[DimensionProjection, ...]
    suggestions: tuple[str, ...]
    strengths: tuple[str, ...]
    evidence: tuple[EvidenceProjection, ...]
    transcript: tuple[TranscriptTurn, ...]
    scoring_json: JsonObject
    state_card: JsonObject
    roleplay_contract_hash: str
    ai_quality: JsonObject
    quality_flags: tuple[str, ...]
    scoring_confidence: float
    manual_review_required: bool
    manual_review_reasons: tuple[str, ...]


class OpsReportProjection(TypedDict):
    quality_flags: tuple[str, ...]
    metrics: JsonObject
    redacted_logs: tuple[str, ...]


ReportProjection: TypeAlias = (
    LearnerReportProjection | AdminReportProjection | OpsReportProjection
)


@dataclass(frozen=True, slots=True)
class PermissionedReportProjectionResult:
    allowed: bool
    projection: ReportProjection | None
    reason_code: str | None = None


def validate_offline_scoring_report(
    draft: OfflineScoringDraft,
) -> ScoringValidationResult:
    reason_codes: list[str] = []
    reason_codes.extend(_rubric_reason_codes(draft.dimension_scores))
    reason_codes.extend(_score_reason_codes(draft))
    reason_codes.extend(_evidence_reason_codes(draft))

    if reason_codes:
        return ScoringValidationResult(
            accepted_report=None,
            rejected_report=RejectedScoringReport(reason_codes=tuple(reason_codes)),
        )

    manual_review_reasons = _manual_review_reasons(draft)
    return ScoringValidationResult(
        accepted_report=AcceptedScoringReport(
            total_score=draft.total_score,
            dimension_scores=draft.dimension_scores,
            evidence_quotes=draft.evidence_quotes,
            suggestions=draft.suggestions,
            strengths=draft.strengths,
            confidence=draft.confidence,
            manual_review_required=bool(manual_review_reasons),
            manual_review_reasons=manual_review_reasons,
            scoring_json=dict(draft.scoring_json),
            state_card=dict(draft.state_card),
            roleplay_contract_hash=draft.roleplay_contract_hash,
            quality_flags=draft.quality_flags,
            transcript=draft.transcript,
            ai_quality=dict(draft.ai_quality),
            ops_metrics=dict(draft.ops_metrics),
            redacted_logs=draft.redacted_logs,
        ),
        rejected_report=None,
    )


def build_learner_projection(
    report: AcceptedScoringReport,
) -> LearnerReportProjection:
    return {
        "total_score": report.total_score,
        "dimension_scores": _dimension_projection(report.dimension_scores),
        "suggestions": report.suggestions,
        "evidence": _learner_evidence_projection(report),
    }


def build_admin_projection(report: AcceptedScoringReport) -> AdminReportProjection:
    return {
        "total_score": report.total_score,
        "dimension_scores": _dimension_projection(report.dimension_scores),
        "suggestions": report.suggestions,
        "strengths": report.strengths,
        "evidence": _learner_evidence_projection(report),
        "transcript": report.transcript,
        "scoring_json": report.scoring_json,
        "state_card": report.state_card,
        "roleplay_contract_hash": report.roleplay_contract_hash,
        "ai_quality": report.ai_quality,
        "quality_flags": report.quality_flags,
        "scoring_confidence": report.confidence,
        "manual_review_required": report.manual_review_required,
        "manual_review_reasons": report.manual_review_reasons,
    }


def build_ops_projection(report: AcceptedScoringReport) -> OpsReportProjection:
    return {
        "quality_flags": report.quality_flags,
        "metrics": report.ops_metrics,
        "redacted_logs": report.redacted_logs,
    }


def build_permissioned_report_projection(
    report: AcceptedScoringReport,
    *,
    viewer_role: str,
) -> PermissionedReportProjectionResult:
    role = _normalize_report_projection_role(viewer_role)
    match role:
        case "learner":
            projection: ReportProjection = build_learner_projection(report)
        case "admin" | "supervisor":
            projection = build_admin_projection(report)
        case "ops":
            projection = build_ops_projection(report)
        case None:
            return PermissionedReportProjectionResult(
                allowed=False,
                projection=None,
                reason_code="report_projection_role_denied",
            )
        case unreachable:
            assert_never(unreachable)
    return PermissionedReportProjectionResult(
        allowed=True,
        projection=projection,
    )


def _normalize_report_projection_role(role: str) -> ReportProjectionRole | None:
    normalized = role.strip().lower()
    match normalized:
        case "learner":
            return "learner"
        case "admin":
            return "admin"
        case "supervisor":
            return "supervisor"
        case "ops" | "operations":
            return "ops"
        case _:
            return None


def _rubric_reason_codes(scores: Sequence[RubricScore]) -> tuple[str, ...]:
    ids = tuple(score.rubric_id for score in scores)
    expected_ids = tuple(item.rubric_id for item in V1_RUBRIC)
    reason_codes: list[str] = []
    if len(ids) != len(set(ids)):
        reason_codes.append("duplicate_rubric_score")
    if set(ids) != set(expected_ids):
        reason_codes.append("rubric_set_mismatch")
    return tuple(reason_codes)


def _score_reason_codes(draft: OfflineScoringDraft) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if not _valid_score_value(draft.total_score, RUBRIC_TOTAL_SCORE):
        reason_codes.append("invalid_total_score")
    if not 0 <= draft.confidence <= 1:
        reason_codes.append("invalid_confidence")
    for score in draft.dimension_scores:
        rubric = RUBRIC_BY_ID.get(score.rubric_id)
        if rubric is None:
            continue
        if not _valid_score_value(score.score, rubric.max_score):
            reason_codes.append(f"invalid_score:{score.rubric_id}")
    dimension_total = sum(score.score for score in draft.dimension_scores)
    if abs(dimension_total - draft.total_score) > TOTAL_SCORE_TOLERANCE:
        reason_codes.append("total_score_mismatch")
    return tuple(reason_codes)


def _evidence_reason_codes(draft: OfflineScoringDraft) -> tuple[str, ...]:
    reason_codes: list[str] = []
    quotes_by_id = {quote.quote_id: quote for quote in draft.evidence_quotes}
    if len(quotes_by_id) != len(draft.evidence_quotes):
        reason_codes.append("duplicate_evidence_quote")
    for quote in draft.evidence_quotes:
        if not quote.quote_id.strip() or not quote.text.strip():
            reason_codes.append("invalid_evidence_quote")
        if quote.speaker != "learner":
            reason_codes.append("ai_customer_evidence")
    for score in draft.dimension_scores:
        if not score.evidence_quote_ids:
            reason_codes.append(f"missing_evidence:{score.rubric_id}")
        for quote_id in score.evidence_quote_ids:
            quote_candidate = quotes_by_id.get(quote_id)
            if quote_candidate is None:
                reason_codes.append(f"unknown_evidence:{score.rubric_id}")
                continue
            if quote_candidate.speaker != "learner":
                reason_codes.append("ai_customer_evidence")
    return tuple(dict.fromkeys(reason_codes))


def _manual_review_reasons(draft: OfflineScoringDraft) -> tuple[str, ...]:
    reasons: list[str] = []
    if draft.confidence < MIN_CONFIDENCE_WITHOUT_REVIEW:
        reasons.append("low_confidence")
    if any(flag.startswith("blocking_violation_count:") for flag in draft.quality_flags):
        reasons.append("blocking_roleplay_quality_flag")
    return tuple(reasons)


def _dimension_projection(
    scores: Sequence[RubricScore],
) -> tuple[DimensionProjection, ...]:
    projected: list[DimensionProjection] = []
    for score in scores:
        rubric = RUBRIC_BY_ID[score.rubric_id]
        projected.append(
            {
                "rubric_id": score.rubric_id,
                "display_name": rubric.display_name,
                "score": score.score,
                "max_score": rubric.max_score,
                "suggestion": score.suggestion,
                "evidence_quote_ids": score.evidence_quote_ids,
            }
        )
    return tuple(projected)


def _learner_evidence_projection(
    report: AcceptedScoringReport,
) -> tuple[EvidenceProjection, ...]:
    referenced_quote_ids = {
        quote_id
        for score in report.dimension_scores
        for quote_id in score.evidence_quote_ids
    }
    return tuple(
        {
            "quote_id": quote.quote_id,
            "speaker": quote.speaker,
            "text": quote.text,
            "turn_index": quote.turn_index,
        }
        for quote in report.evidence_quotes
        if quote.quote_id in referenced_quote_ids and quote.speaker == "learner"
    )


def _valid_score_value(value: float, max_score: float) -> bool:
    return math.isfinite(value) and 0 <= value <= max_score
