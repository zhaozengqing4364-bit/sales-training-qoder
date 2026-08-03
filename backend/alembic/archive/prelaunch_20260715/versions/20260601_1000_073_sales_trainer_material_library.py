"""add sales trainer material library

Revision ID: 20260601_1000_073
Revises: 20260528_1600_072
Create Date: 2026-06-01 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260601_1000_073"
down_revision: str | None = "20260528_1600_072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names())


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in set(inspector.get_table_names()):
        return False
    return constraint_name in {
        constraint.get("name") for constraint in inspector.get_foreign_keys(table_name)
    }


def upgrade() -> None:
    if not _table_exists("sales_trainer_materials"):
        op.create_table(
            "sales_trainer_materials",
            sa.Column("material_id", sa.String(length=36), nullable=False),
            sa.Column("material_key", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("material_type", sa.String(length=40), nullable=False, server_default="ppt_deck"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("purpose", sa.String(length=50), nullable=False, server_default="ppt_pitch"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("current_version_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "material_type IN ('ppt_deck', 'script', 'example_audio', 'attachment')",
                name="ck_sales_trainer_material_type",
            ),
            sa.CheckConstraint(
                "status IN ('draft', 'published', 'archived')",
                name="ck_sales_trainer_material_status",
            ),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("material_id"),
            sa.UniqueConstraint("material_key"),
        )
    if not _table_exists("sales_trainer_material_versions"):
        op.create_table(
            "sales_trainer_material_versions",
            sa.Column("version_id", sa.String(length=36), nullable=False),
            sa.Column("material_id", sa.String(length=36), nullable=False),
            sa.Column("version_label", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("file_name", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=False),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("storage_key", sa.Text(), nullable=False),
            sa.Column("file_hash", sa.String(length=128), nullable=True),
            sa.Column("release_notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_by", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('draft', 'published', 'archived')",
                name="ck_sales_trainer_material_version_status",
            ),
            sa.CheckConstraint(
                "file_size_bytes > 0",
                name="ck_sales_trainer_material_version_file_size",
            ),
            sa.ForeignKeyConstraint(
                ["material_id"],
                ["sales_trainer_materials.material_id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["published_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("version_id"),
            sa.UniqueConstraint(
                "material_id",
                "version_label",
                name="uq_sales_trainer_material_version_label",
            ),
        )

    if not _index_exists("sales_trainer_materials", "idx_sales_trainer_material_status_updated"):
        op.create_index(
            "idx_sales_trainer_material_status_updated",
            "sales_trainer_materials",
            ["status", "updated_at"],
        )
    if not _index_exists("sales_trainer_materials", "ix_sales_trainer_materials_material_key"):
        op.create_index(
            "ix_sales_trainer_materials_material_key",
            "sales_trainer_materials",
            ["material_key"],
        )
    if not _index_exists("sales_trainer_materials", "ix_sales_trainer_materials_material_type"):
        op.create_index(
            "ix_sales_trainer_materials_material_type",
            "sales_trainer_materials",
            ["material_type"],
        )
    if not _index_exists("sales_trainer_materials", "ix_sales_trainer_materials_purpose"):
        op.create_index(
            "ix_sales_trainer_materials_purpose",
            "sales_trainer_materials",
            ["purpose"],
        )
    if not _index_exists("sales_trainer_materials", "ix_sales_trainer_materials_status"):
        op.create_index(
            "ix_sales_trainer_materials_status",
            "sales_trainer_materials",
            ["status"],
        )
    if not _index_exists("sales_trainer_material_versions", "idx_sales_trainer_material_versions_material_status"):
        op.create_index(
            "idx_sales_trainer_material_versions_material_status",
            "sales_trainer_material_versions",
            ["material_id", "status", "updated_at"],
        )
    if not _index_exists("sales_trainer_material_versions", "ix_sales_trainer_material_versions_material_id"):
        op.create_index(
            "ix_sales_trainer_material_versions_material_id",
            "sales_trainer_material_versions",
            ["material_id"],
        )
    if not _index_exists("sales_trainer_material_versions", "ix_sales_trainer_material_versions_status"):
        op.create_index(
            "ix_sales_trainer_material_versions_status",
            "sales_trainer_material_versions",
            ["status"],
        )

    if not _column_exists("sales_trainer_audio_score_prompts", "learner_rubric"):
        op.add_column(
            "sales_trainer_audio_score_prompts",
            sa.Column("learner_rubric", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
    for column_name, column in (
        ("confirmed_material_version_id", sa.Column("confirmed_material_version_id", sa.String(length=36), nullable=True)),
        ("confirmed_material_at", sa.Column("confirmed_material_at", sa.DateTime(timezone=True), nullable=True)),
        ("material_snapshot", sa.Column("material_snapshot", sa.JSON(), nullable=True)),
        ("score_scheme_snapshot", sa.Column("score_scheme_snapshot", sa.JSON(), nullable=True)),
        ("task_brief_snapshot", sa.Column("task_brief_snapshot", sa.JSON(), nullable=True)),
    ):
        if not _column_exists("sales_trainer_audio_submissions", column_name):
            op.add_column("sales_trainer_audio_submissions", column)

    if not _index_exists("sales_trainer_audio_submissions", "idx_sales_trainer_audio_confirmed_material_version"):
        op.create_index(
            "idx_sales_trainer_audio_confirmed_material_version",
            "sales_trainer_audio_submissions",
            ["confirmed_material_version_id"],
        )
    if not _foreign_key_exists("sales_trainer_audio_submissions", "fk_sales_trainer_audio_confirmed_material_version"):
        op.create_foreign_key(
            "fk_sales_trainer_audio_confirmed_material_version",
            "sales_trainer_audio_submissions",
            "sales_trainer_material_versions",
            ["confirmed_material_version_id"],
            ["version_id"],
        )


def downgrade() -> None:
    if _foreign_key_exists("sales_trainer_audio_submissions", "fk_sales_trainer_audio_confirmed_material_version"):
        op.drop_constraint(
            "fk_sales_trainer_audio_confirmed_material_version",
            "sales_trainer_audio_submissions",
            type_="foreignkey",
        )
    if _index_exists("sales_trainer_audio_submissions", "idx_sales_trainer_audio_confirmed_material_version"):
        op.drop_index(
            "idx_sales_trainer_audio_confirmed_material_version",
            table_name="sales_trainer_audio_submissions",
        )
    for column_name in (
        "task_brief_snapshot",
        "score_scheme_snapshot",
        "material_snapshot",
        "confirmed_material_at",
        "confirmed_material_version_id",
    ):
        if _column_exists("sales_trainer_audio_submissions", column_name):
            op.drop_column("sales_trainer_audio_submissions", column_name)
    if _column_exists("sales_trainer_audio_score_prompts", "learner_rubric"):
        op.drop_column("sales_trainer_audio_score_prompts", "learner_rubric")
    if _table_exists("sales_trainer_material_versions"):
        op.drop_table("sales_trainer_material_versions")
    if _table_exists("sales_trainer_materials"):
        op.drop_table("sales_trainer_materials")
