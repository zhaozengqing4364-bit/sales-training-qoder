"""multimedia learning source metadata

Revision ID: 20260720_0900_007
Revises: 20260717_1500_006
Create Date: 2026-07-20 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260720_0900_007"
down_revision: str | None = "20260717_1500_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DOCUMENT = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    with op.batch_alter_table("learning_source_document_revisions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "content_kind",
                sa.String(32),
                nullable=False,
                server_default="document",
            )
        )
        batch_op.add_column(sa.Column("original_filename", sa.String(255)))
        batch_op.add_column(sa.Column("trusted_mime_type", sa.String(160)))
        batch_op.add_column(sa.Column("file_extension", sa.String(16)))
        batch_op.add_column(sa.Column("file_size_bytes", sa.Integer()))
        batch_op.add_column(sa.Column("language", sa.String(32)))
        batch_op.add_column(sa.Column("page_count", sa.Integer()))
        batch_op.add_column(sa.Column("duration_ms", sa.Integer()))
        batch_op.add_column(sa.Column("preview_version", sa.String(120)))
        batch_op.add_column(
            sa.Column(
                "processing_state",
                sa.String(24),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("processing_stage", sa.String(120)))
        batch_op.add_column(sa.Column("failure_code", sa.String(120)))
        batch_op.add_column(sa.Column("failure_message", sa.String(500)))
        batch_op.add_column(sa.Column("manual_content", sa.Text()))
        batch_op.add_column(
            sa.Column(
                "preview_manifest_json",
                JSON_DOCUMENT,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(sa.Column("processed_at", sa.DateTime(timezone=True)))
        batch_op.create_check_constraint(
            "ck_learning_source_revision_content_kind",
            "content_kind IN ('document','slide_deck','demo_video','external_demo','script','example_audio','attachment')",
        )
        batch_op.create_check_constraint(
            "ck_learning_source_revision_processing_state",
            "processing_state IN ('pending','processing','partial','ready','failed','cancelled')",
        )
    op.execute(
        sa.text(
            "UPDATE learning_source_document_revisions "
            "SET processing_state = CASE parse_status "
            "WHEN 'ready' THEN 'ready' WHEN 'failed' THEN 'failed' ELSE 'pending' END"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("learning_source_document_revisions") as batch_op:
        batch_op.drop_constraint(
            "ck_learning_source_revision_processing_state", type_="check"
        )
        batch_op.drop_constraint(
            "ck_learning_source_revision_content_kind", type_="check"
        )
        for column_name in (
            "processed_at",
            "preview_manifest_json",
            "failure_message",
            "manual_content",
            "failure_code",
            "processing_stage",
            "processing_state",
            "preview_version",
            "duration_ms",
            "page_count",
            "language",
            "file_size_bytes",
            "file_extension",
            "trusted_mime_type",
            "original_filename",
            "content_kind",
        ):
            batch_op.drop_column(column_name)
