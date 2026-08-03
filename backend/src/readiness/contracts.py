"""Provider-neutral readiness boundary contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from competency_evidence.contracts import CompetencyEvidenceProjection


class ReadinessActor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    actor_id: str = Field(min_length=1, max_length=120)
    capabilities: frozenset[str] = Field(default_factory=frozenset)
    unrestricted_scope: bool = False
    learner_ids: frozenset[str] = Field(default_factory=frozenset)
    is_human: bool = True
    trace_id: str | None = Field(default=None, max_length=160)

    def allows_learner(self, learner_id: str) -> bool:
        return self.unrestricted_scope or learner_id in self.learner_ids


class ReadinessActivityInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    activity_id: str
    activity_type: str
    title: str
    required: bool
    status: str
    latest_attempt_id: str | None = None
    latest_outcome_id: str | None = None
    latest_outcome_version: int | None = None
    latest_outcome_at: datetime | None = None
    processing: bool = False


class ReadinessProjectionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str
    learner_id: str
    learner_name: str
    enrollment_id: str
    cohort_id: str
    cohort_name: str | None = None
    path_revision_id: str
    path_title: str
    path_revision_label: str
    enrollment_status: str
    activities: tuple[ReadinessActivityInput, ...]
    evidence: tuple[CompetencyEvidenceProjection, ...]
    generated_at: datetime


class CompetencyReadinessProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    competency_key: str
    title: str
    description: str
    status: Literal["sufficient", "gap", "quality_review", "missing"]
    latest_result: str | None
    latest_score: float | None
    latest_max_score: float | None
    trend: Literal["improving", "declining", "stable", "insufficient_data"]
    source_coverage: tuple[str, ...]
    evidence_count: int
    valid_evidence_count: int
    evidence_ids: tuple[str, ...]
    gap_reason: str | None
    review_prerequisite_met: bool


class ReadinessEligibility(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: bool
    required_activities_complete: bool
    competencies_sufficient: bool
    no_blocking_tasks: bool
    no_unresolved_quality_conflicts: bool
    missing_activity_ids: tuple[str, ...]
    competency_gaps: tuple[str, ...]
    quality_conflict_evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...]


class ReadinessPolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set_hash: str
    competencies: tuple[CompetencyReadinessProjection, ...]
    eligibility: ReadinessEligibility
    risk_band: Literal["low", "medium", "high"]
    risk_reasons: tuple[str, ...]


class AISummaryFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=2_000)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=100)


class AISummaryDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    facts: tuple[AISummaryFact, ...]
    calculations: tuple[str, ...] = Field(max_length=100)
    inferences: tuple[str, ...] = Field(max_length=100)
    recommendations: tuple[str, ...] = Field(max_length=100)
    limitations: tuple[str, ...] = Field(max_length=100)


class ReviewDecisionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_type: Literal[
        "approve_foundation_ready",
        "request_retraining",
        "request_more_evidence",
        "reject_due_to_integrity_issue",
        "close_without_decision",
        "exception_approved",
    ]
    expected_dossier_version: int = Field(ge=1)
    snapshot_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2_000)
    notes: str | None = Field(default=None, max_length=10_000)
    competency_keys: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    exception_confirmed: bool = False
    preview_token: str | None = Field(default=None, min_length=1, max_length=200)
    impact_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ExceptionDecisionPreviewInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    expected_dossier_version: int = Field(ge=1)
    snapshot_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2_000)
    notes: str | None = Field(default=None, max_length=10_000)
    competency_keys: tuple[str, ...] = Field(min_length=1, max_length=50)
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=200)


class RetrainingAssignmentInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    expected_dossier_version: int = Field(ge=1)
    snapshot_id: str = Field(min_length=1, max_length=160)
    activity_source: Literal["existing_published", "quick_draft"]
    activity_id: str | None = Field(default=None, max_length=160)
    activity_title: str = Field(min_length=1, max_length=200)
    activity_draft: dict[str, Any] | None = None
    target_competency_keys: tuple[str, ...] = Field(min_length=1, max_length=50)
    source_evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=200)
    reason: str = Field(min_length=1, max_length=2_000)
    due_at: datetime | None = None
    completion_rule: dict[str, Any] = Field(default_factory=dict)


class AppealInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: Literal["evidence", "decision", "transcript", "score"]
    target_id: str = Field(min_length=1, max_length=160)
    dossier_version: int = Field(ge=1)
    reason_category: Literal[
        "audio_quality", "transcript_error", "score_error", "fact_error"
    ]
    statement: str = Field(min_length=1, max_length=10_000)


class AppealResolutionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    expected_version: int = Field(ge=1)
    action: Literal[
        "begin_review", "request_regrade", "resolve", "reject", "reopen_review"
    ]
    resolution: str = Field(min_length=1, max_length=10_000)


class CalibrationSessionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    competency_key: str = Field(min_length=1, max_length=80)
    sample_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=200)
    action_items: tuple[str, ...] = Field(default_factory=tuple, max_length=100)


__all__ = [
    "AISummaryDraft",
    "AppealInput",
    "AppealResolutionInput",
    "CalibrationSessionInput",
    "CompetencyReadinessProjection",
    "ExceptionDecisionPreviewInput",
    "ReadinessActivityInput",
    "ReadinessActor",
    "ReadinessEligibility",
    "ReadinessPolicyResult",
    "ReadinessProjectionInput",
    "RetrainingAssignmentInput",
    "ReviewDecisionInput",
]
