from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from common.db.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SalesTrainerUnit(Base):
    __tablename__ = "sales_trainer_units"

    unit_id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    unit_type = Column(String(30), nullable=False, index=True)
    config = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="draft", index=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "unit_type IN ('quiz', 'audio_scoring')",
            name="ck_sales_trainer_unit_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_sales_trainer_unit_status",
        ),
        Index("idx_sales_trainer_units_status_updated", "status", "updated_at"),
    )


class SalesTrainerUnitQuestion(Base):
    __tablename__ = "sales_trainer_unit_questions"

    id = Column(String(36), primary_key=True, default=_uuid)
    unit_id = Column(
        String(36),
        ForeignKey("sales_trainer_units.unit_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        String(36),
        ForeignKey("question_items.question_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_index = Column(Integer, nullable=False, default=1)
    points = Column(Integer, nullable=False, default=10)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "unit_id", "question_id", name="uq_sales_trainer_unit_question"
        ),
        CheckConstraint("order_index >= 1", name="ck_sales_trainer_question_order"),
        CheckConstraint("points > 0", name="ck_sales_trainer_question_points"),
        Index(
            "idx_sales_trainer_unit_questions_order",
            "unit_id",
            "order_index",
        ),
    )


class SalesTrainerQuizAttempt(Base):
    __tablename__ = "sales_trainer_quiz_attempts"

    attempt_id = Column(String(36), primary_key=True, default=_uuid)
    unit_id = Column(
        String(36), ForeignKey("sales_trainer_units.unit_id"), nullable=False, index=True
    )
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    total_score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)
    status = Column(String(20), nullable=False, default="submitted", index=True)
    submitted_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'scored', 'failed')",
            name="ck_sales_trainer_quiz_status",
        ),
        Index(
            "idx_sales_trainer_quiz_attempt_user",
            "user_id",
            "submitted_at",
        ),
    )


class SalesTrainerQuizAnswer(Base):
    __tablename__ = "sales_trainer_quiz_answers"

    answer_id = Column(String(36), primary_key=True, default=_uuid)
    attempt_id = Column(
        String(36),
        ForeignKey("sales_trainer_quiz_attempts.attempt_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        String(36), ForeignKey("question_items.question_id"), nullable=False, index=True
    )
    question_type = Column(String(30), nullable=False)
    answer_payload = Column(JSON, nullable=False, default=dict)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class SalesTrainerAudioSubmission(Base):
    __tablename__ = "sales_trainer_audio_submissions"

    submission_id = Column(String(36), primary_key=True, default=_uuid)
    unit_id = Column(
        String(36), ForeignKey("sales_trainer_units.unit_id"), nullable=True, index=True
    )
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    purpose = Column(String(50), nullable=False, default="general_audio_scoring")
    original_filename = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(Text, nullable=False)
    file_hash = Column(String(128), nullable=True)
    duration_seconds = Column(Numeric(10, 2), nullable=True)
    source_page = Column(String(100), nullable=True)
    status = Column(String(40), nullable=False, default="uploaded", index=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'uploaded', 'transcribing', 'transcribed', 'transcription_failed', "
            "'scoring', 'scored', 'scoring_failed'"
            ")",
            name="ck_sales_trainer_audio_status",
        ),
        Index(
            "idx_sales_trainer_audio_user_created",
            "user_id",
            "created_at",
        ),
    )


class SalesTrainerAudioTranscript(Base):
    __tablename__ = "sales_trainer_audio_transcripts"

    transcript_id = Column(String(36), primary_key=True, default=_uuid)
    submission_id = Column(
        String(36),
        ForeignKey("sales_trainer_audio_submissions.submission_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    transcript_text = Column(Text, nullable=False)
    raw_payload = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class SalesTrainerAudioScorePrompt(Base):
    __tablename__ = "sales_trainer_audio_score_prompts"

    prompt_id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    purpose = Column(String(50), nullable=False, default="general_audio_scoring")
    system_prompt = Column(Text, nullable=False)
    scoring_template = Column(Text, nullable=False)
    output_schema = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="draft", index=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_sales_trainer_prompt_status",
        ),
        Index("idx_sales_trainer_prompts_status", "status", "updated_at"),
    )


class SalesTrainerAudioScoreResult(Base):
    __tablename__ = "sales_trainer_audio_score_results"

    score_id = Column(String(36), primary_key=True, default=_uuid)
    submission_id = Column(
        String(36),
        ForeignKey("sales_trainer_audio_submissions.submission_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_id = Column(
        String(36),
        ForeignKey("sales_trainer_audio_score_prompts.prompt_id"),
        nullable=False,
        index=True,
    )
    prompt_version = Column(Integer, nullable=False)
    prompt_hash = Column(String(128), nullable=False)
    deucate_model = Column(String(100), nullable=True)
    transcript_snapshot = Column(Text, nullable=True)
    total_score = Column(Numeric(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)
    summary = Column(Text, nullable=True)
    strengths = Column(JSON, nullable=False, default=list)
    improvements = Column(JSON, nullable=False, default=list)
    dimension_scores = Column(JSON, nullable=False, default=dict)
    raw_response = Column(JSON, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class SalesTrainerOperationLog(Base):
    __tablename__ = "sales_trainer_operation_logs"

    log_id = Column(String(36), primary_key=True, default=_uuid)
    actor_id = Column(String(36), ForeignKey("users.user_id"), nullable=True, index=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(String(36), nullable=True, index=True)
    request_id = Column(String(100), nullable=True)
    ip_address = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("idx_sales_trainer_operation_actor", "actor_id", "created_at"),
        Index("idx_sales_trainer_operation_target", "target_type", "target_id"),
    )
