"""Single writer for canonical competency mappings and immutable evidence."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from competency_evidence.contracts import (
    CompetencyEvidenceProjection,
    OutcomeEvidenceInput,
)
from competency_evidence.errors import CompetencyEvidenceError
from competency_evidence.identifiers import STANDARD_COMPETENCIES
from competency_evidence.models import (
    CanonicalCompetency,
    CanonicalCompetencyRevision,
    CompetencyEvidenceRecord,
    CompetencyEvidenceValidityEvent,
    CompetencyMapping,
)
from task_runtime.outbox import DomainEvent, SQLAlchemyOutboxWriter


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"newcomer-foundation:{kind}:{key}"))


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


class CompetencyEvidenceService:
    """Owns all writes to competency catalog, mappings, and evidence history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._outbox = SQLAlchemyOutboxWriter(session)

    async def ensure_standard_catalog(
        self,
        *,
        actor_id: str,
        verify_only: bool = False,
    ) -> dict[str, CanonicalCompetencyRevision]:
        revisions: dict[str, CanonicalCompetencyRevision] = {}
        now = _now()
        for order, definition in enumerate(STANDARD_COMPETENCIES, start=1):
            competency_id = _stable_id("competency", definition.stable_key)
            revision_id = _stable_id(
                "competency-revision", f"{definition.stable_key}:1"
            )
            payload = {
                "stable_key": definition.stable_key,
                "title": definition.title,
                "description": definition.description,
                "observable_behaviors": definition.observable_behaviors,
                "evidence_types": definition.evidence_types,
                "evidence_roles": definition.evidence_roles,
                "minimum_requirements": {
                    "minimum_valid_evidence": definition.minimum_valid_evidence,
                    "minimum_confidence": definition.minimum_confidence,
                },
                "applicable_scope": {"launch": True, "organization_extension": False},
            }
            expected_hash = _hash(payload)
            competency = await self._session.get(CanonicalCompetency, competency_id)
            revision = await self._session.get(
                CanonicalCompetencyRevision, revision_id
            )
            if competency is None or revision is None:
                if verify_only:
                    raise CompetencyEvidenceError(
                        "[COMPETENCY_CATALOG_MISSING]",
                        "首发能力目录尚未完整安装。",
                        409,
                        details={"competency_key": definition.stable_key},
                    )
                if competency is None:
                    competency = CanonicalCompetency(
                        competency_id=competency_id,
                        stable_key=definition.stable_key,
                        standard_order=order,
                        is_standard=True,
                        active_revision_id=revision_id,
                        created_at=now,
                    )
                    self._session.add(competency)
                    await self._session.flush([competency])
                if revision is None:
                    revision = CanonicalCompetencyRevision(
                        revision_id=revision_id,
                        competency_id=competency_id,
                        revision_no=1,
                        title=definition.title,
                        description=definition.description,
                        observable_behaviors_json=list(
                            definition.observable_behaviors
                        ),
                        evidence_types_json=list(definition.evidence_types),
                        evidence_roles_json=list(definition.evidence_roles),
                        minimum_requirements_json=payload["minimum_requirements"],
                        applicable_scope_json=payload["applicable_scope"],
                        content_hash=expected_hash,
                        status="published",
                        created_by=actor_id,
                        created_at=now,
                        published_at=now,
                    )
                    self._session.add(revision)
                    await self._session.flush([revision])
            if (
                competency.stable_key != definition.stable_key
                or competency.active_revision_id != revision_id
                or revision.content_hash != expected_hash
                or revision.status != "published"
            ):
                raise CompetencyEvidenceError(
                    "[COMPETENCY_CATALOG_DRIFT]",
                    "首发能力目录与冻结修订不一致，已停止自动覆盖。",
                    409,
                    details={"competency_key": definition.stable_key},
                )
            revisions[definition.stable_key] = revision
        return revisions

    async def require_published_keys(self, competency_keys: Sequence[str]) -> None:
        keys = _unique(competency_keys)
        if not keys:
            raise CompetencyEvidenceError(
                "[COMPETENCY_MAPPING_REQUIRED]",
                "每个训练活动必须映射至少一项基础能力。",
                422,
            )
        rows = list(
            (
                await self._session.execute(
                    select(CanonicalCompetency).where(
                        CanonicalCompetency.stable_key.in_(keys)
                    )
                )
            ).scalars()
        )
        found = {row.stable_key for row in rows}
        missing = sorted(set(keys) - found)
        if missing:
            raise CompetencyEvidenceError(
                "[COMPETENCY_MAPPING_UNKNOWN]",
                "训练活动引用了未发布的基础能力。",
                422,
                details={"competency_keys": missing},
            )

    async def publish_activity_mappings(
        self,
        *,
        organization_id: str,
        path_revision_id: str,
        activity_id: str,
        activity_type: str,
        competency_keys: Sequence[str],
        actor_id: str,
    ) -> tuple[CompetencyMapping, ...]:
        revisions = await self.ensure_standard_catalog(actor_id=actor_id)
        keys = _unique(competency_keys)
        await self.require_published_keys(keys)
        role = {
            "lesson": "knowledge",
            "quiz": "knowledge",
            "audio_assessment": "expression",
            "ai_coach": "application",
            "assignment": "application",
        }.get(activity_type, "application")
        weight = (Decimal(1) / Decimal(len(keys))).quantize(
            Decimal("0.000001")
        )
        source_revision_id = f"{path_revision_id}:{activity_id}"
        result: list[CompetencyMapping] = []
        for key in keys:
            revision = revisions[key]
            existing = await self._session.scalar(
                select(CompetencyMapping)
                .where(CompetencyMapping.organization_id == organization_id)
                .where(CompetencyMapping.source_type == "activity_definition")
                .where(
                    CompetencyMapping.source_revision_id == source_revision_id
                )
                .where(
                    CompetencyMapping.competency_revision_id
                    == revision.revision_id
                )
                .where(CompetencyMapping.mapping_revision == 1)
                .limit(1)
            )
            if existing is None:
                existing = CompetencyMapping(
                    organization_id=organization_id,
                    source_type="activity_definition",
                    source_id=activity_id,
                    source_revision_id=source_revision_id,
                    competency_revision_id=revision.revision_id,
                    competency_key=key,
                    weight=weight,
                    evidence_role=role,
                    mapping_revision=1,
                    status="published",
                    created_by=actor_id,
                    created_at=_now(),
                )
                self._session.add(existing)
                await self._session.flush([existing])
            elif (
                existing.competency_key != key
                or existing.evidence_role != role
                or Decimal(existing.weight) != weight
                or existing.status != "published"
            ):
                raise CompetencyEvidenceError(
                    "[COMPETENCY_MAPPING_DRIFT]",
                    "训练活动能力映射与已发布修订不一致。",
                    409,
                    details={"activity_id": activity_id, "competency_key": key},
                )
            result.append(existing)
        return tuple(result)

    async def append_outcome(
        self, input_value: OutcomeEvidenceInput
    ) -> tuple[CompetencyEvidenceProjection, ...]:
        revisions = await self.ensure_standard_catalog(actor_id=input_value.actor_id)
        mappings = await self.publish_activity_mappings(
            organization_id=input_value.organization_id,
            path_revision_id=input_value.path_revision_id,
            activity_id=input_value.activity_id,
            activity_type=input_value.activity_type,
            competency_keys=input_value.competency_keys,
            actor_id=input_value.actor_id,
        )
        mapping_by_key = {item.competency_key: item for item in mappings}
        created: list[CompetencyEvidenceRecord] = []
        for key in _unique(input_value.competency_keys):
            revision = revisions[key]
            existing = await self._session.scalar(
                select(CompetencyEvidenceRecord)
                .where(
                    CompetencyEvidenceRecord.organization_id
                    == input_value.organization_id
                )
                .where(CompetencyEvidenceRecord.outcome_id == input_value.outcome_id)
                .where(
                    CompetencyEvidenceRecord.outcome_version
                    == input_value.outcome_version
                )
                .where(
                    CompetencyEvidenceRecord.competency_revision_id
                    == revision.revision_id
                )
                .limit(1)
            )
            if existing is not None:
                created.append(existing)
                continue
            previous = await self._previous_evidence(
                input_value=input_value,
                competency_revision_id=revision.revision_id,
            )
            validity, quality = self._initial_validity(input_value, revision)
            mapping = mapping_by_key[key]
            row = CompetencyEvidenceRecord(
                organization_id=input_value.organization_id,
                learner_id=input_value.learner_id,
                enrollment_id=input_value.enrollment_id,
                competency_revision_id=revision.revision_id,
                competency_key=key,
                source_activity_id=input_value.activity_id,
                attempt_id=input_value.attempt_id,
                outcome_id=input_value.outcome_id,
                outcome_version=input_value.outcome_version,
                evidence_type=input_value.activity_type,
                evidence_role=mapping.evidence_role,
                observed_score=input_value.score,
                observed_max_score=input_value.max_score,
                observed_result=(
                    input_value.assessment_result or input_value.lifecycle_result
                ),
                confidence=input_value.confidence,
                quality=quality,
                initial_validity=validity,
                source_refs_json=[dict(item) for item in input_value.source_refs],
                lineage_json={
                    **input_value.lineage,
                    "path_revision_id": input_value.path_revision_id,
                    "mapping_id": mapping.mapping_id,
                    "mapping_revision": mapping.mapping_revision,
                },
                critical_flags_json=list(input_value.critical_flags),
                degradations_json=list(input_value.degradations),
                supersedes_evidence_id=(
                    previous.evidence_id if previous is not None else None
                ),
                created_by=input_value.actor_id,
                observed_at=input_value.produced_at,
                created_at=_now(),
            )
            self._session.add(row)
            await self._session.flush([row])
            created.append(row)
            await self._outbox.append(
                DomainEvent(
                    event_type="CompetencyEvidenceUpdated",
                    schema_version=1,
                    occurred_at=_now(),
                    organization_id=input_value.organization_id,
                    actor_id=input_value.actor_id,
                    trace_id=input_value.trace_id,
                    correlation_id=input_value.enrollment_id,
                    causation_id=input_value.outcome_id,
                    idempotency_key=f"competency-evidence:{row.evidence_id}",
                    aggregate_type="competency_evidence",
                    aggregate_id=row.evidence_id,
                    aggregate_version=1,
                    payload={
                        "evidence_id": row.evidence_id,
                        "enrollment_id": input_value.enrollment_id,
                        "learner_id": input_value.learner_id,
                        "competency_key": key,
                        "outcome_id": input_value.outcome_id,
                        "outcome_version": input_value.outcome_version,
                        "validity": validity,
                    },
                )
            )
        return await self._project_rows(created)

    async def rebuild(
        self, inputs: Sequence[OutcomeEvidenceInput]
    ) -> tuple[CompetencyEvidenceProjection, ...]:
        enrollment_ids = {item.enrollment_id for item in inputs}
        if len(enrollment_ids) > 1:
            raise CompetencyEvidenceError(
                "[EVIDENCE_REBUILD_SCOPE_INVALID]",
                "一次只能重建一个训练分配的能力证据。",
                422,
            )
        for item in sorted(inputs, key=lambda value: (value.produced_at, value.outcome_version)):
            await self.append_outcome(item)
        if not inputs:
            return ()
        return await self.list_for_enrollment(
            organization_id=inputs[0].organization_id,
            enrollment_id=inputs[0].enrollment_id,
        )

    async def invalidate(
        self,
        *,
        organization_id: str,
        evidence_id: str,
        actor_id: str,
        reason: str,
        idempotency_key: str,
        trace_id: str | None = None,
    ) -> CompetencyEvidenceProjection:
        if not reason.strip():
            raise CompetencyEvidenceError(
                "[EVIDENCE_INVALIDATION_REASON_REQUIRED]",
                "请填写证据失效原因。",
                422,
            )
        row = await self._session.get(CompetencyEvidenceRecord, evidence_id)
        if row is None or row.organization_id != organization_id:
            raise CompetencyEvidenceError(
                "[EVIDENCE_NOT_FOUND]", "训练证据不存在或不可访问。", 404
            )
        key_hash = _secret_hash(idempotency_key)
        event = await self._session.scalar(
            select(CompetencyEvidenceValidityEvent)
            .where(
                CompetencyEvidenceValidityEvent.organization_id == organization_id
            )
            .where(CompetencyEvidenceValidityEvent.evidence_id == evidence_id)
            .where(
                CompetencyEvidenceValidityEvent.idempotency_key_hash == key_hash
            )
            .limit(1)
        )
        if event is None:
            event = CompetencyEvidenceValidityEvent(
                organization_id=organization_id,
                evidence_id=evidence_id,
                status="invalidated",
                reason=reason.strip(),
                replacement_evidence_id=None,
                actor_id=actor_id,
                idempotency_key_hash=key_hash,
                created_at=_now(),
            )
            self._session.add(event)
            await self._session.flush([event])
            await self._outbox.append(
                DomainEvent(
                    event_type="CompetencyEvidenceInvalidated",
                    schema_version=1,
                    occurred_at=event.created_at,
                    organization_id=organization_id,
                    actor_id=actor_id,
                    trace_id=trace_id,
                    correlation_id=row.enrollment_id,
                    causation_id=row.evidence_id,
                    idempotency_key=f"evidence-validity:{event.event_id}",
                    aggregate_type="competency_evidence",
                    aggregate_id=row.evidence_id,
                    aggregate_version=1,
                    payload={
                        "evidence_id": row.evidence_id,
                        "enrollment_id": row.enrollment_id,
                        "status": "invalidated",
                    },
                )
            )
        return (await self._project_rows([row]))[0]

    async def list_for_enrollment(
        self,
        *,
        organization_id: str,
        enrollment_id: str,
    ) -> tuple[CompetencyEvidenceProjection, ...]:
        rows = list(
            (
                await self._session.execute(
                    select(CompetencyEvidenceRecord)
                    .where(
                        CompetencyEvidenceRecord.organization_id == organization_id
                    )
                    .where(
                        CompetencyEvidenceRecord.enrollment_id == enrollment_id
                    )
                    .order_by(
                        CompetencyEvidenceRecord.observed_at.asc(),
                        CompetencyEvidenceRecord.outcome_version.asc(),
                        CompetencyEvidenceRecord.evidence_id.asc(),
                    )
                )
            ).scalars()
        )
        return await self._project_rows(rows)

    async def _previous_evidence(
        self,
        *,
        input_value: OutcomeEvidenceInput,
        competency_revision_id: str,
    ) -> CompetencyEvidenceRecord | None:
        if input_value.supersedes_outcome_id is None:
            return None
        row: CompetencyEvidenceRecord | None = await self._session.scalar(
            select(CompetencyEvidenceRecord)
            .where(
                CompetencyEvidenceRecord.organization_id
                == input_value.organization_id
            )
            .where(
                CompetencyEvidenceRecord.outcome_id
                == input_value.supersedes_outcome_id
            )
            .where(
                CompetencyEvidenceRecord.competency_revision_id
                == competency_revision_id
            )
            .order_by(CompetencyEvidenceRecord.outcome_version.desc())
            .limit(1)
        )
        return row

    @staticmethod
    def _initial_validity(
        input_value: OutcomeEvidenceInput,
        revision: CanonicalCompetencyRevision,
    ) -> tuple[str, str]:
        if input_value.lifecycle_result in {"invalidated", "cancelled"}:
            return "invalidated", "invalid"
        if input_value.lifecycle_result != "completed":
            return "insufficient_quality", "invalid"
        if input_value.assessment_result == "needs_review":
            return "pending_review", "unscorable"
        minimum_confidence = float(
            revision.minimum_requirements_json.get("minimum_confidence", 0.6)
        )
        if (
            input_value.degradations
            or (
                input_value.confidence is not None
                and input_value.confidence < minimum_confidence
            )
        ):
            return "insufficient_quality", "degraded"
        return "valid", "verified"

    async def _project_rows(
        self, rows: Sequence[CompetencyEvidenceRecord]
    ) -> tuple[CompetencyEvidenceProjection, ...]:
        if not rows:
            return ()
        evidence_ids = [row.evidence_id for row in rows]
        replacement_ids = {
            str(item)
            for item in (
                await self._session.scalars(
                    select(CompetencyEvidenceRecord.supersedes_evidence_id).where(
                        CompetencyEvidenceRecord.supersedes_evidence_id.in_(evidence_ids)
                    )
                )
            ).all()
            if item is not None
        }
        validity_events = list(
            (
                await self._session.execute(
                    select(CompetencyEvidenceValidityEvent)
                    .where(
                        CompetencyEvidenceValidityEvent.evidence_id.in_(evidence_ids)
                    )
                    .order_by(CompetencyEvidenceValidityEvent.created_at.asc())
                )
            ).scalars()
        )
        latest_event = {item.evidence_id: item for item in validity_events}
        revision_ids = {row.competency_revision_id for row in rows}
        revisions = {
            item.revision_id: item
            for item in (
                await self._session.scalars(
                    select(CanonicalCompetencyRevision).where(
                        CanonicalCompetencyRevision.revision_id.in_(revision_ids)
                    )
                )
            ).all()
        }
        projections: list[CompetencyEvidenceProjection] = []
        for row in rows:
            validity = row.initial_validity
            event = latest_event.get(row.evidence_id)
            if event is not None:
                validity = (
                    row.initial_validity
                    if event.status == "restored"
                    else "invalidated"
                )
            if row.evidence_id in replacement_ids:
                validity = "superseded"
            revision = revisions[row.competency_revision_id]
            projections.append(
                CompetencyEvidenceProjection(
                    evidence_id=row.evidence_id,
                    organization_id=row.organization_id,
                    learner_id=row.learner_id,
                    enrollment_id=row.enrollment_id,
                    competency_revision_id=row.competency_revision_id,
                    competency_key=row.competency_key,
                    competency_title=revision.title,
                    source_activity_id=row.source_activity_id,
                    attempt_id=row.attempt_id,
                    outcome_id=row.outcome_id,
                    outcome_version=row.outcome_version,
                    evidence_type=row.evidence_type,
                    evidence_role=row.evidence_role,
                    observed_score=(
                        float(row.observed_score)
                        if row.observed_score is not None
                        else None
                    ),
                    observed_max_score=(
                        float(row.observed_max_score)
                        if row.observed_max_score is not None
                        else None
                    ),
                    observed_result=row.observed_result,
                    confidence=(
                        float(row.confidence) if row.confidence is not None else None
                    ),
                    quality=row.quality,
                    validity=validity,
                    source_refs=tuple(dict(item) for item in row.source_refs_json),
                    lineage=dict(row.lineage_json),
                    critical_flags=tuple(row.critical_flags_json),
                    degradations=tuple(row.degradations_json),
                    supersedes_evidence_id=row.supersedes_evidence_id,
                    observed_at=row.observed_at,
                )
            )
        return tuple(projections)


__all__ = ["CompetencyEvidenceService"]
