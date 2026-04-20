"""formalize password reset lifecycle and delivery observability

Revision ID: 027_reset_lifecycle_delivery
Revises: 026_password_reset_tokens
Create Date: 2026-04-11 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "027_reset_lifecycle_delivery"
down_revision: Union[str, None] = "026_password_reset_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("password_reset_tokens") as batch_op:
        batch_op.add_column(sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("invalidation_reason", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column(
                "delivery_status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(sa.Column("delivery_attempted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("delivery_error", sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            "ck_password_reset_tokens_delivery_status",
            "delivery_status IN ('pending', 'sent', 'failed')",
        )
        batch_op.create_check_constraint(
            "ck_password_reset_tokens_invalidation_reason",
            "invalidation_reason IS NULL OR invalidation_reason IN ('superseded', 'expired')",
        )
        batch_op.create_index(
            "ix_password_reset_tokens_invalidated_at",
            ["invalidated_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_password_reset_tokens_delivery_status",
            ["delivery_status"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("password_reset_tokens") as batch_op:
        batch_op.drop_index("ix_password_reset_tokens_delivery_status")
        batch_op.drop_index("ix_password_reset_tokens_invalidated_at")
        batch_op.drop_constraint("ck_password_reset_tokens_invalidation_reason", type_="check")
        batch_op.drop_constraint("ck_password_reset_tokens_delivery_status", type_="check")
        batch_op.drop_column("delivery_error")
        batch_op.drop_column("delivery_attempted_at")
        batch_op.drop_column("delivery_status")
        batch_op.drop_column("invalidation_reason")
        batch_op.drop_column("invalidated_at")
