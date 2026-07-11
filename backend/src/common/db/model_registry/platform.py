"""Grouped SQLAlchemy declarations extracted from the compatibility model registry."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from common.db.model_registry.base import Base


class Achievement(Base):
    """Configurable achievement rule definition for retention loops."""

    __tablename__ = "achievements"

    achievement_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    icon_key = Column(String(60), nullable=False, default="trophy")
    condition_json = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user_achievements = relationship(
        "UserAchievement",
        back_populates="achievement",
        cascade="all, delete-orphan",
    )


class UserAchievement(Base):
    """Idempotent achievement unlock for a user."""

    __tablename__ = "user_achievements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    achievement_id = Column(
        String(36),
        ForeignKey("achievements.achievement_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_json = Column(JSON, nullable=False, default=dict)
    unlocked_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "achievement_id",
            name="uq_user_achievements_user_achievement",
        ),
        Index("idx_user_achievements_user_unlocked", "user_id", "unlocked_at"),
    )

    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


class Notification(Base):
    """In-app notification with read/unread, expiry, and evidence metadata."""

    __tablename__ = "notifications"

    notification_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(30), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    content = Column(Text, nullable=False)
    action_label = Column(String(80), nullable=True)
    action_path = Column(String(500), nullable=True)
    source = Column(String(160), nullable=True, index=True)
    evidence_json = Column(JSON, nullable=False, default=dict)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('system', 'tip', 'reminder', 'achievement', 'ai_coach')",
            name="ck_notification_type",
        ),
        Index(
            "idx_notifications_user_read_created", "user_id", "is_read", "created_at"
        ),
    )

    user = relationship("User", back_populates="notifications")


class UserGoal(Base):
    """User-configurable practice goal."""

    __tablename__ = "user_goals"

    goal_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type = Column(String(40), nullable=False)
    period = Column(String(20), nullable=False, default="weekly")
    target_count = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "goal_type IN ('weekly_sessions', 'monthly_presentations')",
            name="ck_user_goal_type",
        ),
        CheckConstraint(
            "period IN ('weekly', 'monthly')",
            name="ck_user_goal_period",
        ),
        CheckConstraint("target_count > 0", name="ck_user_goal_target_positive"),
        Index("idx_user_goals_user_active", "user_id", "is_active"),
    )

    user = relationship("User", back_populates="goals")


class ManagerIntervention(Base):
    __tablename__ = "manager_interventions"

    intervention_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    manager_user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    user_id = Column(
        String(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    issue_family = Column(String(64), nullable=False, index=True)
    note = Column(Text)
    due_state = Column(String(20), nullable=False, default="pending", index=True)
    reminder_status = Column(String(20), nullable=False, default="not_sent")
    reminder_sent_at = Column(DateTime(timezone=True))
    resolving_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "due_state IN ('pending', 'due', 'resolved')",
            name="ck_manager_intervention_due_state",
        ),
        CheckConstraint(
            "reminder_status IN ('not_sent', 'sent')",
            name="ck_manager_intervention_reminder_status",
        ),
        CheckConstraint(
            "(resolving_session_id IS NULL AND due_state IN ('pending', 'due')) OR "
            "(resolving_session_id IS NOT NULL AND due_state = 'resolved')",
            name="ck_manager_intervention_resolution_state",
        ),
        Index("idx_manager_interventions_user_created", "user_id", "created_at"),
        Index(
            "idx_manager_interventions_manager_created", "manager_user_id", "created_at"
        ),
    )


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    entry_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    scenario_type = Column(String(20), nullable=False, index=True)
    presentation_id = Column(String(36), ForeignKey("presentations.presentation_id"))
    average_score = Column(Float, nullable=False)
    total_sessions = Column(Integer, default=1)
    rank = Column(Integer, index=True)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('presentation', 'sales')",
            name="ck_leaderboard_scenario_type",
        ),
        CheckConstraint("average_score BETWEEN 0 AND 100", name="ck_leaderboard_score"),
        UniqueConstraint(
            "user_id",
            "scenario_type",
            "presentation_id",
            name="uq_leaderboard_user_scenario",
        ),
        Index("idx_leaderboard_scenario", "scenario_type"),
        Index("idx_leaderboard_rank", "rank"),
    )

    # Relationships
    user = relationship("User", back_populates="leaderboard_entries")


class SystemLog(Base):
    """
    SystemLog - Audit log for system activities

    Tracks user actions and system events for audit purposes.

    References:
    - Requirements: 7.1, 7.2, 7.3
    - Design: Section "System Logs API"
    """

    __tablename__ = "system_logs"

    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(100), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    user_identifier = Column(String(255), nullable=False)  # email or "system"
    ip_address = Column(String(45), nullable=True)
    status = Column(
        String(20), nullable=False, default="success"
    )  # success, failed, warning
    details = Column(String, nullable=True)  # JSON string for additional details
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'warning')", name="ck_system_log_status"
        ),
        Index("idx_system_logs_created_at", "created_at"),
        Index("idx_system_logs_user_id", "user_id"),
        Index("idx_system_logs_action", "action"),
    )

    # Relationships
    user = relationship("User", backref="system_logs")


class ReleaseVerificationRecord(Base):
    """
    ReleaseVerificationRecord - Records release gate verification results

    Tracks verification checks for release candidates to ensure
    quality gates are passed before deployment.

    References:
    - Requirements: FR40 - Release gate check results recording and tracking
    - NFR19: Contract test pass rate 100% required for release
    """

    __tablename__ = "release_verification_records"

    record_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    release_version = Column(String(50), nullable=False, index=True)
    release_candidate_id = Column(String(100), nullable=False, index=True)

    # Check details
    check_type = Column(String(20), nullable=False)
    check_name = Column(String(200), nullable=False)
    check_description = Column(Text, nullable=True)

    # Result
    status = Column(String(20), nullable=False, default="pending")
    passed = Column(Boolean, nullable=False, default=False)
    details = Column(JSON, nullable=True)  # Additional check-specific data
    error_message = Column(Text, nullable=True)

    # Audit trail
    executed_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Traceability
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        CheckConstraint(
            "check_type IN ("
            "'migration', "
            "'unit_tests', "
            "'coverage', "
            "'integration_tests', "
            "'contract', "
            "'performance', "
            "'health', "
            "'security', "
            "'documentation', "
            "'manual'"
            ")",
            name="ck_verification_check_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'skipped')",
            name="ck_verification_status",
        ),
        Index("idx_verification_release_version", "release_version"),
        Index("idx_verification_candidate", "release_candidate_id"),
        Index("idx_verification_status", "status"),
        Index("idx_verification_type", "check_type"),
    )

    # Relationships
    executor = relationship("User", foreign_keys=[executed_by])


class ReleaseVerificationSummary(Base):
    """
    ReleaseVerificationSummary - Overall verification summary for a release candidate

    Aggregates all verification checks for a release candidate to provide
    a go/no-go decision summary.
    """

    __tablename__ = "release_verification_summaries"

    summary_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    release_version = Column(String(50), nullable=False, unique=True, index=True)
    release_candidate_id = Column(String(100), nullable=False, unique=True)

    # Summary counts
    total_checks = Column(Integer, nullable=False, default=0)
    passed_checks = Column(Integer, nullable=False, default=0)
    failed_checks = Column(Integer, nullable=False, default=0)
    skipped_checks = Column(Integer, nullable=False, default=0)
    pending_checks = Column(Integer, nullable=False, default=0)

    # Overall decision
    overall_status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, passed, failed
    go_no_go_decision = Column(String(10), nullable=True)  # go, no_go, conditional
    decision_reason = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    finalized_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "overall_status IN ('pending', 'passed', 'failed')",
            name="ck_verification_summary_status",
        ),
        CheckConstraint(
            "go_no_go_decision IS NULL OR go_no_go_decision IN ('go', 'no_go', 'conditional')",
            name="ck_go_no_go_decision",
        ),
        Index("idx_verification_summary_version", "release_version"),
    )

    # Relationships
    finalizer = relationship("User", foreign_keys=[finalized_by])


class SessionAudioSegment(Base):
    """Audio segment metadata for browser-direct OSS uploads.

    Each row represents one audio chunk uploaded during a training session.
    The actual audio bytes live in Alibaba Cloud OSS; this table only stores
    metadata and upload status.
    """

    __tablename__ = "session_audio_segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_sequence = Column(Integer, nullable=False)
    object_key = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False, default="audio/webm")
    size_bytes = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    upload_status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "upload_status IN ('pending', 'uploaded', 'failed')",
            name="ck_audio_segment_upload_status",
        ),
        UniqueConstraint(
            "session_id",
            "segment_sequence",
            name="uq_audio_segment_session_sequence",
        ),
        Index("idx_audio_segments_session", "session_id"),
    )

    # Relationships
    session = relationship("PracticeSession", back_populates="audio_segments")


__all__ = [
    "Achievement",
    "UserAchievement",
    "Notification",
    "UserGoal",
    "ManagerIntervention",
    "LeaderboardEntry",
    "SystemLog",
    "ReleaseVerificationRecord",
    "ReleaseVerificationSummary",
    "SessionAudioSegment",
]
