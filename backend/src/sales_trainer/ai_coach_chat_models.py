from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from common.db.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SalesTrainerAiCoachChatMessage(Base):
    __tablename__ = "sales_trainer_ai_coach_chat_messages"

    message_id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_sales_trainer_ai_coach_chat_message_role",
        ),
        UniqueConstraint(
            "session_id",
            "order_index",
            name="uq_sales_trainer_ai_coach_chat_message_order",
        ),
        Index(
            "idx_sales_trainer_ai_coach_chat_messages_session",
            "session_id",
            "order_index",
        ),
    )


class SalesTrainerAiCoachUiEvent(Base):
    __tablename__ = "sales_trainer_ai_coach_ui_events"

    event_id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_chat_messages.message_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    payload_json = Column("payload", JSON, nullable=False, default=dict)
    answer_payload = Column(JSON, nullable=True)
    score_result = Column(JSON, nullable=True)
    order_index = Column(Integer, nullable=False)
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
            "event_type IN ("
            "'assistant_text', 'quiz_card', 'quiz_result', "
            "'explanation_card', 'summary_card', 'followup_prompt'"
            ")",
            name="ck_sales_trainer_ai_coach_ui_event_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'submitted', 'scored', 'failed')",
            name="ck_sales_trainer_ai_coach_ui_event_status",
        ),
        UniqueConstraint(
            "message_id",
            "order_index",
            name="uq_sales_trainer_ai_coach_ui_event_message_order",
        ),
        Index(
            "idx_sales_trainer_ai_coach_ui_events_session",
            "session_id",
            "created_at",
        ),
    )


class SalesTrainerAiCoachCoachAction(Base):
    __tablename__ = "sales_trainer_ai_coach_coach_actions"

    action_id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_type = Column(String(40), nullable=False)
    trigger_event_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_ui_events.event_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(40), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="generated")
    state_before = Column(JSON, nullable=False, default=dict)
    state_after = Column(JSON, nullable=False, default=dict)
    assistant_message_id = Column(
        String(36),
        ForeignKey("sales_trainer_ai_coach_chat_messages.message_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_code = Column(String(120), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('session_start', 'user_message', 'event_answer')",
            name="ck_sales_trainer_ai_coach_action_trigger_type",
        ),
        CheckConstraint(
            "action IN ("
            "'continue_drill', 'increase_difficulty', 'remediate', "
            "'switch_scenario', 'summarize', 'ask_user_choice', 'end_session'"
            ")",
            name="ck_sales_trainer_ai_coach_action",
        ),
        CheckConstraint(
            "status IN ('generated', 'skipped', 'failed')",
            name="ck_sales_trainer_ai_coach_action_status",
        ),
        Index(
            "idx_sales_trainer_ai_coach_actions_session",
            "session_id",
            "created_at",
        ),
    )
