from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)

from common.db.models import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SalesTrainerRegradeRun(Base):
    __tablename__ = "sales_trainer_regrade_runs"

    run_id = Column(String(36), primary_key=True, default=_uuid)
    target_type = Column(String(40), nullable=False, index=True)
    target_id = Column(String(36), nullable=False, index=True)
    target_revision_id = Column(
        String(36),
        ForeignKey("sales_trainer_asset_revisions.revision_id"),
        nullable=True,
        index=True,
    )
    status = Column(String(20), nullable=False, default="completed", index=True)
    reason = Column(Text, nullable=False)
    impact_scope_json = Column("impact_scope", JSON, nullable=False, default=dict)
    before_snapshot_json = Column("before_snapshot", JSON, nullable=False, default=dict)
    after_snapshot_json = Column("after_snapshot", JSON, nullable=False, default=dict)
    trace_id = Column(String(100), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "target_type IN ('quiz_attempt', 'audio_submission')",
            name="ck_sales_trainer_regrade_target_type",
        ),
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_sales_trainer_regrade_status",
        ),
        Index(
            "idx_sales_trainer_regrade_target",
            "target_type",
            "target_id",
            "created_at",
        ),
    )
