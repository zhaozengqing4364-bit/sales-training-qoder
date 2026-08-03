"""SQLAlchemy persistence owned exclusively by audio_assessment."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
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
)
from sqlalchemy.orm import Mapped, mapped_column

from common.db.model_registry import Base
from common.db.model_registry.base import jsonb_compatible_type


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class AudioActivityResourceRevision(Base):
    """Published immutable material/scorecard/scenario revision used by a run."""

    __tablename__ = "audio_activity_resource_revisions"

    revision_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="working")
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('audio_material','scoring_scheme','scenario')",
            name="ck_audio_resource_revision_type",
        ),
        CheckConstraint(
            "status IN ('working','published','archived')",
            name="ck_audio_resource_revision_status",
        ),
        UniqueConstraint(
            "organization_id",
            "resource_type",
            "stable_key",
            "revision_no",
            name="uq_audio_resource_revision_number",
        ),
    )


class AudioActivityRun(Base):
    __tablename__ = "audio_activity_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    enrollment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_enrollments_v2.enrollment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    path_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_activity_attempts_v2.attempt_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    config_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    competency_keys_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('audio_assessment','assignment')",
            name="ck_audio_activity_run_type",
        ),
        CheckConstraint(
            "status IN ('draft','in_progress','processing','needs_review',"
            "'completed','failed','cancelled','invalidated')",
            name="ck_audio_activity_run_status",
        ),
        Index(
            "ix_audio_activity_runs_scope",
            "organization_id",
            "learner_id",
            "activity_id",
        ),
    )


class AudioSubmission(Base):
    __tablename__ = "audio_submissions_v2"

    submission_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_activity_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    task_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("durable_tasks.task_id", ondelete="SET NULL"),
        nullable=True,
    )
    original_artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    normalized_artifact_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    current_transcript_revision_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    current_score_outcome_version_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    failed_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_classification: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "run_id", "segment_id", name="uq_audio_submission_run_segment"
        ),
        CheckConstraint(
            "state IN ('draft','uploading','uploaded','validating','normalizing',"
            "'transcribing','transcript_ready','scoring','reconciling','completed',"
            "'partially_completed','failed_recoverable','failed_terminal',"
            "'needs_review','cancelled','invalidated','expired')",
            name="ck_audio_submission_v2_state",
        ),
        Index("ix_audio_submissions_v2_run_state", "run_id", "state"),
    )


class AudioUploadSession(Base):
    __tablename__ = "audio_upload_sessions"

    upload_session_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_submissions_v2.submission_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="uploading")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    declared_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_duration_seconds: Mapped[float] = mapped_column(
        Numeric(10, 3), nullable=False
    )
    declared_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    part_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_part_count: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(24), nullable=False)
    object_prefix: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleanup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleanup_claim_token: Mapped[str | None] = mapped_column(String(36))
    cleanup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cleanup_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint(
            "state IN ('uploading','finalized','cancelled','expired')",
            name="ck_audio_upload_session_state",
        ),
        UniqueConstraint(
            "submission_id",
            "idempotency_key_hash",
            name="uq_audio_upload_session_command",
        ),
        Index(
            "ix_audio_upload_sessions_cleanup",
            "state",
            "cleanup_completed_at",
            "expires_at",
        ),
    )


class AudioUploadPart(Base):
    __tablename__ = "audio_upload_parts"

    part_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    upload_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_upload_sessions.upload_session_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    part_number: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    declared_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "upload_session_id", "part_number", name="uq_audio_upload_part_number"
        ),
        CheckConstraint(
            "part_number >= 1", name="ck_audio_upload_part_number_positive"
        ),
    )


class AudioArtifact(Base):
    __tablename__ = "audio_artifacts"

    artifact_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_submissions_v2.submission_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    artifact_ref: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    storage_backend: Mapped[str] = mapped_column(String(24), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    sample_rate_hz: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('original','normalized')", name="ck_audio_artifact_kind"
        ),
        UniqueConstraint(
            "submission_id", "kind", name="uq_audio_artifact_submission_kind"
        ),
    )


class AudioTranscriptRevision(Base):
    __tablename__ = "audio_transcript_revisions"

    revision_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_submissions_v2.submission_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_artifacts.artifact_id", ondelete="RESTRICT"),
        nullable=False,
    )
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    segments_json: Mapped[list[dict[str, Any]]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    confidence: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_summary_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=dict
    )
    ai_invocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="valid")
    supersedes_revision_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "submission_id", "revision_no", name="uq_audio_transcript_revision_number"
        ),
        CheckConstraint(
            "source IN ('automatic','manual_correction','retranscription','legacy_conversion')",
            name="ck_audio_transcript_revision_source",
        ),
        CheckConstraint(
            "status IN ('valid','invalidated')",
            name="ck_audio_transcript_revision_status",
        ),
    )


class AudioQualityReport(Base):
    __tablename__ = "audio_quality_reports"

    report_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_submissions_v2.submission_id", ondelete="RESTRICT"),
        nullable=False,
    )
    transcript_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_transcript_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    metrics_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    quality_flags_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    scorable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class AudioScoreOutcomeVersion(Base):
    __tablename__ = "audio_score_outcome_versions"

    outcome_version_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_submissions_v2.submission_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_transcript_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    scoring_scheme_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_contract_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    ai_invocation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    dimension_scores_json: Mapped[list[dict[str, Any]]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    evidence_spans_json: Mapped[list[dict[str, Any]]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    missing_points_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    feedback_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    remediation_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    critical_flags_json: Mapped[list[str]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=list
    )
    deterministic_metrics_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=dict
    )
    total_score: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="valid")
    supersedes_outcome_version_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    review_trace_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False, default=dict
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "submission_id", "version_no", name="uq_audio_score_outcome_version_number"
        ),
        CheckConstraint(
            "status IN ('valid','invalidated')",
            name="ck_audio_score_outcome_version_status",
        ),
    )


class AudioCommandAudit(Base):
    __tablename__ = "audio_command_audits"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
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
        jsonb_compatible_type(), nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class AudioChangePreview(Base):
    __tablename__ = "audio_change_previews"

    preview_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    submission_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_submissions_v2.submission_id", ondelete="RESTRICT"),
        nullable=False,
    )
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    preview_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    impact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_json: Mapped[dict[str, Any]] = mapped_column(
        jsonb_compatible_type(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('transcript_correction','regrade','invalidation')",
            name="ck_audio_change_preview_type",
        ),
    )


__all__ = [
    "AudioActivityResourceRevision",
    "AudioActivityRun",
    "AudioArtifact",
    "AudioChangePreview",
    "AudioCommandAudit",
    "AudioQualityReport",
    "AudioScoreOutcomeVersion",
    "AudioSubmission",
    "AudioTranscriptRevision",
    "AudioUploadPart",
    "AudioUploadSession",
]
