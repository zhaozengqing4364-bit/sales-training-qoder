"""Grouped SQLAlchemy declarations extracted from the compatibility model registry."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from common.db.model_registry.base import Base, _jsonb_compatible_type
from common.db.model_registry.enums import (
    EvaluationRunStatus,
)


class EvaluationRun(Base):
    """Durable record of one evaluation pass over session evidence."""

    __tablename__ = "evaluation_runs"

    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    config_bundle_id = Column(
        String(36),
        ForeignKey("config_bundles.bundle_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    config_version_id = Column(
        String(36),
        ForeignKey("config_versions.version_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        String(32),
        nullable=False,
        default=EvaluationRunStatus.PENDING.value,
        server_default=EvaluationRunStatus.PENDING.value,
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    input_evidence_reference = Column(JSON, nullable=False, default=dict)
    result_payload = Column(JSON, nullable=True)
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    error_trace = Column(Text, nullable=True)
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
        UniqueConstraint("session_id", name="uq_evaluation_runs_session"),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'non_evaluable', 'failed')",
            name="ck_evaluation_run_status",
        ),
        Index("idx_evaluation_runs_session_status", "session_id", "status"),
        Index(
            "idx_evaluation_runs_config_binding",
            "config_bundle_id",
            "config_version_id",
        ),
    )

    session = relationship("PracticeSession", back_populates="evaluation_runs")
    config_bundle = relationship("ConfigBundle")
    config_version = relationship("ConfigVersion")
    report_snapshots = relationship(
        "TrainingReportSnapshot",
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
    )


class TrainingReportSnapshot(Base):
    """Immutable report payload snapshot for one practice session."""

    __tablename__ = "training_report_snapshots"

    snapshot_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evaluation_run_id = Column(
        String(36),
        ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_payload = Column(JSON, nullable=False, default=dict)
    config_bundle_id = Column(
        String(36),
        ForeignKey("config_bundles.bundle_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    config_bundle_snapshot = Column(JSON, nullable=True)
    ruleset_source = Column(String(80), nullable=False, default="legacy_unversioned")
    ruleset_version = Column(String(80), nullable=False, default="legacy_unversioned")
    score_basis = Column(String(120), nullable=False, default="legacy_unversioned")
    evidence_completeness = Column(JSON, nullable=False, default=dict)
    non_evaluable_reason = Column(Text, nullable=True)
    generated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("session_id", name="uq_training_report_snapshots_session"),
        UniqueConstraint(
            "evaluation_run_id",
            name="uq_training_report_snapshots_evaluation_run",
        ),
        Index(
            "idx_training_report_snapshots_session_generated",
            "session_id",
            "generated_at",
        ),
    )

    session = relationship("PracticeSession", back_populates="report_snapshots")
    evaluation_run = relationship("EvaluationRun", back_populates="report_snapshots")
    config_bundle = relationship("ConfigBundle")


class StagedEvaluationResult(Base):
    """Staged evaluation result for a practice session.
    Matches actual DB schema.
    """

    __tablename__ = "staged_evaluation_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False)
    stage_number = Column(Integer, nullable=False)
    start_turn = Column(Integer, nullable=False, default=0)
    end_turn = Column(Integer, nullable=False, default=0)
    scores = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    strengths = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    weaknesses = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    suggestions = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    summary = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        Index("idx_staged_eval_session", "session_id"),
        Index("idx_staged_eval_stage", "session_id", "stage_number", unique=True),
        {"extend_existing": True},
    )


class ComprehensiveReport(Base):
    """Comprehensive evaluation report for a practice session.
    Matches actual DB schema.
    """

    __tablename__ = "comprehensive_reports"

    session_id = Column(String(36), primary_key=True)
    overall_score = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    dimension_scores = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    key_strengths = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    key_improvements = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    recommendations = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    detailed_feedback = Column(Text, nullable=True)
    stage_summaries = Column(
        _jsonb_compatible_type(),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    scoring_metadata = Column(
        _jsonb_compatible_type(),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = {"extend_existing": True}


class SupervisorReview(Base):
    """Supervisor decision for one completed practice report."""

    __tablename__ = "supervisor_reviews"

    review_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trainee_user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supervisor_user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision = Column(String(32), nullable=False, default="pending", index=True)
    readiness_status = Column(String(32), nullable=False, default="not_ready")
    comment = Column(Text, nullable=True)
    required_retraining = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    audit_metadata = Column(_jsonb_compatible_type(), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected', 'needs_retraining')",
            name="ck_supervisor_review_decision",
        ),
        CheckConstraint(
            "readiness_status IN ('not_ready', 'shadow_only', 'ready_for_trial', 'approved')",
            name="ck_supervisor_review_readiness_status",
        ),
        UniqueConstraint("session_id", name="uq_supervisor_review_session"),
        Index("idx_supervisor_reviews_trainee_decision", "trainee_user_id", "decision"),
        Index(
            "idx_supervisor_reviews_supervisor_created",
            "supervisor_user_id",
            "created_at",
        ),
    )


class RetrainingTask(Base):
    """Minimal task created when a supervisor requires retraining."""

    __tablename__ = "retraining_tasks"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_review_id = Column(
        String(36),
        ForeignKey("supervisor_reviews.review_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    training_task_id = Column(
        String(36),
        ForeignKey("training_tasks.task_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    skill_dimension = Column(String(120), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="todo", index=True)
    completed_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'completed', 'cancelled')",
            name="ck_retraining_task_status",
        ),
        UniqueConstraint(
            "source_review_id",
            "skill_dimension",
            name="uq_retraining_task_review_dimension",
        ),
        Index("idx_retraining_tasks_user_status", "user_id", "status"),
        Index("idx_retraining_tasks_training_status", "training_task_id", "status"),
        Index(
            "idx_retraining_tasks_source_completed",
            "source_session_id",
            "completed_session_id",
        ),
    )

    training_task = relationship(
        "TrainingTask",
        back_populates="retraining_tasks",
        foreign_keys=[training_task_id],
    )


class SupervisorScoreCalibration(Base):
    """Supervisor correction of an AI dimension score without mutating AI output."""

    __tablename__ = "supervisor_score_calibrations"

    calibration_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    review_id = Column(
        String(36),
        ForeignKey("supervisor_reviews.review_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dimension = Column(String(120), nullable=False)
    ai_score = Column(Float, nullable=True)
    supervisor_score = Column(Float, nullable=True)
    calibration_label = Column(String(32), nullable=False)
    comment = Column(Text, nullable=True)
    calibrated_by_user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "calibration_label IN ('accurate', 'too_high', 'too_low', 'wrong_reason', 'missing_evidence')",
            name="ck_supervisor_score_calibration_label",
        ),
        CheckConstraint(
            "ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)",
            name="ck_supervisor_score_calibration_ai_score",
        ),
        CheckConstraint(
            "supervisor_score IS NULL OR (supervisor_score >= 0 AND supervisor_score <= 100)",
            name="ck_supervisor_score_calibration_supervisor_score",
        ),
        UniqueConstraint(
            "review_id",
            "dimension",
            name="uq_supervisor_score_calibration_review_dimension",
        ),
        Index(
            "idx_supervisor_score_calibrations_session_dimension",
            "session_id",
            "dimension",
        ),
    )


__all__ = [
    "EvaluationRun",
    "TrainingReportSnapshot",
    "StagedEvaluationResult",
    "ComprehensiveReport",
    "SupervisorReview",
    "RetrainingTask",
    "SupervisorScoreCalibration",
]
