"""admin release governance and enrollment import previews

Revision ID: 20260717_1500_006
Revises: 20260717_1230_005
Create Date: 2026-07-17 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_1500_006"
down_revision: str | None = "20260717_1230_005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    with op.batch_alter_table("newcomer_cohorts") as batch_op:
        batch_op.drop_constraint("ck_newcomer_cohorts_status", type_="check")
        batch_op.create_check_constraint(
            "ck_newcomer_cohorts_status",
            "status IN ('active','paused','cancelled','closed','archived')",
        )
    op.create_table(
        "learning_question_candidate_bulk_reviews",
        sa.Column("review_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("command", sa.String(32), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("preview_token_hash", sa.String(64), nullable=False),
        sa.Column("impact_hash", sa.String(64), nullable=False),
        sa.Column("preview_json", JSON_DOCUMENT, nullable=False),
        sa.Column("result_json", JSON_DOCUMENT, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("confirm_idempotency_key_hash", sa.String(64), nullable=True),
        sa.Column("confirm_fingerprint", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "command IN ('approve','reject','supersede')",
            name="ck_learning_candidate_bulk_review_command",
        ),
        sa.CheckConstraint(
            "status IN ('previewed','succeeded','partial','failed','expired')",
            name="ck_learning_candidate_bulk_review_status",
        ),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("preview_token_hash"),
    )
    op.create_index(
        "ix_learning_question_candidate_bulk_reviews_organization_id",
        "learning_question_candidate_bulk_reviews",
        ["organization_id"],
    )
    op.create_index(
        "ix_learning_candidate_bulk_review_org_created",
        "learning_question_candidate_bulk_reviews",
        ["organization_id", "created_at"],
    )
    op.create_table(
        "newcomer_enrollment_imports",
        sa.Column("import_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("cohort_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("preview_token_hash", sa.String(64), nullable=False),
        sa.Column("impact_hash", sa.String(64), nullable=False),
        sa.Column("preview_json", JSON_DOCUMENT, nullable=False),
        sa.Column("result_json", JSON_DOCUMENT, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirm_idempotency_key_hash", sa.String(64), nullable=True),
        sa.Column("confirm_fingerprint", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('previewed','succeeded','partial','failed','expired')",
            name="ck_newcomer_enrollment_imports_status",
        ),
        sa.ForeignKeyConstraint(
            ["cohort_id"],
            ["newcomer_cohorts.cohort_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("import_id"),
        sa.UniqueConstraint("preview_token_hash"),
    )
    op.create_index(
        "ix_newcomer_enrollment_imports_organization_id",
        "newcomer_enrollment_imports",
        ["organization_id"],
    )
    op.create_index(
        "ix_newcomer_enrollment_imports_cohort_id",
        "newcomer_enrollment_imports",
        ["cohort_id"],
    )
    op.create_index(
        "ix_newcomer_enrollment_imports_cohort_created",
        "newcomer_enrollment_imports",
        ["cohort_id", "created_at"],
    )

    op.create_table(
        "newcomer_release_plans",
        sa.Column("release_plan_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column("path_id", sa.String(36), nullable=False),
        sa.Column("path_revision_id", sa.String(36), nullable=False),
        sa.Column("previous_release_plan_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("target_revisions_json", JSON_DOCUMENT, nullable=False),
        sa.Column("dependency_graph_json", JSON_DOCUMENT, nullable=False),
        sa.Column("validation_report_json", JSON_DOCUMENT, nullable=False),
        sa.Column("impact_preview_json", JSON_DOCUMENT, nullable=False),
        sa.Column("impact_hash", sa.String(64), nullable=False),
        sa.Column("preview_token_hash", sa.String(64), nullable=False),
        sa.Column("preview_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("creation_idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("creation_fingerprint", sa.String(64), nullable=False),
        sa.Column("publish_idempotency_key_hash", sa.String(64), nullable=True),
        sa.Column("publish_fingerprint", sa.String(64), nullable=True),
        sa.Column("rollback_preview_token_hash", sa.String(64), nullable=True),
        sa.Column("rollback_impact_hash", sa.String(64), nullable=True),
        sa.Column("rollback_preview_json", JSON_DOCUMENT, nullable=True),
        sa.Column(
            "rollback_preview_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "rollback_confirm_idempotency_key_hash", sa.String(64), nullable=True
        ),
        sa.Column("rollback_confirm_fingerprint", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("published_by", sa.String(120), nullable=True),
        sa.Column("rolled_back_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft','validating','ready','blocked','publishing',"
            "'published','superseded','failed','cancelled')",
            name="ck_newcomer_release_plans_status",
        ),
        sa.ForeignKeyConstraint(
            ["path_id"], ["newcomer_paths.path_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["path_revision_id"],
            ["newcomer_path_revisions.revision_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_release_plan_id"],
            ["newcomer_release_plans.release_plan_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("release_plan_id"),
        sa.UniqueConstraint("preview_token_hash"),
        sa.UniqueConstraint("rollback_preview_token_hash"),
    )
    op.create_index(
        "ix_newcomer_release_plans_organization_id",
        "newcomer_release_plans",
        ["organization_id"],
    )
    op.create_index(
        "ix_newcomer_release_plans_path_id",
        "newcomer_release_plans",
        ["path_id"],
    )
    op.create_index(
        "ix_newcomer_release_plans_path_revision_id",
        "newcomer_release_plans",
        ["path_revision_id"],
    )
    op.create_index(
        "ix_newcomer_release_plans_status",
        "newcomer_release_plans",
        ["status"],
    )
    op.create_index(
        "ix_newcomer_release_plans_path_created",
        "newcomer_release_plans",
        ["path_id", "created_at"],
    )
    op.create_index(
        "ix_newcomer_release_plans_org_status_created",
        "newcomer_release_plans",
        ["organization_id", "status", "created_at"],
    )
    op.add_column(
        "newcomer_paths",
        sa.Column(
            "active_release_plan_id",
            sa.String(36),
            sa.ForeignKey(
                "newcomer_release_plans.release_plan_id",
                ondelete="RESTRICT",
                name="fk_newcomer_paths_active_release_plan",
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("newcomer_paths", "active_release_plan_id")
    op.drop_index(
        "ix_newcomer_release_plans_org_status_created",
        table_name="newcomer_release_plans",
    )
    op.drop_index(
        "ix_newcomer_release_plans_path_created",
        table_name="newcomer_release_plans",
    )
    op.drop_index("ix_newcomer_release_plans_status", table_name="newcomer_release_plans")
    op.drop_index(
        "ix_newcomer_release_plans_path_revision_id",
        table_name="newcomer_release_plans",
    )
    op.drop_index("ix_newcomer_release_plans_path_id", table_name="newcomer_release_plans")
    op.drop_index(
        "ix_newcomer_release_plans_organization_id",
        table_name="newcomer_release_plans",
    )
    op.drop_table("newcomer_release_plans")
    op.drop_index(
        "ix_newcomer_enrollment_imports_cohort_created",
        table_name="newcomer_enrollment_imports",
    )
    op.drop_index(
        "ix_newcomer_enrollment_imports_cohort_id",
        table_name="newcomer_enrollment_imports",
    )
    op.drop_index(
        "ix_newcomer_enrollment_imports_organization_id",
        table_name="newcomer_enrollment_imports",
    )
    op.drop_table("newcomer_enrollment_imports")
    op.drop_index(
        "ix_learning_candidate_bulk_review_org_created",
        table_name="learning_question_candidate_bulk_reviews",
    )
    op.drop_index(
        "ix_learning_question_candidate_bulk_reviews_organization_id",
        table_name="learning_question_candidate_bulk_reviews",
    )
    op.drop_table("learning_question_candidate_bulk_reviews")
    with op.batch_alter_table("newcomer_cohorts") as batch_op:
        batch_op.drop_constraint("ck_newcomer_cohorts_status", type_="check")
        batch_op.create_check_constraint(
            "ck_newcomer_cohorts_status",
            "status IN ('active','closed','archived')",
        )
