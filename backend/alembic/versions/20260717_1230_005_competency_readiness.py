"""canonical competency evidence and readiness review

Revision ID: 20260717_1230_005
Revises: 20260717_0930_004
Create Date: 2026-07-17 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_1230_005"
down_revision: str | None = "20260717_0930_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    _create_competency_tables()
    _create_readiness_core_tables()
    _create_readiness_follow_up_tables()


def _create_competency_tables() -> None:
    op.create_table(
        "canonical_competencies",
        sa.Column("competency_id", sa.String(36), nullable=False),
        sa.Column("stable_key", sa.String(80), nullable=False),
        sa.Column("standard_order", sa.Integer(), nullable=False),
        sa.Column("is_standard", sa.Boolean(), nullable=False),
        sa.Column("active_revision_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("competency_id"),
        sa.UniqueConstraint("stable_key"),
    )
    op.create_table(
        "canonical_competency_revisions",
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("competency_id", sa.String(36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("observable_behaviors_json", JSON_DOCUMENT, nullable=False),
        sa.Column("evidence_types_json", JSON_DOCUMENT, nullable=False),
        sa.Column("evidence_roles_json", JSON_DOCUMENT, nullable=False),
        sa.Column("minimum_requirements_json", JSON_DOCUMENT, nullable=False),
        sa.Column("applicable_scope_json", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('published','archived')",
            name="ck_competency_revision_status",
        ),
        sa.ForeignKeyConstraint(
            ["competency_id"],
            ["canonical_competencies.competency_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint(
            "competency_id",
            "revision_no",
            name="uq_competency_revision_number",
        ),
    )
    op.create_table(
        "competency_mappings",
        sa.Column("mapping_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(48), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("source_revision_id", sa.String(200), nullable=False),
        sa.Column("competency_revision_id", sa.String(36), nullable=False),
        sa.Column("competency_key", sa.String(80), nullable=False),
        sa.Column("weight", sa.Numeric(8, 6), nullable=False),
        sa.Column("evidence_role", sa.String(32), nullable=False),
        sa.Column("mapping_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('published','superseded','archived')",
            name="ck_competency_mapping_status",
        ),
        sa.CheckConstraint(
            "weight > 0 AND weight <= 1",
            name="ck_competency_mapping_weight",
        ),
        sa.ForeignKeyConstraint(
            ["competency_revision_id"],
            ["canonical_competency_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("mapping_id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_type",
            "source_revision_id",
            "competency_revision_id",
            "mapping_revision",
            name="uq_competency_mapping_revision",
        ),
    )
    op.create_index(
        "ix_competency_mappings_organization_id",
        "competency_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_competency_mapping_source",
        "competency_mappings",
        ["organization_id", "source_type", "source_revision_id"],
    )
    op.create_table(
        "competency_evidence_records",
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(120), nullable=False),
        sa.Column("enrollment_id", sa.String(36), nullable=False),
        sa.Column("competency_revision_id", sa.String(36), nullable=False),
        sa.Column("competency_key", sa.String(80), nullable=False),
        sa.Column("source_activity_id", sa.String(160), nullable=False),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("outcome_id", sa.String(36), nullable=False),
        sa.Column("outcome_version", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(48), nullable=False),
        sa.Column("evidence_role", sa.String(32), nullable=False),
        sa.Column("observed_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("observed_max_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("observed_result", sa.String(40), nullable=True),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=True),
        sa.Column("quality", sa.String(32), nullable=False),
        sa.Column("initial_validity", sa.String(32), nullable=False),
        sa.Column("source_refs_json", JSON_DOCUMENT, nullable=False),
        sa.Column("lineage_json", JSON_DOCUMENT, nullable=False),
        sa.Column("critical_flags_json", JSON_DOCUMENT, nullable=False),
        sa.Column("degradations_json", JSON_DOCUMENT, nullable=False),
        sa.Column("supersedes_evidence_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "initial_validity IN ('valid','pending_review','insufficient_quality','invalidated')",
            name="ck_competency_evidence_initial_validity",
        ),
        sa.CheckConstraint(
            "quality IN ('verified','degraded','unscorable','invalid')",
            name="ck_competency_evidence_quality",
        ),
        sa.ForeignKeyConstraint(
            ["competency_revision_id"],
            ["canonical_competency_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_evidence_id"],
            ["competency_evidence_records.evidence_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint(
            "organization_id",
            "outcome_id",
            "outcome_version",
            "competency_revision_id",
            name="uq_competency_evidence_outcome_revision",
        ),
    )
    for column in ("organization_id", "learner_id", "enrollment_id"):
        op.create_index(
            f"ix_competency_evidence_records_{column}",
            "competency_evidence_records",
            [column],
        )
    op.create_index(
        "ix_competency_evidence_enrollment_key_time",
        "competency_evidence_records",
        ["organization_id", "enrollment_id", "competency_key", "observed_at"],
    )
    op.create_table(
        "competency_evidence_validity_events",
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("replacement_evidence_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('invalidated','restored')",
            name="ck_competency_evidence_validity_event_status",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["competency_evidence_records.evidence_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint(
            "organization_id",
            "evidence_id",
            "idempotency_key_hash",
            name="uq_competency_evidence_validity_command",
        ),
    )
    op.create_index(
        "ix_competency_evidence_validity_events_organization_id",
        "competency_evidence_validity_events",
        ["organization_id"],
    )


def _create_readiness_core_tables() -> None:
    op.create_table(
        "readiness_policy_revisions",
        sa.Column("policy_revision_id", sa.String(36), nullable=False),
        sa.Column("stable_key", sa.String(120), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("snapshot_json", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('published','archived')",
            name="ck_readiness_policy_status",
        ),
        sa.PrimaryKeyConstraint("policy_revision_id"),
        sa.UniqueConstraint(
            "stable_key", "revision_no", name="uq_readiness_policy_revision"
        ),
    )
    op.create_table(
        "readiness_dossiers",
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("enrollment_id", sa.String(36), nullable=False),
        sa.Column("learner_id", sa.String(120), nullable=False),
        sa.Column("path_revision_id", sa.String(160), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=True),
        sa.Column("pending_evidence_set_hash", sa.String(64), nullable=True),
        sa.Column("current_snapshot_id", sa.String(36), nullable=True),
        sa.Column("active_decision_id", sa.String(36), nullable=True),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('projecting','incomplete','ready_for_review','under_review',"
            "'decided','stale','projection_failed')",
            name="ck_readiness_dossier_state",
        ),
        sa.PrimaryKeyConstraint("dossier_id"),
        sa.UniqueConstraint(
            "organization_id",
            "enrollment_id",
            name="uq_readiness_dossier_enrollment",
        ),
    )
    op.create_index(
        "ix_readiness_dossiers_organization_id",
        "readiness_dossiers",
        ["organization_id"],
    )
    op.create_index(
        "ix_readiness_dossiers_learner_id",
        "readiness_dossiers",
        ["learner_id"],
    )
    op.create_index(
        "ix_readiness_dossier_queue",
        "readiness_dossiers",
        ["organization_id", "state", "updated_at"],
    )
    op.create_table(
        "readiness_dossier_snapshots",
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("evidence_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("competency_revision_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("readiness_policy_revision_id", sa.String(36), nullable=False),
        sa.Column("path_revision_id", sa.String(160), nullable=False),
        sa.Column("projection_json", JSON_DOCUMENT, nullable=False),
        sa.Column("ai_summary_revision_id", sa.String(36), nullable=True),
        sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dossier_id"],
            ["readiness_dossiers.dossier_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["readiness_policy_revision_id"],
            ["readiness_policy_revisions.policy_revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "dossier_id",
            "snapshot_version",
            name="uq_dossier_snapshot_version",
        ),
    )
    op.create_index(
        "ix_readiness_dossier_snapshots_organization_id",
        "readiness_dossier_snapshots",
        ["organization_id"],
    )
    op.create_index(
        "ix_dossier_snapshot_current",
        "readiness_dossier_snapshots",
        ["organization_id", "dossier_id", "created_at"],
    )
    op.create_table(
        "readiness_review_decisions",
        sa.Column("decision_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("dossier_version", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reviewer_id", sa.String(120), nullable=False),
        sa.Column("competency_keys_json", JSON_DOCUMENT, nullable=False),
        sa.Column("evidence_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("supersedes_decision_id", sa.String(36), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('recorded','superseded','voided')",
            name="ck_readiness_decision_status",
        ),
        sa.CheckConstraint(
            "decision_type IN ('approve_foundation_ready','request_retraining',"
            "'request_more_evidence','reject_due_to_integrity_issue',"
            "'close_without_decision','exception_approved')",
            name="ck_readiness_decision_type",
        ),
        sa.ForeignKeyConstraint(
            ["dossier_id"],
            ["readiness_dossiers.dossier_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["readiness_dossier_snapshots.snapshot_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "organization_id",
            "dossier_id",
            "idempotency_key_hash",
            name="uq_readiness_decision_command",
        ),
    )
    op.create_index(
        "ix_readiness_review_decisions_organization_id",
        "readiness_review_decisions",
        ["organization_id"],
    )
    op.create_table(
        "readiness_exception_previews",
        sa.Column("preview_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("dossier_version", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.String(120), nullable=False),
        sa.Column("impact_json", JSON_DOCUMENT, nullable=False),
        sa.Column("impact_hash", sa.String(64), nullable=False),
        sa.Column("preview_token_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('previewed','consumed','expired')",
            name="ck_readiness_exception_preview_status",
        ),
        sa.ForeignKeyConstraint(
            ["dossier_id"],
            ["readiness_dossiers.dossier_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["readiness_dossier_snapshots.snapshot_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("preview_id"),
        sa.UniqueConstraint("preview_token_hash"),
        sa.UniqueConstraint(
            "organization_id",
            "dossier_id",
            "idempotency_key_hash",
            name="uq_readiness_exception_preview_command",
        ),
    )
    op.create_index(
        "ix_readiness_exception_previews_organization_id",
        "readiness_exception_previews",
        ["organization_id"],
    )
    op.create_index(
        "ix_readiness_exception_preview_active",
        "readiness_exception_previews",
        ["organization_id", "dossier_id", "status", "expires_at"],
    )


def _create_readiness_follow_up_tables() -> None:
    op.create_table(
        "readiness_retraining_assignments",
        sa.Column("assignment_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("enrollment_id", sa.String(36), nullable=False),
        sa.Column("learner_id", sa.String(120), nullable=False),
        sa.Column("source_snapshot_id", sa.String(36), nullable=False),
        sa.Column("activity_source", sa.String(32), nullable=False),
        sa.Column("activity_id", sa.String(160), nullable=True),
        sa.Column("activity_title", sa.String(200), nullable=False),
        sa.Column("activity_draft_json", JSON_DOCUMENT, nullable=True),
        sa.Column("target_competency_keys_json", JSON_DOCUMENT, nullable=False),
        sa.Column("source_evidence_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_rule_json", JSON_DOCUMENT, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("completed_outcome_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "activity_source IN ('existing_published','quick_draft')",
            name="ck_retraining_activity_source",
        ),
        sa.CheckConstraint(
            "status IN ('assigned','draft_pending_governance','completed','cancelled')",
            name="ck_retraining_assignment_status",
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint(
            "organization_id",
            "dossier_id",
            "idempotency_key_hash",
            name="uq_retraining_assignment_command",
        ),
    )
    for column in ("organization_id", "learner_id"):
        op.create_index(
            f"ix_readiness_retraining_assignments_{column}",
            "readiness_retraining_assignments",
            [column],
        )
    op.create_table(
        "readiness_appeals",
        sa.Column("appeal_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("learner_id", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(24), nullable=False),
        sa.Column("target_id", sa.String(160), nullable=False),
        sa.Column("dossier_version", sa.Integer(), nullable=False),
        sa.Column("reason_category", sa.String(32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_to", sa.String(120), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "target_type IN ('evidence','decision','transcript','score')",
            name="ck_readiness_appeal_target",
        ),
        sa.CheckConstraint(
            "status IN ('submitted','under_review','regrade_pending','resolved','rejected')",
            name="ck_readiness_appeal_status",
        ),
        sa.PrimaryKeyConstraint("appeal_id"),
        sa.UniqueConstraint(
            "organization_id",
            "learner_id",
            "idempotency_key_hash",
            name="uq_readiness_appeal_command",
        ),
    )
    for column in ("organization_id", "learner_id"):
        op.create_index(
            f"ix_readiness_appeals_{column}",
            "readiness_appeals",
            [column],
        )
    op.create_table(
        "readiness_calibration_sessions",
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("competency_key", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("sample_evidence_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("decision_distribution_json", JSON_DOCUMENT, nullable=False),
        sa.Column("disagreements_json", JSON_DOCUMENT, nullable=False),
        sa.Column("action_items_json", JSON_DOCUMENT, nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open','closed')", name="ck_readiness_calibration_status"
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        "ix_readiness_calibration_sessions_organization_id",
        "readiness_calibration_sessions",
        ["organization_id"],
    )
    op.create_table(
        "readiness_ai_summaries",
        sa.Column("summary_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload_json", JSON_DOCUMENT, nullable=True),
        sa.Column("evidence_ids_json", JSON_DOCUMENT, nullable=False),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready','rejected','failed')",
            name="ck_readiness_ai_summary_status",
        ),
        sa.PrimaryKeyConstraint("summary_id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "revision_no",
            name="uq_readiness_ai_summary_revision",
        ),
    )
    op.create_index(
        "ix_readiness_ai_summaries_organization_id",
        "readiness_ai_summaries",
        ["organization_id"],
    )
    op.create_table(
        "readiness_command_audits",
        sa.Column("audit_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(120), nullable=False),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("object_id", sa.String(160), nullable=False),
        sa.Column("command", sa.String(120), nullable=False),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_version", sa.Integer(), nullable=True),
        sa.Column("after_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=True),
        sa.Column("details_json", JSON_DOCUMENT, nullable=False),
        sa.Column("trace_id", sa.String(160), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_readiness_command_audits_organization_id",
        "readiness_command_audits",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_readiness_exception_preview_active",
        table_name="readiness_exception_previews",
    )
    op.drop_index(
        "ix_readiness_exception_previews_organization_id",
        table_name="readiness_exception_previews",
    )
    op.drop_table("readiness_exception_previews")
    op.drop_index(
        "ix_readiness_command_audits_organization_id",
        table_name="readiness_command_audits",
    )
    op.drop_table("readiness_command_audits")
    op.drop_index(
        "ix_readiness_ai_summaries_organization_id",
        table_name="readiness_ai_summaries",
    )
    op.drop_table("readiness_ai_summaries")
    op.drop_index(
        "ix_readiness_calibration_sessions_organization_id",
        table_name="readiness_calibration_sessions",
    )
    op.drop_table("readiness_calibration_sessions")
    for column in ("learner_id", "organization_id"):
        op.drop_index(
            f"ix_readiness_appeals_{column}", table_name="readiness_appeals"
        )
    op.drop_table("readiness_appeals")
    for column in ("learner_id", "organization_id"):
        op.drop_index(
            f"ix_readiness_retraining_assignments_{column}",
            table_name="readiness_retraining_assignments",
        )
    op.drop_table("readiness_retraining_assignments")
    op.drop_index(
        "ix_readiness_review_decisions_organization_id",
        table_name="readiness_review_decisions",
    )
    op.drop_table("readiness_review_decisions")
    op.drop_index(
        "ix_dossier_snapshot_current", table_name="readiness_dossier_snapshots"
    )
    op.drop_index(
        "ix_readiness_dossier_snapshots_organization_id",
        table_name="readiness_dossier_snapshots",
    )
    op.drop_table("readiness_dossier_snapshots")
    op.drop_index("ix_readiness_dossier_queue", table_name="readiness_dossiers")
    op.drop_index(
        "ix_readiness_dossiers_learner_id", table_name="readiness_dossiers"
    )
    op.drop_index(
        "ix_readiness_dossiers_organization_id", table_name="readiness_dossiers"
    )
    op.drop_table("readiness_dossiers")
    op.drop_table("readiness_policy_revisions")
    op.drop_index(
        "ix_competency_evidence_validity_events_organization_id",
        table_name="competency_evidence_validity_events",
    )
    op.drop_table("competency_evidence_validity_events")
    op.drop_index(
        "ix_competency_evidence_enrollment_key_time",
        table_name="competency_evidence_records",
    )
    for column in ("enrollment_id", "learner_id", "organization_id"):
        op.drop_index(
            f"ix_competency_evidence_records_{column}",
            table_name="competency_evidence_records",
        )
    op.drop_table("competency_evidence_records")
    op.drop_index(
        "ix_competency_mapping_source", table_name="competency_mappings"
    )
    op.drop_index(
        "ix_competency_mappings_organization_id",
        table_name="competency_mappings",
    )
    op.drop_table("competency_mappings")
    op.drop_table("canonical_competency_revisions")
    op.drop_table("canonical_competencies")
