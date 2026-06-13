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

import sales_trainer.ai_coach_chat_models  # noqa: F401
import sales_trainer.regrade_models  # noqa: F401
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


class SalesTrainerExamPaper(Base):
    __tablename__ = "sales_trainer_exam_papers"

    paper_id = Column(String(36), primary_key=True, default=_uuid)
    paper_key = Column(String(120), nullable=False, unique=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    module_key = Column(
        String(80), nullable=False, default="business_skills", index=True
    )
    unit_id = Column(
        String(36),
        ForeignKey("sales_trainer_units.unit_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pass_threshold = Column(Numeric(5, 2), nullable=True)
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
            name="ck_sales_trainer_exam_paper_status",
        ),
        CheckConstraint(
            "pass_threshold IS NULL OR pass_threshold >= 0",
            name="ck_sales_trainer_exam_paper_pass_threshold",
        ),
        Index(
            "idx_sales_trainer_exam_papers_module_status",
            "module_key",
            "status",
            "updated_at",
        ),
    )


class SalesTrainerAssetRevision(Base):
    __tablename__ = "sales_trainer_asset_revisions"

    revision_id = Column(String(36), primary_key=True, default=_uuid)
    resource_type = Column(String(80), nullable=False, index=True)
    logical_id = Column(String(120), nullable=False, index=True)
    revision_no = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="working", index=True)
    payload_json = Column("payload", JSON, nullable=False, default=dict)
    payload_hash = Column(String(128), nullable=False)
    change_class = Column(String(40), nullable=False, default="semantic")
    source_revision_id = Column(
        String(36),
        ForeignKey("sales_trainer_asset_revisions.revision_id"),
        nullable=True,
    )
    reason = Column(Text, nullable=True)
    trace_id = Column(String(100), nullable=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    published_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "logical_id",
            "revision_no",
            name="uq_sales_trainer_asset_revision_no",
        ),
        CheckConstraint(
            "status IN ('working', 'published', 'archived')",
            name="ck_sales_trainer_asset_revision_status",
        ),
        CheckConstraint(
            "change_class IN ('non_semantic', 'semantic', 'binding', 'scoring_high_risk')",
            name="ck_sales_trainer_asset_revision_change_class",
        ),
        Index(
            "idx_sales_trainer_asset_revisions_lookup",
            "resource_type",
            "logical_id",
            "status",
            "revision_no",
        ),
    )


class SalesTrainerAssetActiveRevision(Base):
    __tablename__ = "sales_trainer_asset_active_revisions"

    active_ref_id = Column(String(36), primary_key=True, default=_uuid)
    resource_type = Column(String(80), nullable=False, index=True)
    logical_id = Column(String(120), nullable=False, index=True)
    active_revision_id = Column(
        String(36),
        ForeignKey("sales_trainer_asset_revisions.revision_id"),
        nullable=False,
    )
    activated_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    activation_reason = Column(Text, nullable=True)
    trace_id = Column(String(100), nullable=True)
    activated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "resource_type",
            "logical_id",
            name="uq_sales_trainer_asset_active_ref",
        ),
        Index(
            "idx_sales_trainer_asset_active_lookup",
            "resource_type",
            "logical_id",
        ),
    )


class SalesTrainerQuizAttempt(Base):
    __tablename__ = "sales_trainer_quiz_attempts"

    attempt_id = Column(String(36), primary_key=True, default=_uuid)
    unit_id = Column(
        String(36),
        ForeignKey("sales_trainer_units.unit_id"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    paper_revision_id = Column(
        String(36),
        ForeignKey("sales_trainer_asset_revisions.revision_id"),
        nullable=True,
        index=True,
    )
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
        Index(
            "idx_sales_trainer_quiz_attempt_submitted_id",
            "submitted_at",
            "attempt_id",
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
    user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    purpose = Column(String(50), nullable=False, default="general_audio_scoring")
    original_filename = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(Text, nullable=False)
    file_hash = Column(String(128), nullable=True)
    duration_seconds = Column(Numeric(10, 2), nullable=True)
    source_page = Column(String(100), nullable=True)
    confirmed_material_version_id = Column(
        String(36),
        ForeignKey("sales_trainer_material_versions.version_id"),
        nullable=True,
    )
    confirmed_material_at = Column(DateTime(timezone=True), nullable=True)
    material_snapshot = Column(JSON, nullable=True)
    score_scheme_snapshot = Column(JSON, nullable=True)
    task_brief_snapshot = Column(JSON, nullable=True)
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
        Index(
            "idx_sales_trainer_audio_created_id",
            "created_at",
            "submission_id",
        ),
        Index(
            "idx_sales_trainer_audio_confirmed_material_version",
            "confirmed_material_version_id",
        ),
    )


class SalesTrainerMaterial(Base):
    __tablename__ = "sales_trainer_materials"

    material_id = Column(String(36), primary_key=True, default=_uuid)
    material_key = Column(String(120), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    material_type = Column(String(40), nullable=False, default="ppt_deck", index=True)
    description = Column(Text, nullable=True)
    purpose = Column(String(50), nullable=False, default="ppt_pitch", index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    current_version_id = Column(String(36), nullable=True)
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
            "material_type IN ('ppt_deck', 'script', 'example_audio', 'attachment')",
            name="ck_sales_trainer_material_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_sales_trainer_material_status",
        ),
        Index("idx_sales_trainer_material_status_updated", "status", "updated_at"),
    )


class SalesTrainerMaterialVersion(Base):
    __tablename__ = "sales_trainer_material_versions"

    version_id = Column(String(36), primary_key=True, default=_uuid)
    material_id = Column(
        String(36),
        ForeignKey("sales_trainer_materials.material_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_label = Column(String(80), nullable=False)
    title = Column(String(200), nullable=False)
    file_name = Column(String(500), nullable=False)
    content_type = Column(String(120), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    storage_key = Column(Text, nullable=False)
    file_hash = Column(String(128), nullable=True)
    release_notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
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
        UniqueConstraint(
            "material_id",
            "version_label",
            name="uq_sales_trainer_material_version_label",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_sales_trainer_material_version_status",
        ),
        CheckConstraint(
            "file_size_bytes > 0",
            name="ck_sales_trainer_material_version_file_size",
        ),
        Index(
            "idx_sales_trainer_material_versions_material_status",
            "material_id",
            "status",
            "updated_at",
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
    learner_rubric = Column(JSON, nullable=False, default=dict)
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


class SalesTrainerAiCoachSession(Base):
    __tablename__ = "sales_trainer_ai_coach_sessions"

    session_id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    module_key = Column(String(80), nullable=False, index=True)
    path_key = Column(String(80), nullable=True, index=True)
    path_revision_id = Column(
        String(36),
        ForeignKey("sales_trainer_asset_revisions.revision_id"),
        nullable=True,
    )
    path_revision_no = Column(Integer, nullable=True)
    article_snapshot = Column(JSON, nullable=False, default=dict)
    path_config_snapshot = Column(JSON, nullable=False, default=dict)
    prompt_template_id = Column(String(36), nullable=True)
    prompt_revision_id = Column(String(36), nullable=True)
    prompt_contract_hash = Column(String(128), nullable=True)
    config_snapshot = Column(JSON, nullable=False, default=dict)
    coach_state = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="in_progress", index=True)
    mastery_state = Column(String(20), nullable=True)
    total_score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), nullable=True)
    trace_id = Column(String(100), nullable=True)
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
            "status IN ('in_progress', 'completed', 'failed')",
            name="ck_sales_trainer_ai_coach_session_status",
        ),
        CheckConstraint(
            "mastery_state IS NULL OR mastery_state IN ('mastered', 'not_mastered')",
            name="ck_sales_trainer_ai_coach_session_mastery",
        ),
        Index(
            "idx_sales_trainer_ai_coach_sessions_user_status",
            "user_id",
            "status",
        ),
        Index(
            "idx_sales_trainer_ai_coach_sessions_module_created",
            "module_key",
            "created_at",
        ),
        Index(
            "idx_sales_trainer_ai_coach_sessions_created_id",
            "created_at",
            "session_id",
        ),
    )


class SalesTrainerAiCoachTurn(Base):
    __tablename__ = "sales_trainer_ai_coach_turns"

    turn_id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=False)
    ai_feedback = Column(Text, nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    max_score = Column(Numeric(5, 2), nullable=True)
    missed_points = Column(JSON, nullable=False, default=list)
    next_question = Column(Text, nullable=True)
    raw_model_output = Column(JSON, nullable=True)
    validated_output = Column(JSON, nullable=True)
    # Layered interaction v1 fields (added by migration 078b)
    interaction_snapshot = Column(JSON, nullable=True)
    public_interaction = Column(JSON, nullable=True)
    schema_version = Column(String(32), nullable=True)
    answer_payload = Column(JSON, nullable=True)
    score_result = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "turn_number >= 1",
            name="ck_sales_trainer_ai_coach_turn_number",
        ),
        UniqueConstraint(
            "session_id",
            "turn_number",
            name="uq_sales_trainer_ai_coach_turn_session_number",
        ),
        Index(
            "idx_sales_trainer_ai_coach_turns_session",
            "session_id",
            "turn_number",
        ),
        Index(
            "idx_sales_trainer_ai_coach_turns_schema_version",
            "schema_version",
        ),
    )


class SalesTrainerOperationLog(Base):
    __tablename__ = "sales_trainer_operation_logs"

    log_id = Column(String(36), primary_key=True, default=_uuid)
    actor_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=True, index=True
    )
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
