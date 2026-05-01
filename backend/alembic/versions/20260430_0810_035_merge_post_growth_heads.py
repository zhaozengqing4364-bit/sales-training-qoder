"""merge post-growth migration heads

Revision ID: 20260430_0810_035
Revises: 20260424_1100_033, 20260424_1101_033_business_rules, 20260428_0917_034
Create Date: 2026-04-30 08:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260430_0810_035"
down_revision: str | tuple[str, ...] | None = (
    "20260424_1100_033",
    "20260424_1101_033_business_rules",
    "20260428_0917_034",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
