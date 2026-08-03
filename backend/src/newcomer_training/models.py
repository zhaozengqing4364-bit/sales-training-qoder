"""SQLAlchemy persistence owned by the newcomer-training domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.db.model_registry import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class NewcomerPath(Base):
    __tablename__ = "newcomer_paths"

    path_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    working_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_release_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "newcomer_release_plans.release_plan_id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_newcomer_paths_active_release_plan",
        ),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "stable_key", name="uq_newcomer_paths_org_key"
        ),
        CheckConstraint(
            "status IN ('draft','active','archived')",
            name="ck_newcomer_paths_status",
        ),
    )


class NewcomerPathRevision(Base):
    __tablename__ = "newcomer_path_revisions"

    revision_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    path_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("newcomer_paths.path_id", ondelete="RESTRICT"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="working")
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    save_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    save_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    publish_idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    publish_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "path_id", "revision_no", name="uq_newcomer_path_revision_number"
        ),
        CheckConstraint(
            "status IN ('working','published','archived')",
            name="ck_newcomer_path_revisions_status",
        ),
        Index(
            "ix_newcomer_path_revisions_path_status", "path_id", "status"
        ),
    )


class NewcomerCohort(Base):
    __tablename__ = "newcomer_cohorts"

    cohort_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_path_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "stable_key", name="uq_newcomer_cohorts_org_key"
        ),
        CheckConstraint(
            "status IN ('active','paused','cancelled','closed','archived')",
            name="ck_newcomer_cohorts_status",
        ),
    )


class NewcomerEnrollment(Base):
    __tablename__ = "newcomer_enrollments_v2"

    enrollment_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    cohort_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("newcomer_cohorts.cohort_id", ondelete="RESTRICT"), nullable=False
    )
    path_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_path_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(120), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "cohort_id",
            "learner_id",
            name="uq_newcomer_enrollment_cohort_learner",
        ),
        CheckConstraint(
            "status IN ('active','completed','cancelled')",
            name="ck_newcomer_enrollments_v2_status",
        ),
        Index(
            "uq_newcomer_enrollments_v2_active_learner",
            "organization_id",
            "learner_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )


class NewcomerEnrollmentMigration(Base):
    __tablename__ = "newcomer_enrollment_migrations"

    migration_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_path_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="previewed")
    preview_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    impact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    confirm_idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    confirm_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('previewed','succeeded','partial','failed','expired')",
            name="ck_newcomer_enrollment_migrations_status",
        ),
    )


class NewcomerEnrollmentImport(Base):
    """Persisted preview/confirm batch for assigning learners to one cohort."""

    __tablename__ = "newcomer_enrollment_imports"

    import_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    cohort_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_cohorts.cohort_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="previewed"
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    impact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_DOCUMENT, nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirm_idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    confirm_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('previewed','succeeded','partial','failed','expired')",
            name="ck_newcomer_enrollment_imports_status",
        ),
        Index(
            "ix_newcomer_enrollment_imports_cohort_created",
            "cohort_id",
            "created_at",
        ),
    )


class NewcomerReleasePlan(Base):
    """Auditable atomic publication plan for one exact path revision graph."""

    __tablename__ = "newcomer_release_plans"

    release_plan_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    path_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_paths.path_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    path_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_path_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    previous_release_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("newcomer_release_plans.release_plan_id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_revisions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    dependency_graph_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    validation_report_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    impact_preview_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    impact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    preview_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    publish_idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    publish_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    rollback_preview_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    rollback_impact_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    rollback_preview_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_DOCUMENT, nullable=True
    )
    rollback_preview_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rollback_confirm_idempotency_key_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    rollback_confirm_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rolled_back_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','validating','ready','blocked','publishing',"
            "'published','superseded','failed','cancelled')",
            name="ck_newcomer_release_plans_status",
        ),
        Index(
            "ix_newcomer_release_plans_path_created",
            "path_id",
            "created_at",
        ),
        Index(
            "ix_newcomer_release_plans_org_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
    )


class NewcomerCommandAudit(Base):
    __tablename__ = "newcomer_command_audits"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    command: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    before_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    impact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class NewcomerActivityAttempt(Base):
    __tablename__ = "newcomer_activity_attempts_v2"

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_enrollments_v2.enrollment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    path_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="started")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    activity_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    outcome_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    reconcile_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "enrollment_id",
            "activity_id",
            "attempt_no",
            name="uq_newcomer_activity_attempt_number_v2",
        ),
        UniqueConstraint(
            "organization_id",
            "enrollment_id",
            "activity_id",
            "idempotency_key_hash",
            name="uq_newcomer_activity_attempt_command_v2",
        ),
        CheckConstraint(
            "status IN ('started','in_progress','submitted','processing','completed',"
            "'failed','invalidated','cancelled')",
            name="ck_newcomer_activity_attempts_v2_status",
        ),
    )


class NewcomerActivityOutcome(Base):
    __tablename__ = "newcomer_activity_outcomes"

    outcome_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_activity_attempts_v2.attempt_id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    result_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    lifecycle_result: Mapped[str] = mapped_column(String(32), nullable=False)
    assessment_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    competency_evidence_refs_json: Mapped[list[dict[str, str]]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    source_refs_json: Mapped[list[dict[str, str]]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    lineage_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    critical_flags_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    degradations_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    next_action_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_DOCUMENT, nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_outcome_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("newcomer_activity_outcomes.outcome_id", ondelete="RESTRICT"),
        nullable=True,
    )
    produced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "version",
            name="uq_newcomer_activity_outcome_version",
        ),
        UniqueConstraint(
            "organization_id",
            "attempt_id",
            "idempotency_key_hash",
            name="uq_newcomer_activity_outcome_command",
        ),
        Index(
            "ix_newcomer_activity_outcome_attempt_produced",
            "attempt_id",
            "produced_at",
        ),
    )


NEWCOMER_TRAINING_TABLES = Base.metadata


__all__ = [
    "NewcomerActivityAttempt",
    "NewcomerActivityOutcome",
    "NewcomerCohort",
    "NewcomerCommandAudit",
    "NewcomerEnrollment",
    "NewcomerEnrollmentImport",
    "NewcomerEnrollmentMigration",
    "NewcomerPath",
    "NewcomerPathRevision",
    "NewcomerReleasePlan",
]
