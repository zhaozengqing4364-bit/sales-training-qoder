"""Expand knowledge_documents file_type check for spreadsheet uploads

Revision ID: 20260314_1200_018
Revises: 20260225_1000_017
Create Date: 2026-03-14 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260314_1200_018"
down_revision: Union[str, None] = "20260225_1000_017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_NAME = "knowledge_documents"
_CONSTRAINT_NAME = "ck_knowledge_document_file_type"
_UPGRADE_CONSTRAINT = "file_type IN ('pdf', 'docx', 'txt', 'md', 'xlsx', 'xls')"
_DOWNGRADE_CONSTRAINT = "file_type IN ('pdf', 'docx', 'txt', 'md')"


def _check_constraint_exists(
    inspector: sa.Inspector,
    table_name: str,
    constraint_name: str,
) -> bool:
    try:
        constraints = inspector.get_check_constraints(table_name)
    except Exception:
        return False
    return any(item.get("name") == constraint_name for item in constraints)


def _replace_file_type_constraint(constraint_sql: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_constraint = _check_constraint_exists(
        inspector,
        _TABLE_NAME,
        _CONSTRAINT_NAME,
    )
    dialect = str(getattr(bind.dialect, "name", "")).lower()

    # PostgreSQL can update the check constraint in-place. Recreating the table
    # here may emit UNIQUE NULLS DISTINCT for inherited unique constraints,
    # which is unsupported on older PostgreSQL versions.
    if dialect == "postgresql":
        if has_constraint:
            op.drop_constraint(_CONSTRAINT_NAME, _TABLE_NAME, type_="check")
        op.create_check_constraint(_CONSTRAINT_NAME, _TABLE_NAME, constraint_sql)
        return

    with op.batch_alter_table(_TABLE_NAME, recreate="always") as batch_op:
        if has_constraint:
            batch_op.drop_constraint(_CONSTRAINT_NAME, type_="check")
        batch_op.create_check_constraint(_CONSTRAINT_NAME, constraint_sql)


def upgrade() -> None:
    _replace_file_type_constraint(_UPGRADE_CONSTRAINT)


def downgrade() -> None:
    _replace_file_type_constraint(_DOWNGRADE_CONSTRAINT)
