"""Reapply explicit legacy startup schema repairs under Alembic authority

Revision ID: 20260413_1040_029
Revises: 20260412_0315_028
Create Date: 2026-04-13 10:40:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from common.db.legacy_schema_repair import (
    repair_knowledge_document_legacy_schema,
    repair_persona_policy_legacy_schema,
)


# revision identifiers, used by Alembic.
revision: str = "20260413_1040_029"
down_revision: Union[str, None] = "20260412_0315_028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op

    bind = op.get_bind()
    repair_persona_policy_legacy_schema(
        bind,
        repair_surface=f"alembic revision {revision}",
    )
    repair_knowledge_document_legacy_schema(
        bind,
        repair_surface=f"alembic revision {revision}",
    )


def downgrade() -> None:
    # This revision only re-applies idempotent legacy compatibility repairs under
    # explicit Alembic authority. Existing feature revisions own reversible schema
    # changes, so this reconciliation layer intentionally performs no downgrade.
    return None
