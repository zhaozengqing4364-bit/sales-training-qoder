"""Add content_hash to knowledge_documents for deduplication

Revision ID: 20260225_1000_017
Revises: 20260221_2000_016
Create Date: 2026-02-25 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225_1000_017"
down_revision: Union[str, None] = "20260221_2000_016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(column.get("name") == column_name for column in columns)


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(index.get("name") == index_name for index in indexes)


def _unique_constraint_exists(
    inspector: sa.Inspector,
    table_name: str,
    constraint_name: str,
) -> bool:
    try:
        constraints = inspector.get_unique_constraints(table_name)
    except Exception:
        return False
    return any(item.get("name") == constraint_name for item in constraints)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _column_exists(inspector, "knowledge_documents", "content_hash"):
        op.add_column(
            "knowledge_documents",
            sa.Column("content_hash", sa.String(length=64), nullable=True),
        )

    inspector = sa.inspect(op.get_bind())
    if not _index_exists(
        inspector,
        "knowledge_documents",
        "ix_knowledge_documents_content_hash",
    ):
        op.create_index(
            "ix_knowledge_documents_content_hash",
            "knowledge_documents",
            ["content_hash"],
            unique=False,
        )

    inspector = sa.inspect(op.get_bind())
    if not _unique_constraint_exists(
        inspector,
        "knowledge_documents",
        "uq_knowledge_document_kb_content_hash",
    ):
        op.create_unique_constraint(
            "uq_knowledge_document_kb_content_hash",
            "knowledge_documents",
            ["knowledge_base_id", "content_hash"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _unique_constraint_exists(
        inspector,
        "knowledge_documents",
        "uq_knowledge_document_kb_content_hash",
    ):
        op.drop_constraint(
            "uq_knowledge_document_kb_content_hash",
            "knowledge_documents",
            type_="unique",
        )

    inspector = sa.inspect(op.get_bind())
    if _index_exists(
        inspector,
        "knowledge_documents",
        "ix_knowledge_documents_content_hash",
    ):
        op.drop_index("ix_knowledge_documents_content_hash", table_name="knowledge_documents")

    inspector = sa.inspect(op.get_bind())
    if _column_exists(inspector, "knowledge_documents", "content_hash"):
        op.drop_column("knowledge_documents", "content_hash")
