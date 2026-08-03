"""SQLAlchemy persistence owned exclusively by the structured AI Coach domain."""

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


class CoachProfileRevision(Base):
    __tablename__ = "coach_profile_revisions"

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    stable_key: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    published_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "stable_key",
            "revision_no",
            name="uq_coach_profile_revision_number",
        ),
        CheckConstraint(
            "status IN ('working','published','archived')",
            name="ck_coach_profile_revision_status",
        ),
    )


class CoachSession(Base):
    __tablename__ = "coach_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    enrollment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_enrollments_v2.enrollment_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    path_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("newcomer_activity_attempts_v2.attempt_id", ondelete="RESTRICT"),
        nullable=False,
    )
    profile_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_profile_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    profile_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    context_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    competency_keys_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    checkpoint_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_cycle_id: Mapped[str | None] = mapped_column(String(36))
    active_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("durable_tasks.task_id", ondelete="SET NULL"), index=True
    )
    failure_stage: Mapped[str | None] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(120))
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    human_help_status: Mapped[str | None] = mapped_column(String(24))
    human_help_next_action_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON_DOCUMENT
    )
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_coach_sessions_attempt_id"),
        CheckConstraint(
            "checkpoint_index BETWEEN 0 AND 2", name="ck_coach_session_checkpoint"
        ),
        CheckConstraint("cycle_no BETWEEN 0 AND 2", name="ck_coach_session_cycle"),
        CheckConstraint(
            "status IN ('created','preparing','awaiting_answer','evaluating',"
            "'feedback_ready','checkpoint_mastered','remediation_required',"
            "'completed','needs_human_help','failed_recoverable','cancelled')",
            name="ck_coach_session_status",
        ),
        CheckConstraint(
            "human_help_status IS NULL OR human_help_status IN ('open','resolved')",
            name="ck_coach_session_human_help_status",
        ),
        Index(
            "ix_coach_session_help_queue",
            "organization_id",
            "status",
            "updated_at",
        ),
    )


class CoachRemediationCycle(Base):
    __tablename__ = "coach_remediation_cycles"

    cycle_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    checkpoint_index: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_key: Mapped[str] = mapped_column(String(120), nullable=False)
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    input_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    remediation_inputs_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    generation_strategy: Mapped[str | None] = mapped_column(Text)
    generation_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("durable_tasks.task_id", ondelete="SET NULL")
    )
    generation_invocation_id: Mapped[str | None] = mapped_column(String(160))
    score_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    maximum_uncertainty: Mapped[float | None] = mapped_column(Numeric(6, 5))
    result_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "checkpoint_index",
            "cycle_no",
            name="uq_coach_cycle_checkpoint_number",
        ),
        CheckConstraint(
            "checkpoint_index BETWEEN 0 AND 2", name="ck_coach_cycle_checkpoint"
        ),
        CheckConstraint("cycle_no BETWEEN 0 AND 2", name="ck_coach_cycle_number"),
        CheckConstraint(
            "status IN ('generating','active','completed','mastered',"
            "'remediation_needed','failed','needs_human_help','cancelled')",
            name="ck_coach_cycle_status",
        ),
    )


class CoachTurn(Base):
    __tablename__ = "coach_turns"

    turn_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    cycle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_remediation_cycles.cycle_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    checkpoint_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_coach_turn_sequence"),
        UniqueConstraint(
            "cycle_id", "cycle_position", name="uq_coach_turn_cycle_position"
        ),
        CheckConstraint(
            "status IN ('pending','current','answered','scored','cancelled')",
            name="ck_coach_turn_status",
        ),
    )


class CoachTrainingCard(Base):
    __tablename__ = "coach_training_cards"

    card_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    cycle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_remediation_cycles.cycle_id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_turns.turn_id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    card_type: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    public_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    evaluation_spec_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    source_ref_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    generation_invocation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("turn_id", name="uq_coach_training_cards_turn_id"),
        CheckConstraint(
            "card_type IN ('single_choice','multiple_choice','ordering',"
            "'short_answer_rewrite','scenario_choice','key_points_completion',"
            "'example_comparison','summary')",
            name="ck_coach_training_card_type",
        ),
        CheckConstraint(
            "evaluation_mode IN ('deterministic','ai')",
            name="ck_coach_training_card_evaluation_mode",
        ),
        CheckConstraint(
            "status IN ('pending','current','answered','scored','cancelled')",
            name="ck_coach_training_card_status",
        ),
    )


class CoachCardResponse(Base):
    __tablename__ = "coach_card_responses"

    response_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    card_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_training_cards.card_id", ondelete="RESTRICT"),
        nullable=False,
    )
    turn_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_turns.turn_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    raw_answer_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    client_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("durable_tasks.task_id", ondelete="SET NULL")
    )
    score_percent: Mapped[float | None] = mapped_column(Numeric(6, 3))
    mastered: Mapped[bool | None] = mapped_column(Boolean)
    evaluation_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    uncertainty: Mapped[float | None] = mapped_column(Numeric(6, 5))
    source_ref_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    evaluation_kind: Mapped[str | None] = mapped_column(String(24))
    invocation_id: Mapped[str | None] = mapped_column(String(160))
    prompt_template_id: Mapped[str | None] = mapped_column(String(160))
    prompt_revision_id: Mapped[str | None] = mapped_column(String(160))
    prompt_contract_hash: Mapped[str | None] = mapped_column(String(80))
    model_routing_profile_id: Mapped[str | None] = mapped_column(String(160))
    model_routing_revision_id: Mapped[str | None] = mapped_column(String(160))
    error_code: Mapped[str | None] = mapped_column(String(120))
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("card_id", name="uq_coach_card_responses_card_id"),
        UniqueConstraint(
            "session_id", "client_token_hash", name="uq_coach_response_client_token"
        ),
        CheckConstraint(
            "status IN ('saved','evaluating','evaluated','failed_recoverable','cancelled')",
            name="ck_coach_response_status",
        ),
        CheckConstraint(
            "evaluation_kind IS NULL OR evaluation_kind IN ('deterministic','ai')",
            name="ck_coach_response_evaluation_kind",
        ),
    )


class CoachAssistance(Base):
    __tablename__ = "coach_assistances"

    assistance_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_id
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    card_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_training_cards.card_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    assistance_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("durable_tasks.task_id", ondelete="SET NULL")
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT)
    source_ref_ids_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    invocation_id: Mapped[str | None] = mapped_column(String(160))
    prompt_revision_id: Mapped[str | None] = mapped_column(String(160))
    model_routing_revision_id: Mapped[str | None] = mapped_column(String(160))
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "idempotency_key_hash",
            name="uq_coach_assistance_idempotency",
        ),
        CheckConstraint(
            "assistance_type IN ('explain','example')",
            name="ck_coach_assistance_type",
        ),
        CheckConstraint(
            "status IN ('queued','completed','failed_recoverable','cancelled')",
            name="ck_coach_assistance_status",
        ),
    )


class CoachOutcome(Base):
    __tablename__ = "coach_outcomes"

    outcome_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(String(36), nullable=False)
    profile_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    mastery_score_percent: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    checkpoint_results_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    cycle_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    source_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    lineage_json: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    generic_activity_outcome_id: Mapped[str | None] = mapped_column(String(36))
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("session_id", name="uq_coach_outcomes_session_id"),
    )


class CoachHumanIntervention(Base):
    __tablename__ = "coach_human_interventions"

    intervention_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_id
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("coach_sessions.session_id", ondelete="RESTRICT"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    guidance: Mapped[str | None] = mapped_column(Text)
    target_resource_id: Mapped[str | None] = mapped_column(String(160))
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "idempotency_key_hash",
            name="uq_coach_human_intervention_idempotency",
        ),
        CheckConstraint(
            "action IN ('add_guidance','assign_learning','assign_audio',"
            "'restart_coach','no_further_action')",
            name="ck_coach_human_intervention_action",
        ),
    )


class CoachCommandAudit(Base):
    __tablename__ = "coach_command_audits"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(
        String(120), nullable=False, index=True
    )
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    capability: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(120), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    command: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    before_version: Mapped[int | None] = mapped_column(Integer)
    after_version: Mapped[int | None] = mapped_column(Integer)
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(160))
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


__all__ = [
    "CoachAssistance",
    "CoachCardResponse",
    "CoachCommandAudit",
    "CoachHumanIntervention",
    "CoachOutcome",
    "CoachProfileRevision",
    "CoachRemediationCycle",
    "CoachSession",
    "CoachTrainingCard",
    "CoachTurn",
]
