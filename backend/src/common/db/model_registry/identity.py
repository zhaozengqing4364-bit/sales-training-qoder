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
from sqlalchemy.orm import relationship

from common.auth.roles import admin_permission_role_check_sql, user_role_check_sql
from common.db.model_registry.base import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wechat_user_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100))
    email = Column(String(255), unique=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(32), default="user", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint(
            user_role_check_sql(),
            name="ck_user_role",
        ),
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
