"""Add persona_policy and backfill persona-centered source-of-truth

Revision ID: 20260216_0100_015
Revises: 20260215_2300_014
Create Date: 2026-02-16 01:00:00.000000
"""

from __future__ import annotations

import json
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260216_0100_015"
down_revision: Union[str, None] = "20260215_2300_014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(column.get("name") == column_name for column in columns)


def _parse_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _parse_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _column_exists(inspector, "personas", "persona_policy"):
        op.add_column(
            "personas",
            sa.Column("persona_policy", sa.JSON(), nullable=True),
        )
        inspector = sa.inspect(bind)

    personas_rows = bind.execute(
        sa.text(
            "SELECT id, system_prompt, knowledge_base_ids, persona_policy FROM personas"
        )
    ).mappings()

    personas_table = sa.table(
        "personas",
        sa.column("id", sa.String),
        sa.column("persona_policy", sa.JSON),
    )

    for row in personas_rows:
        existing_policy = _parse_json_dict(row.get("persona_policy"))
        if existing_policy:
            continue

        system_prompt = str(row.get("system_prompt") or "").strip()
        kb_ids = _parse_json_list(row.get("knowledge_base_ids"))
        persona_policy = {
            "version": 1,
            "system_prompt": system_prompt,
            "knowledge_base_ids": kb_ids,
            "tool_policy": {},
        }
        bind.execute(
            personas_table.update()
            .where(personas_table.c.id == str(row.get("id")))
            .values(persona_policy=persona_policy)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _column_exists(inspector, "personas", "persona_policy"):
        op.drop_column("personas", "persona_policy")
