"""audio assessment durable pipeline

Revision ID: 20260717_0600_003
Revises: b9fc04c1ad65
Create Date: 2026-07-17 06:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_0600_003"
down_revision: str | None = "b9fc04c1ad65"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    _upgrade_outcome_versions()
    op.create_table(
        "audio_activity_resource_revisions",
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(40), nullable=False),
        sa.Column("stable_key", sa.String(160), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("snapshot_json", JSON_DOCUMENT, nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "resource_type IN ('audio_material','scoring_scheme','scenario')",
            name="ck_audio_resource_revision_type",
        ),
        sa.CheckConstraint(
            "status IN ('working','published','archived')",
            name="ck_audio_resource_revision_status",
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint(
            "organization_id",
            "resource_type",
            "stable_key",
            "revision_no",
            name="uq_audio_resource_revision_number",
        ),
    )
    op.create_index(
        "ix_audio_activity_resource_revisions_organization_id",
        "audio_activity_resource_revisions",
        ["organization_id"],
    )
    op.create_index(
        "ix_audio_activity_resource_revisions_resource_type",
        "audio_activity_resource_revisions",
        ["resource_type"],
    )
    op.create_table(
        "audio_activity_runs",
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("enrollment_id", sa.String(36), nullable=False),
        sa.Column("path_revision_id", sa.String(36), nullable=False),
        sa.Column("activity_id", sa.String(160), nullable=False),
        sa.Column("activity_type", sa.String(32), nullable=False),
        sa.Column("attempt_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config_snapshot_json", JSON_DOCUMENT, nullable=False),
        sa.Column("competency_keys_json", JSON_DOCUMENT, nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "activity_type IN ('audio_assessment','assignment')",
            name="ck_audio_activity_run_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','in_progress','processing','needs_review',"
            "'completed','failed','cancelled','invalidated')",
            name="ck_audio_activity_run_status",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["users.user_id"],
            ondelete="RESTRICT",
        ),
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
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("attempt_id", name="uq_audio_activity_run_attempt"),
    )
    op.create_index(
        "ix_audio_activity_runs_organization_id",
        "audio_activity_runs",
        ["organization_id"],
    )
    op.create_index(
        "ix_audio_activity_runs_scope",
        "audio_activity_runs",
        ["organization_id", "learner_id", "activity_id"],
    )
    op.create_table(
        "audio_submissions_v2",
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("segment_id", sa.String(40), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("original_artifact_id", sa.String(36), nullable=True),
        sa.Column("normalized_artifact_id", sa.String(36), nullable=True),
        sa.Column("current_transcript_revision_id", sa.String(36), nullable=True),
        sa.Column("current_score_outcome_version_id", sa.String(36), nullable=True),
        sa.Column("failed_stage", sa.String(40), nullable=True),
        sa.Column("error_classification", sa.String(80), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=True),
        sa.Column("safe_error_message", sa.Text(), nullable=True),
        sa.Column("processing_generation", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('draft','uploading','uploaded','validating','normalizing',"
            "'transcribing','transcript_ready','scoring','reconciling','completed',"
            "'partially_completed','failed_recoverable','failed_terminal',"
            "'needs_review','cancelled','invalidated','expired')",
            name="ck_audio_submission_v2_state",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["audio_activity_runs.run_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["durable_tasks.task_id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("submission_id"),
        sa.UniqueConstraint(
            "run_id",
            "segment_id",
            name="uq_audio_submission_run_segment",
        ),
    )
    op.create_index(
        "ix_audio_submissions_v2_organization_id",
        "audio_submissions_v2",
        ["organization_id"],
    )
    op.create_index(
        "ix_audio_submissions_v2_learner_id",
        "audio_submissions_v2",
        ["learner_id"],
    )
    op.create_index(
        "ix_audio_submissions_v2_state",
        "audio_submissions_v2",
        ["state"],
    )
    op.create_index(
        "ix_audio_submissions_v2_run_state",
        "audio_submissions_v2",
        ["run_id", "state"],
    )
    _create_upload_tables()
    _create_artifact_tables()
    _create_governance_tables()


def _create_upload_tables() -> None:
    op.create_table(
        "audio_upload_sessions",
        sa.Column("upload_session_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("declared_size_bytes", sa.Integer(), nullable=False),
        sa.Column("declared_duration_seconds", sa.Numeric(10, 3), nullable=False),
        sa.Column("declared_manifest_sha256", sa.String(64), nullable=False),
        sa.Column("part_size_bytes", sa.Integer(), nullable=False),
        sa.Column("expected_part_count", sa.Integer(), nullable=False),
        sa.Column("storage_backend", sa.String(24), nullable=False),
        sa.Column("object_prefix", sa.String(500), nullable=False),
        sa.Column("upload_token_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_claim_token", sa.String(36), nullable=True),
        sa.Column("cleanup_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "state IN ('uploading','finalized','cancelled','expired')",
            name="ck_audio_upload_session_state",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["audio_submissions_v2.submission_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("upload_session_id"),
        sa.UniqueConstraint(
            "submission_id",
            "idempotency_key_hash",
            name="uq_audio_upload_session_command",
        ),
    )
    op.create_index(
        "ix_audio_upload_sessions_organization_id",
        "audio_upload_sessions",
        ["organization_id"],
    )
    op.create_index(
        "ix_audio_upload_sessions_expires_at",
        "audio_upload_sessions",
        ["expires_at"],
    )
    op.create_index(
        "ix_audio_upload_sessions_cleanup",
        "audio_upload_sessions",
        ["state", "cleanup_completed_at", "expires_at"],
    )
    op.create_table(
        "audio_upload_parts",
        sa.Column("part_id", sa.String(36), nullable=False),
        sa.Column("upload_session_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("declared_size_bytes", sa.Integer(), nullable=False),
        sa.Column("declared_sha256", sa.String(64), nullable=False),
        sa.Column("actual_size_bytes", sa.Integer(), nullable=True),
        sa.Column("actual_sha256", sa.String(64), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "part_number >= 1",
            name="ck_audio_upload_part_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["upload_session_id"],
            ["audio_upload_sessions.upload_session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("part_id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint(
            "upload_session_id",
            "part_number",
            name="uq_audio_upload_part_number",
        ),
    )
    op.create_index(
        "ix_audio_upload_parts_organization_id",
        "audio_upload_parts",
        ["organization_id"],
    )


def _create_artifact_tables() -> None:
    op.create_table(
        "audio_artifacts",
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("artifact_ref", sa.String(1000), nullable=False),
        sa.Column("storage_backend", sa.String(24), nullable=False),
        sa.Column("manifest_json", JSON_DOCUMENT, nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(10, 3), nullable=False),
        sa.Column("sample_rate_hz", sa.Integer(), nullable=True),
        sa.Column("channels", sa.Integer(), nullable=True),
        sa.Column("tool_version", sa.String(160), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('original','normalized')",
            name="ck_audio_artifact_kind",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["audio_submissions_v2.submission_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.UniqueConstraint("artifact_ref"),
        sa.UniqueConstraint(
            "submission_id",
            "kind",
            name="uq_audio_artifact_submission_kind",
        ),
    )
    op.create_index(
        "ix_audio_artifacts_organization_id",
        "audio_artifacts",
        ["organization_id"],
    )
    op.create_table(
        "audio_transcript_revisions",
        sa.Column("revision_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("artifact_id", sa.String(36), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("segments_json", JSON_DOCUMENT, nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("provider_summary_json", JSON_DOCUMENT, nullable=False),
        sa.Column("ai_invocation_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("supersedes_revision_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('automatic','manual_correction','retranscription',"
            "'legacy_conversion')",
            name="ck_audio_transcript_revision_source",
        ),
        sa.CheckConstraint(
            "status IN ('valid','invalidated')",
            name="ck_audio_transcript_revision_status",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["audio_submissions_v2.submission_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["audio_artifacts.artifact_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("revision_id"),
        sa.UniqueConstraint(
            "submission_id",
            "revision_no",
            name="uq_audio_transcript_revision_number",
        ),
    )
    op.create_index(
        "ix_audio_transcript_revisions_organization_id",
        "audio_transcript_revisions",
        ["organization_id"],
    )
    op.create_table(
        "audio_quality_reports",
        sa.Column("report_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("transcript_revision_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("metrics_json", JSON_DOCUMENT, nullable=False),
        sa.Column("quality_flags_json", JSON_DOCUMENT, nullable=False),
        sa.Column("scorable", sa.Boolean(), nullable=False),
        sa.Column("algorithm_version", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["audio_submissions_v2.submission_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transcript_revision_id"],
            ["audio_transcript_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id"),
        sa.UniqueConstraint("transcript_revision_id"),
    )
    op.create_index(
        "ix_audio_quality_reports_organization_id",
        "audio_quality_reports",
        ["organization_id"],
    )
    op.create_table(
        "audio_score_outcome_versions",
        sa.Column("outcome_version_id", sa.String(36), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("transcript_revision_id", sa.String(36), nullable=False),
        sa.Column("scoring_scheme_revision_id", sa.String(160), nullable=False),
        sa.Column("prompt_revision_id", sa.String(160), nullable=False),
        sa.Column("prompt_contract_hash", sa.String(80), nullable=False),
        sa.Column("model_routing_revision_id", sa.String(160), nullable=False),
        sa.Column("ai_invocation_id", sa.String(36), nullable=False),
        sa.Column("dimension_scores_json", JSON_DOCUMENT, nullable=False),
        sa.Column("evidence_spans_json", JSON_DOCUMENT, nullable=False),
        sa.Column("missing_points_json", JSON_DOCUMENT, nullable=False),
        sa.Column("feedback_json", JSON_DOCUMENT, nullable=False),
        sa.Column("remediation_json", JSON_DOCUMENT, nullable=False),
        sa.Column("critical_flags_json", JSON_DOCUMENT, nullable=False),
        sa.Column("deterministic_metrics_json", JSON_DOCUMENT, nullable=False),
        sa.Column("total_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("uncertainty", sa.Numeric(6, 5), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("supersedes_outcome_version_id", sa.String(36), nullable=True),
        sa.Column("review_trace_json", JSON_DOCUMENT, nullable=False),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('valid','invalidated')",
            name="ck_audio_score_outcome_version_status",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["audio_submissions_v2.submission_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transcript_revision_id"],
            ["audio_transcript_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("outcome_version_id"),
        sa.UniqueConstraint(
            "submission_id",
            "version_no",
            name="uq_audio_score_outcome_version_number",
        ),
    )
    op.create_index(
        "ix_audio_score_outcome_versions_organization_id",
        "audio_score_outcome_versions",
        ["organization_id"],
    )


def _create_governance_tables() -> None:
    op.create_table(
        "audio_command_audits",
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
        sa.Column("expected_version", sa.Integer(), nullable=True),
        sa.Column("actual_version", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("preview_token_hash", sa.String(64), nullable=True),
        sa.Column("impact_hash", sa.String(64), nullable=True),
        sa.Column("trace_id", sa.String(160), nullable=True),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("details_json", JSON_DOCUMENT, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_audio_command_audits_organization_id",
        "audio_command_audits",
        ["organization_id"],
    )
    op.create_index(
        "ix_audio_command_audits_actor_id",
        "audio_command_audits",
        ["actor_id"],
    )
    op.create_index(
        "ix_audio_command_audits_command",
        "audio_command_audits",
        ["command"],
    )
    op.create_table(
        "audio_change_previews",
        sa.Column("preview_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("change_type", sa.String(40), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("preview_token_hash", sa.String(64), nullable=False),
        sa.Column("impact_hash", sa.String(64), nullable=False),
        sa.Column("request_json", JSON_DOCUMENT, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "change_type IN ('transcript_correction','regrade','invalidation')",
            name="ck_audio_change_preview_type",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["audio_submissions_v2.submission_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("preview_id"),
        sa.UniqueConstraint("preview_token_hash"),
    )
    op.create_index(
        "ix_audio_change_previews_organization_id",
        "audio_change_previews",
        ["organization_id"],
    )


def _upgrade_outcome_versions() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        naming = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
        with op.batch_alter_table(
            "newcomer_activity_outcomes",
            recreate="always",
            naming_convention=naming,
        ) as batch:
            batch.drop_constraint(
                "uq_newcomer_activity_outcomes_attempt_id",
                type_="unique",
            )
            batch.add_column(
                sa.Column("supersedes_outcome_id", sa.String(36), nullable=True)
            )
            batch.create_foreign_key(
                "fk_newcomer_outcome_supersedes",
                "newcomer_activity_outcomes",
                ["supersedes_outcome_id"],
                ["outcome_id"],
                ondelete="RESTRICT",
            )
            batch.create_unique_constraint(
                "uq_newcomer_activity_outcome_version",
                ["attempt_id", "version"],
            )
            batch.create_unique_constraint(
                "uq_newcomer_activity_outcome_command",
                ["organization_id", "attempt_id", "idempotency_key_hash"],
            )
    else:
        op.drop_constraint(
            "newcomer_activity_outcomes_attempt_id_key",
            "newcomer_activity_outcomes",
            type_="unique",
        )
        op.add_column(
            "newcomer_activity_outcomes",
            sa.Column("supersedes_outcome_id", sa.String(36), nullable=True),
        )
        op.create_foreign_key(
            "fk_newcomer_outcome_supersedes",
            "newcomer_activity_outcomes",
            "newcomer_activity_outcomes",
            ["supersedes_outcome_id"],
            ["outcome_id"],
            ondelete="RESTRICT",
        )
        op.create_unique_constraint(
            "uq_newcomer_activity_outcome_version",
            "newcomer_activity_outcomes",
            ["attempt_id", "version"],
        )
        op.create_unique_constraint(
            "uq_newcomer_activity_outcome_command",
            "newcomer_activity_outcomes",
            ["organization_id", "attempt_id", "idempotency_key_hash"],
        )
    op.create_index(
        "ix_newcomer_activity_outcome_attempt_produced",
        "newcomer_activity_outcomes",
        ["attempt_id", "produced_at"],
    )


def downgrade() -> None:
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT attempt_id FROM newcomer_activity_outcomes "
                "GROUP BY attempt_id HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade audio outcome versioning while multiple versions exist."
        )
    op.drop_index(
        "ix_audio_change_previews_organization_id",
        table_name="audio_change_previews",
    )
    op.drop_table("audio_change_previews")
    op.drop_index(
        "ix_audio_command_audits_command",
        table_name="audio_command_audits",
    )
    op.drop_index(
        "ix_audio_command_audits_actor_id",
        table_name="audio_command_audits",
    )
    op.drop_index(
        "ix_audio_command_audits_organization_id",
        table_name="audio_command_audits",
    )
    op.drop_table("audio_command_audits")
    op.drop_index(
        "ix_audio_score_outcome_versions_organization_id",
        table_name="audio_score_outcome_versions",
    )
    op.drop_table("audio_score_outcome_versions")
    op.drop_index(
        "ix_audio_quality_reports_organization_id",
        table_name="audio_quality_reports",
    )
    op.drop_table("audio_quality_reports")
    op.drop_index(
        "ix_audio_transcript_revisions_organization_id",
        table_name="audio_transcript_revisions",
    )
    op.drop_table("audio_transcript_revisions")
    op.drop_index(
        "ix_audio_artifacts_organization_id",
        table_name="audio_artifacts",
    )
    op.drop_table("audio_artifacts")
    op.drop_index(
        "ix_audio_upload_parts_organization_id",
        table_name="audio_upload_parts",
    )
    op.drop_table("audio_upload_parts")
    op.drop_index(
        "ix_audio_upload_sessions_cleanup",
        table_name="audio_upload_sessions",
    )
    op.drop_index(
        "ix_audio_upload_sessions_expires_at",
        table_name="audio_upload_sessions",
    )
    op.drop_index(
        "ix_audio_upload_sessions_organization_id",
        table_name="audio_upload_sessions",
    )
    op.drop_table("audio_upload_sessions")
    op.drop_index(
        "ix_audio_submissions_v2_run_state",
        table_name="audio_submissions_v2",
    )
    op.drop_index(
        "ix_audio_submissions_v2_state",
        table_name="audio_submissions_v2",
    )
    op.drop_index(
        "ix_audio_submissions_v2_learner_id",
        table_name="audio_submissions_v2",
    )
    op.drop_index(
        "ix_audio_submissions_v2_organization_id",
        table_name="audio_submissions_v2",
    )
    op.drop_table("audio_submissions_v2")
    op.drop_index("ix_audio_activity_runs_scope", table_name="audio_activity_runs")
    op.drop_index(
        "ix_audio_activity_runs_organization_id",
        table_name="audio_activity_runs",
    )
    op.drop_table("audio_activity_runs")
    op.drop_index(
        "ix_audio_activity_resource_revisions_resource_type",
        table_name="audio_activity_resource_revisions",
    )
    op.drop_index(
        "ix_audio_activity_resource_revisions_organization_id",
        table_name="audio_activity_resource_revisions",
    )
    op.drop_table("audio_activity_resource_revisions")
    _downgrade_outcome_versions()


def _downgrade_outcome_versions() -> None:
    op.drop_index(
        "ix_newcomer_activity_outcome_attempt_produced",
        table_name="newcomer_activity_outcomes",
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "newcomer_activity_outcomes",
            recreate="always",
        ) as batch:
            batch.drop_constraint(
                "uq_newcomer_activity_outcome_command",
                type_="unique",
            )
            batch.drop_constraint(
                "uq_newcomer_activity_outcome_version",
                type_="unique",
            )
            batch.drop_constraint(
                "fk_newcomer_outcome_supersedes",
                type_="foreignkey",
            )
            batch.drop_column("supersedes_outcome_id")
            batch.create_unique_constraint(
                "uq_newcomer_activity_outcomes_attempt_id",
                ["attempt_id"],
            )
    else:
        op.drop_constraint(
            "uq_newcomer_activity_outcome_command",
            "newcomer_activity_outcomes",
            type_="unique",
        )
        op.drop_constraint(
            "uq_newcomer_activity_outcome_version",
            "newcomer_activity_outcomes",
            type_="unique",
        )
        op.drop_constraint(
            "fk_newcomer_outcome_supersedes",
            "newcomer_activity_outcomes",
            type_="foreignkey",
        )
        op.drop_column("newcomer_activity_outcomes", "supersedes_outcome_id")
        op.create_unique_constraint(
            "newcomer_activity_outcomes_attempt_id_key",
            "newcomer_activity_outcomes",
            ["attempt_id"],
        )
