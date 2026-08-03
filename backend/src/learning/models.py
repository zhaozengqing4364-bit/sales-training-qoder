"""SQLAlchemy persistence for learning source, revision, and question governance."""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.db.model_registry import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class LearningSourceDocument(Base):
    __tablename__ = "learning_source_documents"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    working_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "stable_key", name="uq_learning_source_document_key"),
        CheckConstraint("status IN ('draft','active','archived')", name="ck_learning_source_document_status"),
    )


class LearningSourceDocumentRevision(Base):
    __tablename__ = "learning_source_document_revisions"

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_source_documents.document_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="working")
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    content_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="document"
    )
    source_uri: Mapped[str] = mapped_column(String(1_000), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(120), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(24), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    trusted_mime_type: Mapped[str | None] = mapped_column(String(160))
    file_extension: Mapped[str | None] = mapped_column(String(16))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(32))
    page_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    preview_version: Mapped[str | None] = mapped_column(String(120))
    processing_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending"
    )
    processing_stage: Mapped[str | None] = mapped_column(String(120))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    manual_content: Mapped[str | None] = mapped_column(Text)
    preview_manifest_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT,
        nullable=False,
        default=dict,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    save_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    save_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    publish_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    publish_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("document_id", "revision_no", name="uq_learning_source_revision_number"),
        CheckConstraint("status IN ('working','published','archived')", name="ck_learning_source_revision_status"),
        CheckConstraint("parse_status IN ('pending','ready','failed')", name="ck_learning_source_revision_parse_status"),
        CheckConstraint(
            "content_kind IN ('document','slide_deck','demo_video','external_demo','script','example_audio','attachment')",
            name="ck_learning_source_revision_content_kind",
        ),
        CheckConstraint(
            "processing_state IN ('pending','processing','partial','ready','failed','cancelled')",
            name="ck_learning_source_revision_processing_state",
        ),
    )


class LearningSourceAnchor(Base):
    __tablename__ = "learning_source_anchors"

    anchor_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_revision_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_source_document_revisions.revision_id", ondelete="RESTRICT"), nullable=False)
    anchor_key: Mapped[str] = mapped_column(String(160), nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    locator_type: Mapped[str] = mapped_column(String(24), nullable=False)
    locator_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    excerpt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_revision_id", "anchor_key", name="uq_learning_source_anchor_key"),
    )


class LearningUnit(Base):
    __tablename__ = "learning_units_v2"

    unit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    working_revision_id: Mapped[str | None] = mapped_column(String(36))
    published_revision_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "stable_key", name="uq_learning_unit_key_v2"),
        CheckConstraint("status IN ('draft','active','archived')", name="ck_learning_unit_status_v2"),
    )


class LearningUnitRevision(Base):
    __tablename__ = "learning_unit_revisions"

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    unit_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_units_v2.unit_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="working")
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    source_anchor_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    save_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    save_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    publish_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    publish_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("unit_id", "revision_no", name="uq_learning_unit_revision_number"),
        CheckConstraint("status IN ('working','published','archived')", name="ck_learning_unit_revision_status"),
    )


class LearningQuestionGenerationBatch(Base):
    __tablename__ = "learning_question_generation_batches"

    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_revision_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_source_document_revisions.revision_id", ondelete="RESTRICT"), nullable=False)
    learning_unit_revision_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_unit_revisions.revision_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), index=True)
    prompt_template_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_contract_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    model_routing_profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    input_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    generation_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    invocation_id: Mapped[str | None] = mapped_column(String(160))
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(120))
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key_hash", name="uq_learning_question_batch_idempotency"),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_learning_question_batch_status"),
    )


class LearningQuestionCandidate(Base):
    __tablename__ = "learning_question_candidates"

    candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_question_generation_batches.batch_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="generated")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    source_anchor_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    competency_keys_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    deterministic_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    gate_status: Mapped[str] = mapped_column(String(24), nullable=False)
    gate_results_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    prompt_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_routing_revision_id: Mapped[str] = mapped_column(String(160), nullable=False)
    generation_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    invocation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    review_reason: Mapped[str | None] = mapped_column(Text)
    review_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    review_fingerprint: Mapped[str | None] = mapped_column(String(64))
    approved_question_revision_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('generated','in_review','approved','rejected','superseded')", name="ck_learning_question_candidate_status"),
        CheckConstraint("gate_status IN ('passed','failed')", name="ck_learning_question_candidate_gate_status"),
        Index("ix_learning_question_candidate_queue", "organization_id", "status", "created_at"),
    )


class LearningQuestionCandidateBulkReview(Base):
    __tablename__ = "learning_question_candidate_bulk_reviews"

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    command: Mapped[str] = mapped_column(String(32), nullable=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="previewed"
    )
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
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    confirm_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    confirm_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "command IN ('approve','reject','supersede')",
            name="ck_learning_candidate_bulk_review_command",
        ),
        CheckConstraint(
            "status IN ('previewed','succeeded','partial','failed','expired')",
            name="ck_learning_candidate_bulk_review_status",
        ),
        Index(
            "ix_learning_candidate_bulk_review_org_created",
            "organization_id",
            "created_at",
        ),
    )


class LearningQuestion(Base):
    __tablename__ = "learning_questions"

    question_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    working_revision_id: Mapped[str | None] = mapped_column(String(36))
    published_revision_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "stable_key", name="uq_learning_question_key"),
        CheckConstraint("status IN ('draft','in_review','approved','published','archived','rejected')", name="ck_learning_question_status"),
    )


class LearningQuestionRevision(Base):
    __tablename__ = "learning_question_revisions"

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_questions.question_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    source_anchor_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    competency_keys_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    deterministic_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_candidate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("learning_question_candidates.candidate_id", ondelete="RESTRICT"))
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    review_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("question_id", "revision_no", name="uq_learning_question_revision_number"),
        CheckConstraint("status IN ('draft','in_review','approved','published','archived','rejected')", name="ck_learning_question_revision_status"),
    )


class LearningCommandAudit(Base):
    __tablename__ = "learning_command_audits"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    command: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    before_version: Mapped[int | None] = mapped_column(Integer)
    after_version: Mapped[int | None] = mapped_column(Integer)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(160))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class LearningLessonAttempt(Base):
    __tablename__ = "learning_lesson_attempts"

    detail_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    learner_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    path_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    learning_unit_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("learning_unit_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_progress")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_checkpoint_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    completed_checkpoint_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    reading_position_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    relearn_of_detail_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("learning_lesson_attempts.detail_id", ondelete="RESTRICT"))
    start_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    start_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    invalidation_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    last_saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('in_progress','completed','invalidated')", name="ck_learning_lesson_attempt_status"),
        Index("ix_learning_lesson_enrollment_activity", "enrollment_id", "activity_id", "started_at"),
    )


class LearningLessonCommand(Base):
    __tablename__ = "learning_lesson_commands"

    command_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    detail_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_lesson_attempts.detail_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False)
    command_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("detail_id", "command_type", "idempotency_key_hash", name="uq_learning_lesson_command_idempotency"),
    )


class LearningQuiz(Base):
    __tablename__ = "learning_quizzes"

    quiz_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    working_revision_id: Mapped[str | None] = mapped_column(String(36))
    published_revision_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creation_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    creation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "stable_key", name="uq_learning_quiz_key"),
        CheckConstraint("status IN ('draft','active','archived')", name="ck_learning_quiz_status"),
    )


class LearningQuizRevision(Base):
    __tablename__ = "learning_quiz_revisions"

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    quiz_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_quizzes.quiz_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="working")
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    question_revision_ids_json: Mapped[list[str]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    save_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    save_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    publish_idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    publish_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("quiz_id", "revision_no", name="uq_learning_quiz_revision_number"),
        CheckConstraint("status IN ('working','published','archived')", name="ck_learning_quiz_revision_status"),
    )


class LearningQuizAttempt(Base):
    __tablename__ = "learning_quiz_attempts"

    detail_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    learner_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    path_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    quiz_revision_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_quiz_revisions.revision_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    question_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False)
    rule_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    answers_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    objective_score: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    score: Mapped[float | None] = mapped_column(Numeric(10, 4))
    max_score: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    task_id: Mapped[str | None] = mapped_column(String(36), index=True)
    scoring_invocation_id: Mapped[str | None] = mapped_column(String(160))
    scoring_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    scoring_error_code: Mapped[str | None] = mapped_column(String(120))
    start_idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    start_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    last_saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('in_progress','scoring_pending','needs_review','scored','invalidated','cancelled')", name="ck_learning_quiz_attempt_status"),
        Index("ix_learning_quiz_enrollment_activity", "enrollment_id", "activity_id", "started_at"),
    )


class LearningQuizCommand(Base):
    __tablename__ = "learning_quiz_commands"

    command_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    detail_id: Mapped[str] = mapped_column(String(36), ForeignKey("learning_quiz_attempts.detail_id", ondelete="RESTRICT"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False)
    command_type: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("detail_id", "command_type", "idempotency_key_hash", name="uq_learning_quiz_command_idempotency"),
    )


__all__ = [
    "LearningCommandAudit",
    "LearningQuestion",
    "LearningQuestionCandidate",
    "LearningQuestionGenerationBatch",
    "LearningQuestionRevision",
    "LearningLessonAttempt",
    "LearningLessonCommand",
    "LearningSourceAnchor",
    "LearningSourceDocument",
    "LearningSourceDocumentRevision",
    "LearningUnit",
    "LearningUnitRevision",
    "LearningQuiz",
    "LearningQuizAttempt",
    "LearningQuizCommand",
    "LearningQuizRevision",
]
