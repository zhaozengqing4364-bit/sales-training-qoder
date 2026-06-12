"""Add AI coach interaction v1 structured fields to sales_trainer_ai_coach_turns

Revision ID: 20260609_1100_078b_ai_fields
Revises: 20260609_1000_078_ai_coach
Create Date: 2026-06-09 11:00:00.000000

This migration adds the layered interaction v1 fields to the
``sales_trainer_ai_coach_turns`` table. Existing columns
(``raw_model_output``, ``validated_output``, ``question``, ``user_answer``,
``ai_feedback``, ``score``, ``max_score``, ``missed_points``, ``next_question``)
remain in place; the new JSON fields layer on top of them.

Layering model:
- ``interaction_snapshot``  -> internal contract (AiCoachInteractionInternalV1).
- ``public_interaction``    -> learner render spec (AiCoachInteractionPublicV1).
- ``answer_payload``        -> learner submitted answer (AiCoachAnswerPayloadV1).
- ``score_result``          -> scoring outcome (AiCoachScoreResultV1).
- ``schema_version``        -> backend-pinned contract version ("ai_coach_interaction_v1").

This migration is a minimal, additive ALTER. No existing column is touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260609_1100_078b_ai_fields"
down_revision: str | None = "20260609_1000_078_ai_coach"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sales_trainer_ai_coach_turns",
        sa.Column("interaction_snapshot", sa.JSON, nullable=True),
    )
    op.add_column(
        "sales_trainer_ai_coach_turns",
        sa.Column("public_interaction", sa.JSON, nullable=True),
    )
    op.add_column(
        "sales_trainer_ai_coach_turns",
        sa.Column("schema_version", sa.String(32), nullable=True),
    )
    op.add_column(
        "sales_trainer_ai_coach_turns",
        sa.Column("answer_payload", sa.JSON, nullable=True),
    )
    op.add_column(
        "sales_trainer_ai_coach_turns",
        sa.Column("score_result", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_trainer_ai_coach_turns", "score_result")
    op.drop_column("sales_trainer_ai_coach_turns", "answer_payload")
    op.drop_column("sales_trainer_ai_coach_turns", "schema_version")
    op.drop_column("sales_trainer_ai_coach_turns", "public_interaction")
    op.drop_column("sales_trainer_ai_coach_turns", "interaction_snapshot")
