"""structured ai coach and remediation loop

Revision ID: 20260717_0930_004
Revises: 20260717_0600_003
Create Date: 2026-07-17 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_0930_004"
down_revision: str | None = "20260717_0600_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    _create_profile_and_session_tables()
    _create_cycle_card_and_response_tables()
    _create_assistance_outcome_and_governance_tables()


def _create_profile_and_session_tables() -> None:
    op.create_table(
        "coach_profile_revisions",
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("stable_key", sa.String(160), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("revision_label", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("snapshot_json", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("published_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('working','published','archived')",
            name="ck_coach_profile_revision_status",
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint(
            "organization_id",
            "stable_key",
            "revision_no",
            name="uq_coach_profile_revision_number",
        ),
    )
    op.create_index(
        "ix_coach_profile_revisions_organization_id",
        "coach_profile_revisions",
        ["organization_id"],
    )
    op.create_table(
        "coach_sessions",
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("enrollment_id", sa.String(36), nullable=False),
        sa.Column("path_revision_id", sa.String(36), nullable=False),
        sa.Column("activity_id", sa.String(160), nullable=False),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("profile_revision_id", sa.String(36), nullable=False),
        sa.Column("profile_snapshot_json", JSON_DOCUMENT, nullable=False),
        sa.Column("context_snapshot_json", JSON_DOCUMENT, nullable=False),
        sa.Column("competency_keys_json", JSON_DOCUMENT, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("checkpoint_index", sa.Integer(), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("active_cycle_id", sa.String(36), nullable=True),
        sa.Column("active_task_id", sa.String(36), nullable=True),
        sa.Column("failure_stage", sa.String(40), nullable=True),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("safe_error_message", sa.Text(), nullable=True),
        sa.Column("human_help_status", sa.String(24), nullable=True),
        sa.Column("human_help_next_action_json", JSON_DOCUMENT, nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "checkpoint_index BETWEEN 0 AND 2",
            name="ck_coach_session_checkpoint",
        ),
        sa.CheckConstraint(
            "cycle_no BETWEEN 0 AND 2",
            name="ck_coach_session_cycle",
        ),
        sa.CheckConstraint(
            "status IN ('created','preparing','awaiting_answer','evaluating',"
            "'feedback_ready','checkpoint_mastered','remediation_required',"
            "'completed','needs_human_help','failed_recoverable','cancelled')",
            name="ck_coach_session_status",
        ),
        sa.CheckConstraint(
            "human_help_status IS NULL OR human_help_status IN ('open','resolved')",
            name="ck_coach_session_human_help_status",
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["newcomer_enrollments_v2.enrollment_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["newcomer_activity_attempts_v2.attempt_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_revision_id"],
            ["coach_profile_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["active_task_id"], ["durable_tasks.task_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("attempt_id", name="uq_coach_sessions_attempt_id"),
    )
    op.create_index(
        "ix_coach_sessions_organization_id",
        "coach_sessions",
        ["organization_id"],
    )
    op.create_index("ix_coach_sessions_learner_id", "coach_sessions", ["learner_id"])
    op.create_index(
        "ix_coach_sessions_enrollment_id", "coach_sessions", ["enrollment_id"]
    )
    op.create_index(
        "ix_coach_sessions_active_task_id", "coach_sessions", ["active_task_id"]
    )
    op.create_index(
        "ix_coach_session_help_queue",
        "coach_sessions",
        ["organization_id", "status", "updated_at"],
    )


def _create_cycle_card_and_response_tables() -> None:
    op.create_table(
        "coach_remediation_cycles",
        sa.Column("cycle_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("checkpoint_index", sa.Integer(), nullable=False),
        sa.Column("checkpoint_key", sa.String(120), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("input_evidence_json", JSON_DOCUMENT, nullable=False),
        sa.Column("remediation_inputs_json", JSON_DOCUMENT, nullable=False),
        sa.Column("generation_strategy", sa.Text(), nullable=True),
        sa.Column("generation_task_id", sa.String(36), nullable=True),
        sa.Column("generation_invocation_id", sa.String(160), nullable=True),
        sa.Column("score_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("maximum_uncertainty", sa.Numeric(6, 5), nullable=True),
        sa.Column("result_summary_json", JSON_DOCUMENT, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "checkpoint_index BETWEEN 0 AND 2", name="ck_coach_cycle_checkpoint"
        ),
        sa.CheckConstraint("cycle_no BETWEEN 0 AND 2", name="ck_coach_cycle_number"),
        sa.CheckConstraint(
            "status IN ('generating','active','completed','mastered',"
            "'remediation_needed','failed','needs_human_help','cancelled')",
            name="ck_coach_cycle_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["generation_task_id"],
            ["durable_tasks.task_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("cycle_id"),
        sa.UniqueConstraint(
            "session_id",
            "checkpoint_index",
            "cycle_no",
            name="uq_coach_cycle_checkpoint_number",
        ),
    )
    op.create_index(
        "ix_coach_remediation_cycles_organization_id",
        "coach_remediation_cycles",
        ["organization_id"],
    )
    op.create_table(
        "coach_turns",
        sa.Column("turn_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("cycle_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("checkpoint_index", sa.Integer(), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("cycle_position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','current','answered','scored','cancelled')",
            name="ck_coach_turn_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cycle_id"],
            ["coach_remediation_cycles.cycle_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("turn_id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_coach_turn_sequence"),
        sa.UniqueConstraint(
            "cycle_id", "cycle_position", name="uq_coach_turn_cycle_position"
        ),
    )
    op.create_index(
        "ix_coach_turns_organization_id", "coach_turns", ["organization_id"]
    )
    op.create_table(
        "coach_training_cards",
        sa.Column("card_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("cycle_id", sa.String(36), nullable=False),
        sa.Column("turn_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("card_type", sa.String(40), nullable=False),
        sa.Column("evaluation_mode", sa.String(24), nullable=False),
        sa.Column("public_payload_json", JSON_DOCUMENT, nullable=False),
        sa.Column("evaluation_spec_json", JSON_DOCUMENT, nullable=False),
        sa.Column("source_ref_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("generation_invocation_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "card_type IN ('single_choice','multiple_choice','ordering',"
            "'short_answer_rewrite','scenario_choice','key_points_completion',"
            "'example_comparison','summary')",
            name="ck_coach_training_card_type",
        ),
        sa.CheckConstraint(
            "evaluation_mode IN ('deterministic','ai')",
            name="ck_coach_training_card_evaluation_mode",
        ),
        sa.CheckConstraint(
            "status IN ('pending','current','answered','scored','cancelled')",
            name="ck_coach_training_card_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cycle_id"],
            ["coach_remediation_cycles.cycle_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"], ["coach_turns.turn_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("card_id"),
        sa.UniqueConstraint("turn_id", name="uq_coach_training_cards_turn_id"),
    )
    op.create_index(
        "ix_coach_training_cards_organization_id",
        "coach_training_cards",
        ["organization_id"],
    )
    op.create_table(
        "coach_card_responses",
        sa.Column("response_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("card_id", sa.String(36), nullable=False),
        sa.Column("turn_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("raw_answer_json", JSON_DOCUMENT, nullable=False),
        sa.Column("client_token_hash", sa.String(64), nullable=False),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evaluation_task_id", sa.String(36), nullable=True),
        sa.Column("score_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("mastered", sa.Boolean(), nullable=True),
        sa.Column("evaluation_json", JSON_DOCUMENT, nullable=True),
        sa.Column("uncertainty", sa.Numeric(6, 5), nullable=True),
        sa.Column("source_ref_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("evaluation_kind", sa.String(24), nullable=True),
        sa.Column("invocation_id", sa.String(160), nullable=True),
        sa.Column("prompt_template_id", sa.String(160), nullable=True),
        sa.Column("prompt_revision_id", sa.String(160), nullable=True),
        sa.Column("prompt_contract_hash", sa.String(80), nullable=True),
        sa.Column("model_routing_profile_id", sa.String(160), nullable=True),
        sa.Column("model_routing_revision_id", sa.String(160), nullable=True),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("safe_error_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('saved','evaluating','evaluated','failed_recoverable','cancelled')",
            name="ck_coach_response_status",
        ),
        sa.CheckConstraint(
            "evaluation_kind IS NULL OR evaluation_kind IN ('deterministic','ai')",
            name="ck_coach_response_evaluation_kind",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["coach_training_cards.card_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["turn_id"], ["coach_turns.turn_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_task_id"],
            ["durable_tasks.task_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("response_id"),
        sa.UniqueConstraint("card_id", name="uq_coach_card_responses_card_id"),
        sa.UniqueConstraint(
            "session_id",
            "client_token_hash",
            name="uq_coach_response_client_token",
        ),
    )
    op.create_index(
        "ix_coach_card_responses_organization_id",
        "coach_card_responses",
        ["organization_id"],
    )
    op.create_index(
        "ix_coach_card_responses_learner_id",
        "coach_card_responses",
        ["learner_id"],
    )


def _create_assistance_outcome_and_governance_tables() -> None:
    op.create_table(
        "coach_assistances",
        sa.Column("assistance_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("card_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("assistance_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("result_json", JSON_DOCUMENT, nullable=True),
        sa.Column("source_ref_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("invocation_id", sa.String(160), nullable=True),
        sa.Column("prompt_revision_id", sa.String(160), nullable=True),
        sa.Column("model_routing_revision_id", sa.String(160), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "assistance_type IN ('explain','example')",
            name="ck_coach_assistance_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued','completed','failed_recoverable','cancelled')",
            name="ck_coach_assistance_status",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["coach_training_cards.card_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["durable_tasks.task_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("assistance_id"),
        sa.UniqueConstraint(
            "session_id",
            "idempotency_key_hash",
            name="uq_coach_assistance_idempotency",
        ),
    )
    op.create_index(
        "ix_coach_assistances_organization_id",
        "coach_assistances",
        ["organization_id"],
    )
    op.create_table(
        "coach_outcomes",
        sa.Column("outcome_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("profile_revision_id", sa.String(36), nullable=False),
        sa.Column("mastery_score_percent", sa.Numeric(6, 3), nullable=False),
        sa.Column("checkpoint_results_json", JSON_DOCUMENT, nullable=False),
        sa.Column("cycle_history_json", JSON_DOCUMENT, nullable=False),
        sa.Column("source_refs_json", JSON_DOCUMENT, nullable=False),
        sa.Column("lineage_json", JSON_DOCUMENT, nullable=False),
        sa.Column("generic_activity_outcome_id", sa.String(36), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("outcome_id"),
        sa.UniqueConstraint("session_id", name="uq_coach_outcomes_session_id"),
    )
    op.create_index(
        "ix_coach_outcomes_organization_id", "coach_outcomes", ["organization_id"]
    )
    op.create_index("ix_coach_outcomes_learner_id", "coach_outcomes", ["learner_id"])
    op.create_table(
        "coach_human_interventions",
        sa.Column("intervention_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(120), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("target_resource_id", sa.String(160), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("trace_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('add_guidance','assign_learning','assign_audio',"
            "'restart_coach','no_further_action')",
            name="ck_coach_human_intervention_action",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["coach_sessions.session_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("intervention_id"),
        sa.UniqueConstraint(
            "session_id",
            "idempotency_key_hash",
            name="uq_coach_human_intervention_idempotency",
        ),
    )
    op.create_index(
        "ix_coach_human_interventions_organization_id",
        "coach_human_interventions",
        ["organization_id"],
    )
    op.create_table(
        "coach_command_audits",
        sa.Column("audit_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(120), nullable=False),
        sa.Column("object_type", sa.String(120), nullable=False),
        sa.Column("object_id", sa.String(160), nullable=False),
        sa.Column("command", sa.String(120), nullable=False),
        sa.Column("before_version", sa.Integer(), nullable=True),
        sa.Column("after_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(160), nullable=True),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("details_json", JSON_DOCUMENT, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_coach_command_audits_organization_id",
        "coach_command_audits",
        ["organization_id"],
    )
    op.create_index(
        "ix_coach_command_audits_command",
        "coach_command_audits",
        ["command"],
    )


def downgrade() -> None:
    op.drop_index("ix_coach_command_audits_command", table_name="coach_command_audits")
    op.drop_index(
        "ix_coach_command_audits_organization_id",
        table_name="coach_command_audits",
    )
    op.drop_table("coach_command_audits")
    op.drop_index(
        "ix_coach_human_interventions_organization_id",
        table_name="coach_human_interventions",
    )
    op.drop_table("coach_human_interventions")
    op.drop_index("ix_coach_outcomes_learner_id", table_name="coach_outcomes")
    op.drop_index("ix_coach_outcomes_organization_id", table_name="coach_outcomes")
    op.drop_table("coach_outcomes")
    op.drop_index(
        "ix_coach_assistances_organization_id", table_name="coach_assistances"
    )
    op.drop_table("coach_assistances")
    op.drop_index(
        "ix_coach_card_responses_learner_id", table_name="coach_card_responses"
    )
    op.drop_index(
        "ix_coach_card_responses_organization_id",
        table_name="coach_card_responses",
    )
    op.drop_table("coach_card_responses")
    op.drop_index(
        "ix_coach_training_cards_organization_id",
        table_name="coach_training_cards",
    )
    op.drop_table("coach_training_cards")
    op.drop_index("ix_coach_turns_organization_id", table_name="coach_turns")
    op.drop_table("coach_turns")
    op.drop_index(
        "ix_coach_remediation_cycles_organization_id",
        table_name="coach_remediation_cycles",
    )
    op.drop_table("coach_remediation_cycles")
    op.drop_index("ix_coach_session_help_queue", table_name="coach_sessions")
    op.drop_index("ix_coach_sessions_active_task_id", table_name="coach_sessions")
    op.drop_index("ix_coach_sessions_enrollment_id", table_name="coach_sessions")
    op.drop_index("ix_coach_sessions_learner_id", table_name="coach_sessions")
    op.drop_index("ix_coach_sessions_organization_id", table_name="coach_sessions")
    op.drop_table("coach_sessions")
    op.drop_index(
        "ix_coach_profile_revisions_organization_id",
        table_name="coach_profile_revisions",
    )
    op.drop_table("coach_profile_revisions")
