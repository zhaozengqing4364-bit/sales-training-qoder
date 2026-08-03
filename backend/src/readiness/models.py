"""SQLAlchemy persistence owned only by the readiness module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.db.model_registry import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ReadinessPolicyRevision(Base):
    __tablename__ = "readiness_policy_revisions"

    policy_revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stable_key: Mapped[str] = mapped_column(String(120), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "stable_key", "revision_no", name="uq_readiness_policy_revision"
        ),
        CheckConstraint(
            "status IN ('published','archived')",
            name="ck_readiness_policy_status",
        ),
    )


class ReadinessDossier(Base):
    __tablename__ = "readiness_dossiers"

    dossier_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    learner_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    path_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="projecting")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence_set_hash: Mapped[str | None] = mapped_column(String(64))
    pending_evidence_set_hash: Mapped[str | None] = mapped_column(String(64))
    current_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    active_decision_id: Mapped[str | None] = mapped_column(String(36))
    stale_reason: Mapped[str | None] = mapped_column(Text)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "enrollment_id", name="uq_readiness_dossier_enrollment"
        ),
        CheckConstraint(
            "state IN ('projecting','incomplete','ready_for_review','under_review',"
            "'decided','stale','projection_failed')",
            name="ck_readiness_dossier_state",
        ),
        Index(
            "ix_readiness_dossier_queue",
            "organization_id",
            "state",
            "updated_at",
        ),
    )


class ReadinessDossierSnapshot(Base):
    __tablename__ = "readiness_dossier_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("readiness_dossiers.dossier_id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    competency_revision_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    readiness_policy_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("readiness_policy_revisions.policy_revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    path_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    projection_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    ai_summary_revision_id: Mapped[str | None] = mapped_column(String(36))
    stale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "dossier_id", "snapshot_version", name="uq_dossier_snapshot_version"
        ),
        Index(
            "ix_dossier_snapshot_current",
            "organization_id",
            "dossier_id",
            "created_at",
        ),
    )


class ReadinessReviewDecision(Base):
    __tablename__ = "readiness_review_decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("readiness_dossiers.dossier_id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("readiness_dossier_snapshots.snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    dossier_version: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="recorded")
    reviewer_id: Mapped[str] = mapped_column(String(120), nullable=False)
    competency_keys_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    supersedes_decision_id: Mapped[str | None] = mapped_column(String(36))
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dossier_id",
            "idempotency_key_hash",
            name="uq_readiness_decision_command",
        ),
        CheckConstraint(
            "status IN ('recorded','superseded','voided')",
            name="ck_readiness_decision_status",
        ),
        CheckConstraint(
            "decision_type IN ('approve_foundation_ready','request_retraining',"
            "'request_more_evidence','reject_due_to_integrity_issue',"
            "'close_without_decision','exception_approved')",
            name="ck_readiness_decision_type",
        ),
    )


class ReadinessExceptionPreview(Base):
    __tablename__ = "readiness_exception_previews"

    preview_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("readiness_dossiers.dossier_id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("readiness_dossier_snapshots.snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    dossier_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(120), nullable=False)
    impact_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    impact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="previewed")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dossier_id",
            "idempotency_key_hash",
            name="uq_readiness_exception_preview_command",
        ),
        CheckConstraint(
            "status IN ('previewed','consumed','expired')",
            name="ck_readiness_exception_preview_status",
        ),
        Index(
            "ix_readiness_exception_preview_active",
            "organization_id",
            "dossier_id",
            "status",
            "expires_at",
        ),
    )


class ReadinessRetrainingAssignment(Base):
    __tablename__ = "readiness_retraining_assignments"

    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    enrollment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    learner_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_source: Mapped[str] = mapped_column(String(32), nullable=False)
    activity_id: Mapped[str | None] = mapped_column(String(160))
    activity_title: Mapped[str] = mapped_column(String(200), nullable=False)
    activity_draft_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    target_competency_keys_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    source_evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_rule_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_outcome_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "dossier_id",
            "idempotency_key_hash",
            name="uq_retraining_assignment_command",
        ),
        CheckConstraint(
            "activity_source IN ('existing_published','quick_draft')",
            name="ck_retraining_activity_source",
        ),
        CheckConstraint(
            "status IN ('assigned','draft_pending_governance','completed','cancelled')",
            name="ck_retraining_assignment_status",
        ),
    )


class ReadinessAppeal(Base):
    __tablename__ = "readiness_appeals"

    appeal_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    learner_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target_id: Mapped[str] = mapped_column(String(160), nullable=False)
    dossier_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_category: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    assigned_to: Mapped[str | None] = mapped_column(String(120))
    resolution: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "learner_id",
            "idempotency_key_hash",
            name="uq_readiness_appeal_command",
        ),
        CheckConstraint(
            "target_type IN ('evidence','decision','transcript','score')",
            name="ck_readiness_appeal_target",
        ),
        CheckConstraint(
            "status IN ('submitted','under_review','regrade_pending','resolved','rejected')",
            name="ck_readiness_appeal_status",
        ),
    )


class ReadinessCalibrationSession(Base):
    __tablename__ = "readiness_calibration_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    competency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    sample_evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    decision_distribution_json: Mapped[dict[str, int]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    disagreements_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    action_items_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','closed')", name="ck_readiness_calibration_status"
        ),
    )


class ReadinessAISummary(Base):
    __tablename__ = "readiness_ai_summaries"

    summary_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dossier_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    evidence_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    error_code: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "revision_no", name="uq_readiness_ai_summary_revision"
        ),
        CheckConstraint(
            "status IN ('ready','rejected','failed')",
            name="ck_readiness_ai_summary_status",
        ),
    )


class ReadinessCommandAudit(Base):
    __tablename__ = "readiness_command_audits"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    command: Mapped[str] = mapped_column(String(120), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    before_version: Mapped[int | None] = mapped_column(Integer)
    after_version: Mapped[int | None] = mapped_column(Integer)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    trace_id: Mapped[str | None] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


__all__ = [
    "ReadinessAISummary",
    "ReadinessAppeal",
    "ReadinessCalibrationSession",
    "ReadinessCommandAudit",
    "ReadinessDossier",
    "ReadinessDossierSnapshot",
    "ReadinessExceptionPreview",
    "ReadinessPolicyRevision",
    "ReadinessRetrainingAssignment",
    "ReadinessReviewDecision",
]
