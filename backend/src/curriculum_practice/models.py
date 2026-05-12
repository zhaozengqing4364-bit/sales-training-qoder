from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)

from common.db.models import Base


class PracticeTemplate(Base):
    __tablename__ = "practice_templates"

    template_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(32), nullable=False, index=True)
    mode = Column(String(40), nullable=False)
    agent_id = Column(String(36), nullable=False, index=True)
    persona_id = Column(String(36), nullable=False, index=True)
    runtime_profile_id = Column(String(36), nullable=False, index=True)
    voice_mode = Column(String(32), nullable=False, default="stepfun_realtime")
    scoring_ruleset_id = Column(String(36), nullable=False, index=True)
    knowledge_base_refs = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(80), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "scenario_type IN ('sales', 'presentation')",
            name="ck_practice_template_scenario_type",
        ),
        CheckConstraint(
            "mode IN ('learning', 'expert_qa', 'examiner', 'customer_roleplay', 'mixed_path')",
            name="ck_practice_template_mode",
        ),
        CheckConstraint(
            "voice_mode IN ('legacy', 'stepfun_realtime')",
            name="ck_practice_template_voice_mode",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_practice_template_status",
        ),
        Index("idx_practice_templates_status_updated", "status", "updated_at"),
    )
