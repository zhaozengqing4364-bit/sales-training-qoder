"""SQLAlchemy persistence owned only by the competency-evidence module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.db.model_registry import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class CanonicalCompetency(Base):
    __tablename__ = "canonical_competencies"

    competency_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stable_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    standard_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active_revision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class CanonicalCompetencyRevision(Base):
    __tablename__ = "canonical_competency_revisions"

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    competency_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("canonical_competencies.competency_id", ondelete="RESTRICT"),
        nullable=False,
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    observable_behaviors_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    evidence_types_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    evidence_roles_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    minimum_requirements_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    applicable_scope_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "competency_id", "revision_no", name="uq_competency_revision_number"
        ),
        CheckConstraint(
            "status IN ('published','archived')",
            name="ck_competency_revision_status",
        ),
    )


class CompetencyMapping(Base):
    __tablename__ = "competency_mappings"

    mapping_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_revision_id: Mapped[str] = mapped_column(String(200), nullable=False)
    competency_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("canonical_competency_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    competency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    evidence_role: Mapped[str] = mapped_column(String(32), nullable=False)
    mapping_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="published")
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source_type",
            "source_revision_id",
            "competency_revision_id",
            "mapping_revision",
            name="uq_competency_mapping_revision",
        ),
        CheckConstraint(
            "status IN ('published','superseded','archived')",
            name="ck_competency_mapping_status",
        ),
        CheckConstraint(
            "weight > 0 AND weight <= 1", name="ck_competency_mapping_weight"
        ),
        Index(
            "ix_competency_mapping_source",
            "organization_id",
            "source_type",
            "source_revision_id",
        ),
    )


class CompetencyEvidenceRecord(Base):
    __tablename__ = "competency_evidence_records"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    learner_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    enrollment_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    competency_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("canonical_competency_revisions.revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    competency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    source_activity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(36), nullable=False)
    outcome_id: Mapped[str] = mapped_column(String(36), nullable=False)
    outcome_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_role: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_score: Mapped[float | None] = mapped_column(Numeric(10, 4))
    observed_max_score: Mapped[float | None] = mapped_column(Numeric(10, 4))
    observed_result: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 5))
    quality: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_validity: Mapped[str] = mapped_column(String(32), nullable=False)
    source_refs_json: Mapped[list[dict[str, str]]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    lineage_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=dict
    )
    critical_flags_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    degradations_json: Mapped[list[str]] = mapped_column(
        JSON_DOCUMENT, nullable=False, default=list
    )
    supersedes_evidence_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("competency_evidence_records.evidence_id", ondelete="RESTRICT"),
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "outcome_id",
            "outcome_version",
            "competency_revision_id",
            name="uq_competency_evidence_outcome_revision",
        ),
        CheckConstraint(
            "initial_validity IN ('valid','pending_review','insufficient_quality','invalidated')",
            name="ck_competency_evidence_initial_validity",
        ),
        CheckConstraint(
            "quality IN ('verified','degraded','unscorable','invalid')",
            name="ck_competency_evidence_quality",
        ),
        Index(
            "ix_competency_evidence_enrollment_key_time",
            "organization_id",
            "enrollment_id",
            "competency_key",
            "observed_at",
        ),
    )


class CompetencyEvidenceValidityEvent(Base):
    __tablename__ = "competency_evidence_validity_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("competency_evidence_records.evidence_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    replacement_evidence_id: Mapped[str | None] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "evidence_id",
            "idempotency_key_hash",
            name="uq_competency_evidence_validity_command",
        ),
        CheckConstraint(
            "status IN ('invalidated','restored')",
            name="ck_competency_evidence_validity_event_status",
        ),
    )


__all__ = [
    "CanonicalCompetency",
    "CanonicalCompetencyRevision",
    "CompetencyEvidenceRecord",
    "CompetencyEvidenceValidityEvent",
    "CompetencyMapping",
]
