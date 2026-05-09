"""Schemas for supervisor review and retraining task APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SupervisorDecision = Literal["pending", "approved", "rejected", "needs_retraining"]
ReadinessStatus = Literal[
    "not_ready",
    "shadow_only",
    "ready_for_trial",
    "approved",
]
RetrainingTaskStatus = Literal["todo", "in_progress", "completed", "cancelled"]
CalibrationLabel = Literal[
    "accurate",
    "too_high",
    "too_low",
    "wrong_reason",
    "missing_evidence",
]


class TrainingReportTrainee(BaseModel):
    user_id: str
    name: str | None = None
    email: str | None = None


class TrainingReportEvidenceItem(BaseModel):
    evidence_id: str
    dimension: str | None = None
    issue: str | None = None
    evidence_type: str
    turn_number: int | None = None
    speaker: str | None = None
    quote: str | None = None
    source_message_id: str | None = None
    source_page_id: str | None = None
    knowledge_source_id: str | None = None
    reason: str | None = None
    severity: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class TrainingReportDimensionScore(BaseModel):
    name: str
    score: float | None = Field(default=None, ge=0, le=100)
    description: str | None = None
    evidence_item_ids: list[str] = Field(default_factory=list)


class TrainingReportIssue(BaseModel):
    issue: str
    dimension: str | None = None
    reason: str | None = None
    severity: str | None = None
    evidence_item_ids: list[str] = Field(default_factory=list)


class TrainingReportRiskFlag(BaseModel):
    code: str
    message: str
    evidence_item_ids: list[str] = Field(default_factory=list)


class TrainingReportNextAction(BaseModel):
    action_type: str
    label: str
    target: str | None = None


class SupervisorScoreCalibrationUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., max_length=36)
    dimension: str = Field(..., min_length=1, max_length=120)
    ai_score: float | None = Field(default=None, ge=0, le=100)
    supervisor_score: float | None = Field(default=None, ge=0, le=100)
    calibration_label: CalibrationLabel
    comment: str | None = Field(default=None, max_length=1000)


class SupervisorScoreCalibrationResponse(BaseModel):
    review_id: str
    session_id: str
    dimension: str
    ai_score: float | None = None
    supervisor_score: float | None = None
    calibration_label: CalibrationLabel
    comment: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScoreDimensionDelta(BaseModel):
    name: str
    original_score: float | None = None
    retraining_score: float | None = None
    delta: float | None = None


class BeforeAfterComparison(BaseModel):
    source_session_id: str
    completed_session_id: str | None = None
    original_score: float | None = None
    retraining_score: float | None = None
    score_delta: float | None = None
    weak_dimension_changes: list[ScoreDimensionDelta] = Field(default_factory=list)
    retraining_completed: bool = False


class RetrainingTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = Field(default=None, max_length=36)
    source_session_id: str = Field(..., max_length=36)
    source_review_id: str = Field(..., max_length=36)
    skill_dimension: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class RetrainingTaskCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_session_id: str = Field(..., max_length=36)


class RetrainingTaskResponse(BaseModel):
    task_id: str
    user_id: str
    source_session_id: str
    source_review_id: str
    skill_dimension: str
    title: str
    description: str | None = None
    status: RetrainingTaskStatus
    completed_session_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    before_after: BeforeAfterComparison | None = None


class RetrainingTaskStartResponse(BaseModel):
    task: RetrainingTaskResponse
    session_id: str


class SupervisorReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., max_length=36)
    decision: SupervisorDecision = "pending"
    readiness_status: ReadinessStatus = "not_ready"
    comment: str | None = None
    required_retraining: bool = False
    skill_dimension: str | None = Field(default=None, max_length=120)
    audit_metadata: dict[str, Any] | None = None


class SupervisorReviewDecisionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: SupervisorDecision
    readiness_status: ReadinessStatus | None = None
    comment: str | None = None
    required_retraining: bool | None = None
    skill_dimension: str | None = Field(default=None, max_length=120)
    audit_metadata: dict[str, Any] | None = None


class SupervisorReviewResponse(BaseModel):
    review_id: str
    session_id: str
    trainee_user_id: str
    supervisor_user_id: str
    decision: SupervisorDecision
    readiness_status: ReadinessStatus
    comment: str | None = None
    required_retraining: bool
    audit_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    retraining_tasks: list[RetrainingTaskResponse] = Field(default_factory=list)
    before_after: BeforeAfterComparison | None = None
    calibrations: list[SupervisorScoreCalibrationResponse] = Field(default_factory=list)


class SupervisorTeamReport(BaseModel):
    session_id: str
    trainee_user_id: str
    trainee_name: str | None = None
    scenario_type: str
    status: str
    report_status: str | None = None
    overall_score: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latest_review: SupervisorReviewResponse | None = None
    before_after: BeforeAfterComparison | None = None


class TrainingReportViewModel(BaseModel):
    session_id: str
    scenario_type: str
    trainee: TrainingReportTrainee
    overall_score: float | None = None
    readiness_suggestion: str
    dimension_scores: list[TrainingReportDimensionScore] = Field(default_factory=list)
    key_strengths: list[str] = Field(default_factory=list)
    key_issues: list[TrainingReportIssue] = Field(default_factory=list)
    evidence_items: list[TrainingReportEvidenceItem] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    risk_flags: list[TrainingReportRiskFlag] = Field(default_factory=list)
    next_actions: list[TrainingReportNextAction] = Field(default_factory=list)
    supervisor_review: SupervisorReviewResponse | None = None
    retraining_tasks: list[RetrainingTaskResponse] = Field(default_factory=list)
    before_after: BeforeAfterComparison | None = None
