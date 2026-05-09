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
