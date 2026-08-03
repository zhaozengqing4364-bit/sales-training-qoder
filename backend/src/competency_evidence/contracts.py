"""Stable contracts at the competency-evidence module boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OutcomeEvidenceInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str = Field(min_length=1, max_length=120)
    learner_id: str = Field(min_length=1, max_length=120)
    enrollment_id: str = Field(min_length=1, max_length=160)
    path_revision_id: str = Field(min_length=1, max_length=160)
    activity_id: str = Field(min_length=1, max_length=160)
    activity_type: Literal[
        "lesson", "quiz", "audio_assessment", "ai_coach", "assignment"
    ]
    competency_keys: tuple[str, ...] = Field(min_length=1, max_length=50)
    attempt_id: str = Field(min_length=1, max_length=160)
    outcome_id: str = Field(min_length=1, max_length=160)
    outcome_version: int = Field(ge=1)
    supersedes_outcome_id: str | None = Field(default=None, max_length=160)
    lifecycle_result: Literal["completed", "failed", "invalidated", "cancelled"]
    assessment_result: Literal[
        "passed", "not_passed", "not_applicable", "needs_review"
    ] | None = None
    score: float | None = None
    max_score: float | None = None
    passed: bool | None = None
    source_refs: tuple[dict[str, str], ...] = ()
    lineage: dict[str, Any]
    confidence: float | None = Field(default=None, ge=0, le=1)
    critical_flags: tuple[str, ...] = ()
    degradations: tuple[str, ...] = ()
    produced_at: datetime
    actor_id: str = Field(min_length=1, max_length=120)
    trace_id: str | None = Field(default=None, max_length=160)


class CompetencyEvidenceProjection(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    evidence_id: str
    organization_id: str
    learner_id: str
    enrollment_id: str
    competency_revision_id: str
    competency_key: str
    competency_title: str
    source_activity_id: str
    attempt_id: str
    outcome_id: str
    outcome_version: int
    evidence_type: str
    evidence_role: str
    observed_score: float | None
    observed_max_score: float | None
    observed_result: str | None
    confidence: float | None
    quality: str
    validity: str
    source_refs: tuple[dict[str, str], ...]
    lineage: dict[str, Any]
    critical_flags: tuple[str, ...]
    degradations: tuple[str, ...]
    supersedes_evidence_id: str | None
    observed_at: datetime


__all__ = ["CompetencyEvidenceProjection", "OutcomeEvidenceInput"]
