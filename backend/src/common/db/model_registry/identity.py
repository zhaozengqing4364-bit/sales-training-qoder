"""Grouped SQLAlchemy declarations extracted from the compatibility model registry."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.auth.roles import admin_permission_role_check_sql, user_role_check_sql
from common.db.model_registry.base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wechat_user_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="active"
    )
    temporary_password_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    credential_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    role: Mapped[str] = mapped_column(
        String(32), default="user", nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=True
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool | None] = mapped_column(
        Boolean, default=True, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            user_role_check_sql(),
            name="ck_user_role",
        ),
        CheckConstraint(
            "credential_status IN ('active', 'temporary', 'reset_required')",
            name="ck_users_credential_status",
        ),
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
    )

    # Relationships
    practice_sessions = relationship("PracticeSession", back_populates="user")
    leaderboard_entries = relationship("LeaderboardEntry", back_populates="user")
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    training_preferences = relationship(
        "UserTrainingPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    presentation_progress = relationship(
        "UserPresentationProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    achievements = relationship(
        "UserAchievement",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    goals = relationship(
        "UserGoal",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    highlight_reviews = relationship(
        "HighlightReview",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    training_tasks = relationship(
        "TrainingTask",
        back_populates="assignee",
        cascade="all, delete-orphan",
    )


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    membership_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    membership_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="primary"
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        CheckConstraint(
            "membership_role IN ('primary')", name="ck_team_membership_role"
        ),
        Index(
            "uq_team_memberships_active_primary_user",
            "user_id",
            unique=True,
            postgresql_where=text(
                "effective_to IS NULL AND membership_role = 'primary'"
            ),
            sqlite_where=text("effective_to IS NULL AND membership_role = 'primary'"),
        ),
    )


class TeamLeaderAssignment(Base):
    __tablename__ = "team_leader_assignments"

    assignment_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    leader_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignment_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="primary"
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        CheckConstraint(
            "assignment_role IN ('primary', 'proxy')",
            name="ck_team_leader_assignment_role",
        ),
        Index(
            "uq_team_leader_assignments_active_primary_team",
            "team_id",
            unique=True,
            postgresql_where=text(
                "effective_to IS NULL AND assignment_role = 'primary'"
            ),
            sqlite_where=text("effective_to IS NULL AND assignment_role = 'primary'"),
        ),
        Index(
            "uq_team_leader_assignments_active_role",
            "team_id",
            "leader_user_id",
            "assignment_role",
            unique=True,
            postgresql_where=text("effective_to IS NULL"),
            sqlite_where=text("effective_to IS NULL"),
        ),
    )


class ProvisioningBatch(Base):
    __tablename__ = "provisioning_batches"

    batch_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="previewed", index=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('previewed', 'processing', 'completed', 'partially_completed', 'failed')",
            name="ck_provisioning_batch_status",
        ),
    )


class ProvisioningTeamExecution(Base):
    __tablename__ = "provisioning_team_executions"

    execution_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("provisioning_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending"
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_provisioning_team_execution_status",
        ),
        UniqueConstraint(
            "batch_id", "team_code", name="uq_provisioning_team_execution"
        ),
    )


class ProvisioningRow(Base):
    __tablename__ = "provisioning_rows"

    row_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    batch_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("provisioning_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    team_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    team_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    primary_leader_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    employee_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="valid"
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('valid', 'invalid', 'created', 'failed', 'skipped')",
            name="ck_provisioning_row_status",
        ),
        UniqueConstraint(
            "batch_id", "row_number", name="uq_provisioning_batch_row_number"
        ),
    )


class AdminRolePermission(Base):
    """Persisted role-to-permission mapping for admin action-level RBAC."""

    __tablename__ = "admin_role_permissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role = Column(String(20), nullable=False, index=True)
    permission = Column(String(80), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            admin_permission_role_check_sql(),
            name="ck_admin_role_permissions_role",
        ),
        UniqueConstraint(
            "role", "permission", name="uq_admin_role_permissions_role_permission"
        ),
        Index("idx_admin_role_permissions_role_permission", "role", "permission"),
    )


class UserTrainingPreference(Base):
    __tablename__ = "user_training_preferences"

    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    voice_mode = Column(String(32), nullable=True)
    agent_id = Column(String(36), nullable=True)
    persona_id = Column(String(36), nullable=True)
    presentation_id = Column(String(36), nullable=True)
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
            "voice_mode IS NULL OR voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_user_training_preferences_voice_mode",
        ),
    )

    user = relationship("User", back_populates="training_preferences")


class UserPresentationProgress(Base):
    """Per-user durable progress marker for resuming long PPT practice."""

    __tablename__ = "user_presentation_progress"

    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    presentation_id = Column(
        String(36),
        ForeignKey("presentations.presentation_id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_page_number = Column(Integer, nullable=False)
    last_session_id = Column(
        String(36),
        ForeignKey("practice_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_practice_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
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
            "last_page_number >= 1",
            name="ck_user_presentation_progress_page_positive",
        ),
        Index(
            "idx_user_presentation_progress_user_updated",
            "user_id",
            "updated_at",
        ),
    )

    user = relationship("User", back_populates="presentation_progress")
    presentation = relationship("Presentation", back_populates="user_progress")


class PasswordResetToken(Base):
    """Durable password-reset lifecycle row.

    Formal auth-recovery work should extend this model + its Alembic history
    (`026_password_reset_tokens`, `027_reset_lifecycle_delivery`, and
    `028_reset_single_active_token`) instead of reintroducing
    `used_at` is reserved for successful consumption, while `invalidated_at`
    records superseded/expired tokens that must still remain auditable.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    invalidated_at = Column(DateTime(timezone=True), nullable=True, index=True)
    invalidation_reason = Column(String(32), nullable=True)
    delivery_status = Column(String(20), nullable=False, default="pending", index=True)
    delivery_attempted_at = Column(DateTime(timezone=True), nullable=True)
    delivery_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'failed')",
            name="ck_password_reset_tokens_delivery_status",
        ),
        CheckConstraint(
            "invalidation_reason IS NULL OR invalidation_reason IN ('superseded', 'expired')",
            name="ck_password_reset_tokens_invalidation_reason",
        ),
        Index("idx_password_reset_tokens_user_created", "user_id", "created_at"),
        Index(
            "uq_password_reset_tokens_single_active_user",
            "user_id",
            unique=True,
            sqlite_where=text("used_at IS NULL AND invalidated_at IS NULL"),
            postgresql_where=text("used_at IS NULL AND invalidated_at IS NULL"),
        ),
    )

    user = relationship("User", back_populates="password_reset_tokens")


__all__ = [
    "User",
    "AdminRolePermission",
    "UserTrainingPreference",
    "UserPresentationProgress",
    "PasswordResetToken",
]
