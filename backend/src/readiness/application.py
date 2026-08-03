"""Single readiness writer for dossiers, snapshots, decisions, and follow-up."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from competency_evidence.identifiers import STANDARD_COMPETENCY_KEYS
from readiness.contracts import (
    AISummaryDraft,
    AppealInput,
    AppealResolutionInput,
    CalibrationSessionInput,
    ExceptionDecisionPreviewInput,
    ReadinessActor,
    ReadinessProjectionInput,
    RetrainingAssignmentInput,
    ReviewDecisionInput,
)
from readiness.errors import ReadinessError
from readiness.models import (
    ReadinessAISummary,
    ReadinessAppeal,
    ReadinessCalibrationSession,
    ReadinessCommandAudit,
    ReadinessDossier,
    ReadinessDossierSnapshot,
    ReadinessExceptionPreview,
    ReadinessPolicyRevision,
    ReadinessRetrainingAssignment,
    ReadinessReviewDecision,
)
from readiness.policy import (
    canonical_hash,
    evaluate_readiness,
    readiness_policy_snapshot,
)
from task_runtime.outbox import DomainEvent, SQLAlchemyOutboxWriter

POLICY_KEY = "newcomer-foundation-readiness-v1"
POLICY_REVISION_ID = str(
    uuid.uuid5(uuid.NAMESPACE_URL, f"readiness-policy:{POLICY_KEY}:1")
)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class ReadinessService:
    """Owns every formal readiness mutation and its audit/event lineage."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._outbox = SQLAlchemyOutboxWriter(session)

    async def authorize(
        self,
        *,
        actor: ReadinessActor,
        capability: str,
        object_type: str,
        object_id: str,
        command: str,
    ) -> None:
        """Apply and audit a capability gate for application-root commands."""

        await self._require_capability(
            actor,
            capability,
            object_type=object_type,
            object_id=object_id,
            command=command,
        )

    async def project(
        self,
        input_value: ReadinessProjectionInput,
        *,
        actor_id: str,
        trace_id: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        policy = await self._ensure_policy(actor_id=actor_id)
        result = evaluate_readiness(input_value)
        dossier = await self._session.scalar(
            select(ReadinessDossier)
            .where(
                ReadinessDossier.organization_id == input_value.organization_id
            )
            .where(ReadinessDossier.enrollment_id == input_value.enrollment_id)
            .with_for_update()
            .limit(1)
        )
        now = _now()
        if dossier is None:
            dossier = ReadinessDossier(
                dossier_id=_id(),
                organization_id=input_value.organization_id,
                enrollment_id=input_value.enrollment_id,
                learner_id=input_value.learner_id,
                path_revision_id=input_value.path_revision_id,
                state="projecting",
                version=1,
                created_at=now,
                updated_at=now,
            )
            self._session.add(dossier)
            await self._session.flush([dossier])
        elif (
            dossier.learner_id != input_value.learner_id
            or dossier.path_revision_id != input_value.path_revision_id
        ):
            raise ReadinessError(
                "[DOSSIER_SCOPE_CONFLICT]",
                "训练档案与当前分配版本不一致，需要管理员重建。",
                409,
            )

        await self._complete_retraining_assignments(
            dossier,
            input_value,
            actor_id=actor_id,
            trace_id=trace_id,
        )
        current_snapshot = (
            await self._session.get(
                ReadinessDossierSnapshot, dossier.current_snapshot_id
            )
            if dossier.current_snapshot_id is not None
            else None
        )
        changed = dossier.evidence_set_hash != result.evidence_set_hash
        if (
            current_snapshot is not None
            and changed
            and dossier.state in {"under_review", "decided", "stale"}
            and not force_refresh
        ):
            before_version = dossier.version
            if current_snapshot.stale_at is None:
                current_snapshot.stale_at = now
                current_snapshot.stale_reason = "复核材料冻结后收到新的有效证据或重评结果。"
            dossier.state = "stale"
            dossier.pending_evidence_set_hash = result.evidence_set_hash
            dossier.stale_reason = current_snapshot.stale_reason
            dossier.reopened_at = now
            dossier.version += 1
            dossier.updated_at = now
            await self._audit(
                organization_id=dossier.organization_id,
                actor_id=actor_id,
                capability="readiness.project",
                object_type="readiness_dossier",
                object_id=dossier.dossier_id,
                command="mark_dossier_stale",
                result="succeeded",
                before_version=before_version,
                after_version=dossier.version,
                reason=dossier.stale_reason,
                trace_id=trace_id,
                details={
                    "snapshot_id": current_snapshot.snapshot_id,
                    "pending_evidence_set_hash": result.evidence_set_hash,
                },
            )
            await self._event(
                dossier,
                event_type="DossierMarkedStale",
                actor_id=actor_id,
                trace_id=trace_id,
                payload={"snapshot_id": current_snapshot.snapshot_id},
            )
            await self._session.flush([dossier, current_snapshot])
            return await self._projection(dossier, learner_safe=False)

        if current_snapshot is not None and not changed and not force_refresh:
            return await self._projection(dossier, learner_safe=False)

        before_version = dossier.version
        if current_snapshot is not None and current_snapshot.stale_at is None:
            current_snapshot.stale_at = now
            current_snapshot.stale_reason = "已生成新的档案快照。"
        snapshot_version = int(
            await self._session.scalar(
                select(func.max(ReadinessDossierSnapshot.snapshot_version)).where(
                    ReadinessDossierSnapshot.dossier_id == dossier.dossier_id
                )
            )
            or 0
        ) + 1
        projection_payload = {
            "learner": {
                "learner_id": input_value.learner_id,
                "name": input_value.learner_name,
                "cohort_id": input_value.cohort_id,
                "cohort_name": input_value.cohort_name,
            },
            "path": {
                "path_revision_id": input_value.path_revision_id,
                "title": input_value.path_title,
                "revision_label": input_value.path_revision_label,
            },
            "enrollment_status": input_value.enrollment_status,
            "activities": [
                item.model_dump(mode="json") for item in input_value.activities
            ],
            "competencies": [
                item.model_dump(mode="json") for item in result.competencies
            ],
            "evidence": [
                item.model_dump(mode="json") for item in input_value.evidence
            ],
            "eligibility": result.eligibility.model_dump(mode="json"),
            "risk_band": result.risk_band,
            "risk_reasons": list(result.risk_reasons),
            "generated_at": input_value.generated_at.isoformat(),
        }
        snapshot = ReadinessDossierSnapshot(
            snapshot_id=_id(),
            organization_id=dossier.organization_id,
            dossier_id=dossier.dossier_id,
            snapshot_version=snapshot_version,
            evidence_set_hash=result.evidence_set_hash,
            evidence_ids_json=[item.evidence_id for item in input_value.evidence],
            competency_revision_ids_json=sorted(
                {item.competency_revision_id for item in input_value.evidence}
            ),
            readiness_policy_revision_id=policy.policy_revision_id,
            path_revision_id=input_value.path_revision_id,
            projection_json=projection_payload,
            ai_summary_revision_id=None,
            created_by=actor_id,
            created_at=now,
        )
        self._session.add(snapshot)
        await self._session.flush([snapshot])
        dossier.current_snapshot_id = snapshot.snapshot_id
        dossier.evidence_set_hash = result.evidence_set_hash
        dossier.pending_evidence_set_hash = None
        dossier.state = (
            "ready_for_review" if result.eligibility.eligible else "incomplete"
        )
        dossier.stale_reason = None
        if force_refresh:
            dossier.active_decision_id = None
        dossier.version += 1
        dossier.updated_at = now
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor_id,
            capability="readiness.project",
            object_type="readiness_dossier",
            object_id=dossier.dossier_id,
            command="rebuild_dossier" if force_refresh else "project_dossier",
            result="succeeded",
            before_version=before_version,
            after_version=dossier.version,
            trace_id=trace_id,
            details={
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_version": snapshot.snapshot_version,
                "eligible": result.eligibility.eligible,
            },
        )
        await self._event(
            dossier,
            event_type="DossierRebuilt" if force_refresh else "DossierProjected",
            actor_id=actor_id,
            trace_id=trace_id,
            payload={
                "snapshot_id": snapshot.snapshot_id,
                "state": dossier.state,
            },
        )
        await self._session.flush([dossier, snapshot])
        return await self._projection(dossier, learner_safe=False)

    async def get_by_enrollment(
        self,
        *,
        actor: ReadinessActor,
        enrollment_id: str,
        learner_safe: bool,
    ) -> dict[str, Any]:
        dossier = await self._session.scalar(
            select(ReadinessDossier)
            .where(ReadinessDossier.organization_id == actor.organization_id)
            .where(ReadinessDossier.enrollment_id == enrollment_id)
            .limit(1)
        )
        if dossier is None:
            await self._reject_audit(
                actor=actor,
                dossier=None,
                capability=(
                    "readiness.self.read"
                    if learner_safe
                    else "readiness.dossier.read"
                ),
                command="read_dossier",
                reason="对象不存在或跨组织访问。",
                object_id=enrollment_id,
            )
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]",
                "训练档案尚未生成。",
                404,
                audit_persisted=True,
            )
        await self._require_dossier_access(
            actor,
            dossier,
            capability=("readiness.self.read" if learner_safe else "readiness.dossier.read"),
            command="read_dossier",
        )
        return await self._projection(
            dossier,
            learner_safe=learner_safe,
            actor=actor,
        )

    async def get_by_id(
        self,
        *,
        actor: ReadinessActor,
        dossier_id: str,
        learner_safe: bool = False,
    ) -> dict[str, Any]:
        dossier = await self._session.get(ReadinessDossier, dossier_id)
        if dossier is None or dossier.organization_id != actor.organization_id:
            await self._reject_audit(
                actor=actor,
                dossier=None,
                capability=(
                    "readiness.self.read"
                    if learner_safe
                    else "readiness.dossier.read"
                ),
                command="read_dossier",
                reason="对象不存在或跨组织访问。",
                object_id=dossier_id,
            )
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]",
                "训练档案不存在或不可访问。",
                404,
                audit_persisted=True,
            )
        await self._require_dossier_access(
            actor,
            dossier,
            capability=("readiness.self.read" if learner_safe else "readiness.dossier.read"),
            command="read_dossier",
        )
        return await self._projection(
            dossier,
            learner_safe=learner_safe,
            actor=actor,
        )

    async def list_queue(
        self,
        *,
        actor: ReadinessActor,
        state: str | None = None,
        cohort_id: str | None = None,
        competency_key: str | None = None,
        reviewer_id: str | None = None,
        waiting_hours_gte: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        await self._require_capability(
            actor,
            "readiness.queue.read",
            object_type="readiness_queue",
            object_id=actor.organization_id,
            command="list_review_queue",
        )
        query = select(ReadinessDossier).where(
            ReadinessDossier.organization_id == actor.organization_id
        )
        if not actor.unrestricted_scope:
            query = query.where(ReadinessDossier.learner_id.in_(actor.learner_ids))
        if state:
            query = query.where(ReadinessDossier.state == state)
        dossiers = list((await self._session.execute(query)).scalars())
        items: list[dict[str, Any]] = []
        for dossier in dossiers:
            projection = await self._projection(
                dossier,
                learner_safe=False,
                actor=actor,
            )
            if cohort_id and projection["learner"].get("cohort_id") != cohort_id:
                continue
            if waiting_hours_gte is not None:
                waiting_hours = (
                    _now() - _aware(dossier.updated_at)
                ).total_seconds() / 3600
                if waiting_hours < waiting_hours_gte:
                    continue
            competencies = projection["competencies"]
            if competency_key and not any(
                item["competency_key"] == competency_key
                and item["status"] != "sufficient"
                for item in competencies
            ):
                continue
            decision = projection.get("human_decision")
            if reviewer_id and (
                decision is None or decision.get("reviewer_id") != reviewer_id
            ):
                continue
            risk_rank = {"high": 0, "medium": 1, "low": 2}.get(
                projection["summary"].get("risk_band"), 3
            )
            queue_reason = self._queue_reason(projection)
            items.append(
                {
                    "object_id": dossier.dossier_id,
                    "object_summary": {
                        "learner": projection["learner"],
                        "path": projection["path"],
                        "status": projection["status"],
                    },
                    "queue_reason": queue_reason,
                    "risk_band": projection["summary"].get("risk_band"),
                    "evidence_gaps": projection["summary"]["eligibility"].get(
                        "competency_gaps", []
                    ),
                    "reviewer_id": decision.get("reviewer_id") if decision else None,
                    "due_at": None,
                    "primary_action": {
                        "label": "复核训练档案",
                        "href": (
                            "/admin/newcomer-training/reviews/"
                            f"{dossier.dossier_id}"
                        ),
                    },
                    "capabilities": sorted(actor.capabilities),
                    "updated_at": dossier.updated_at,
                    "_risk_rank": risk_rank,
                }
            )
        items.sort(key=lambda item: (item["_risk_rank"], item["updated_at"]))
        total = len(items)
        page_items = items[offset : offset + limit]
        for item in page_items:
            item.pop("_risk_rank", None)
        return {
            "contract_version": "1",
            "generated_at": _now(),
            "data_freshness": "fresh",
            "capabilities": sorted(actor.capabilities),
            "items": page_items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "applied_filters": {
                "state": state,
                "cohort_id": cohort_id,
                "competency_key": competency_key,
                "reviewer_id": reviewer_id,
                "waiting_hours_gte": waiting_hours_gte,
            },
            "sort": ["risk_desc", "waiting_time_desc"],
        }

    async def preview_exception_decision(
        self,
        *,
        actor: ReadinessActor,
        dossier_id: str,
        command: ExceptionDecisionPreviewInput,
        idempotency_key: str,
    ) -> dict[str, Any]:
        dossier = await self._load_for_command(
            actor=actor,
            dossier_id=dossier_id,
            capability="readiness.review",
            command="preview_exception_decision",
        )
        fingerprint = _fingerprint(command.model_dump(mode="json"))
        key_hash = _secret_hash(idempotency_key)
        token = _fingerprint(
            {
                "purpose": "readiness-exception-preview",
                "organization_id": actor.organization_id,
                "dossier_id": dossier.dossier_id,
                "reviewer_id": actor.actor_id,
                "idempotency_key": idempotency_key,
            }
        )
        existing = await self._session.scalar(
            select(ReadinessExceptionPreview)
            .where(
                ReadinessExceptionPreview.organization_id
                == dossier.organization_id
            )
            .where(ReadinessExceptionPreview.dossier_id == dossier.dossier_id)
            .where(ReadinessExceptionPreview.idempotency_key_hash == key_hash)
            .limit(1)
        )
        if existing is not None:
            if existing.command_fingerprint != fingerprint:
                self._idempotency_conflict()
            return self._exception_preview_payload(existing, preview_token=token)

        snapshot = await self._require_current_snapshot(
            actor=actor,
            dossier=dossier,
            snapshot_id=command.snapshot_id,
            expected_version=command.expected_dossier_version,
            capability="readiness.review",
            command="preview_exception_decision",
        )
        await self._validate_snapshot_references(
            snapshot,
            competency_keys=command.competency_keys,
            evidence_ids=command.evidence_ids,
        )
        impact = self._exception_impact(
            dossier=dossier,
            snapshot=snapshot,
            reason=command.reason,
            notes=command.notes,
            competency_keys=command.competency_keys,
            evidence_ids=command.evidence_ids,
        )
        impact_hash = _fingerprint(impact)
        now = _now()
        row = ReadinessExceptionPreview(
            preview_id=_id(),
            organization_id=dossier.organization_id,
            dossier_id=dossier.dossier_id,
            snapshot_id=snapshot.snapshot_id,
            dossier_version=dossier.version,
            reviewer_id=actor.actor_id,
            impact_json=impact,
            impact_hash=impact_hash,
            preview_token_hash=_secret_hash(token),
            idempotency_key_hash=key_hash,
            command_fingerprint=fingerprint,
            status="previewed",
            expires_at=now + timedelta(minutes=15),
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush([row])
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.review",
            object_type="readiness_dossier",
            object_id=dossier.dossier_id,
            command="preview_exception_decision",
            result="succeeded",
            before_version=dossier.version,
            after_version=dossier.version,
            idempotency_key=idempotency_key,
            trace_id=actor.trace_id,
            details={
                "preview_id": row.preview_id,
                "snapshot_id": row.snapshot_id,
                "impact_hash": row.impact_hash,
                "expires_at": row.expires_at.isoformat(),
            },
        )
        return self._exception_preview_payload(row, preview_token=token)

    async def record_decision(
        self,
        *,
        actor: ReadinessActor,
        dossier_id: str,
        command: ReviewDecisionInput,
        idempotency_key: str,
    ) -> dict[str, Any]:
        dossier = await self._load_for_command(
            actor=actor,
            dossier_id=dossier_id,
            capability="readiness.review",
            command="record_review_decision",
        )
        fingerprint = _fingerprint(command.model_dump(mode="json"))
        existing = await self._decision_replay(
            dossier=dossier,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if existing is not None:
            return self._decision_payload(existing)
        snapshot = await self._require_current_snapshot(
            actor=actor,
            dossier=dossier,
            snapshot_id=command.snapshot_id,
            expected_version=command.expected_dossier_version,
            capability="readiness.review",
            command="record_review_decision",
        )
        eligibility = dict(snapshot.projection_json.get("eligibility") or {})
        blocking_assignment = await self._session.scalar(
            select(ReadinessRetrainingAssignment.assignment_id)
            .where(ReadinessRetrainingAssignment.dossier_id == dossier.dossier_id)
            .where(
                ReadinessRetrainingAssignment.status.in_(
                    ("assigned", "draft_pending_governance")
                )
            )
            .limit(1)
        )
        blocking_appeal = await self._session.scalar(
            select(ReadinessAppeal.appeal_id)
            .where(ReadinessAppeal.dossier_id == dossier.dossier_id)
            .where(
                ReadinessAppeal.status.in_(
                    ("submitted", "under_review", "regrade_pending")
                )
            )
            .limit(1)
        )
        if command.decision_type in {
            "approve_foundation_ready",
            "exception_approved",
        } and (blocking_assignment is not None or blocking_appeal is not None):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="仍有补充训练或申诉处理事项未关闭。",
            )
            raise ReadinessError(
                "[DOSSIER_BLOCKING_FOLLOW_UP]",
                "仍有补充训练或申诉处理事项未关闭，暂不能确认基础训练达标。",
                409,
                audit_persisted=True,
            )
        if command.decision_type == "approve_foundation_ready" and not eligibility.get(
            "eligible"
        ):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="当前档案尚未满足复核前置条件。",
            )
            raise ReadinessError(
                "[DOSSIER_NOT_ELIGIBLE]",
                "当前档案尚未满足基础训练达标前置条件。",
                409,
                details={"eligibility": eligibility},
                audit_persisted=True,
            )
        if command.decision_type in {
            "approve_foundation_ready",
            "exception_approved",
        } and (not command.competency_keys or not command.evidence_ids):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="正式达标结论缺少当前快照的能力或证据引用。",
            )
            raise ReadinessError(
                "[DOSSIER_DECISION_REFERENCES_REQUIRED]",
                "正式达标结论必须引用当前快照中的能力和证据。",
                422,
                audit_persisted=True,
            )
        await self._validate_snapshot_references(
            snapshot,
            competency_keys=command.competency_keys,
            evidence_ids=command.evidence_ids,
        )
        if command.decision_type == "exception_approved":
            await self._consume_exception_preview(
                actor=actor,
                dossier=dossier,
                snapshot=snapshot,
                command=command,
            )
        now = _now()
        previous = (
            await self._session.get(
                ReadinessReviewDecision, dossier.active_decision_id
            )
            if dossier.active_decision_id is not None
            else None
        )
        if previous is not None:
            previous.status = "superseded"
            previous.superseded_at = now
        before_version = dossier.version
        row = ReadinessReviewDecision(
            decision_id=_id(),
            organization_id=dossier.organization_id,
            dossier_id=dossier.dossier_id,
            snapshot_id=snapshot.snapshot_id,
            dossier_version=dossier.version,
            decision_type=command.decision_type,
            status="recorded",
            reviewer_id=actor.actor_id,
            competency_keys_json=list(command.competency_keys),
            evidence_ids_json=list(command.evidence_ids),
            reason=command.reason.strip(),
            notes=command.notes.strip() if command.notes else None,
            supersedes_decision_id=(previous.decision_id if previous else None),
            idempotency_key_hash=_secret_hash(idempotency_key),
            command_fingerprint=fingerprint,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush([row])
        dossier.active_decision_id = row.decision_id
        dossier.state = "decided"
        dossier.version += 1
        dossier.updated_at = now
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.review",
            object_type="readiness_dossier",
            object_id=dossier.dossier_id,
            command="record_review_decision",
            result="succeeded",
            reason=row.reason,
            before_version=before_version,
            after_version=dossier.version,
            idempotency_key=idempotency_key,
            trace_id=actor.trace_id,
            details={
                "decision_id": row.decision_id,
                "decision_type": row.decision_type,
                "snapshot_id": row.snapshot_id,
                "supersedes_decision_id": row.supersedes_decision_id,
            },
        )
        await self._event(
            dossier,
            event_type="ReviewDecisionRecorded",
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
            payload={
                "decision_id": row.decision_id,
                "decision_type": row.decision_type,
                "snapshot_id": row.snapshot_id,
            },
        )
        await self._session.flush([dossier, row])
        return self._decision_payload(row)

    async def assign_retraining(
        self,
        *,
        actor: ReadinessActor,
        dossier_id: str,
        command: RetrainingAssignmentInput,
        idempotency_key: str,
    ) -> dict[str, Any]:
        dossier = await self._load_for_command(
            actor=actor,
            dossier_id=dossier_id,
            capability="readiness.retraining.assign",
            command="assign_retraining",
        )
        fingerprint = _fingerprint(command.model_dump(mode="json"))
        key_hash = _secret_hash(idempotency_key)
        existing = await self._session.scalar(
            select(ReadinessRetrainingAssignment)
            .where(
                ReadinessRetrainingAssignment.organization_id
                == dossier.organization_id
            )
            .where(ReadinessRetrainingAssignment.dossier_id == dossier.dossier_id)
            .where(
                ReadinessRetrainingAssignment.idempotency_key_hash == key_hash
            )
            .limit(1)
        )
        if existing is not None:
            if existing.command_fingerprint != fingerprint:
                self._idempotency_conflict()
            return self._retraining_payload(existing)
        snapshot = await self._require_current_snapshot(
            actor=actor,
            dossier=dossier,
            snapshot_id=command.snapshot_id,
            expected_version=command.expected_dossier_version,
            capability="readiness.retraining.assign",
            command="assign_retraining",
        )
        await self._validate_snapshot_references(
            snapshot,
            competency_keys=command.target_competency_keys,
            evidence_ids=command.source_evidence_ids,
        )
        if command.activity_source == "existing_published" and not command.activity_id:
            raise ReadinessError(
                "[RETRAINING_ACTIVITY_REQUIRED]",
                "请选择一个已发布的训练活动。",
                422,
            )
        if command.activity_source == "quick_draft" and not command.activity_draft:
            raise ReadinessError(
                "[RETRAINING_DRAFT_REQUIRED]",
                "请填写最小补练草稿。",
                422,
            )
        row = ReadinessRetrainingAssignment(
            assignment_id=_id(),
            organization_id=dossier.organization_id,
            dossier_id=dossier.dossier_id,
            enrollment_id=dossier.enrollment_id,
            learner_id=dossier.learner_id,
            source_snapshot_id=snapshot.snapshot_id,
            activity_source=command.activity_source,
            activity_id=command.activity_id,
            activity_title=command.activity_title,
            activity_draft_json=command.activity_draft,
            target_competency_keys_json=list(command.target_competency_keys),
            source_evidence_ids_json=list(command.source_evidence_ids),
            reason=command.reason.strip(),
            due_at=command.due_at,
            completion_rule_json=command.completion_rule,
            status=(
                "assigned"
                if command.activity_source == "existing_published"
                else "draft_pending_governance"
            ),
            version=1,
            completed_outcome_ids_json=[],
            idempotency_key_hash=key_hash,
            command_fingerprint=fingerprint,
            created_by=actor.actor_id,
            assigned_at=_now(),
        )
        self._session.add(row)
        before_version = dossier.version
        dossier.version += 1
        dossier.updated_at = _now()
        await self._session.flush([row, dossier])
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.retraining.assign",
            object_type="retraining_assignment",
            object_id=row.assignment_id,
            command="assign_retraining",
            result="succeeded",
            reason=row.reason,
            before_version=before_version,
            after_version=dossier.version,
            idempotency_key=idempotency_key,
            trace_id=actor.trace_id,
            details={
                "dossier_id": dossier.dossier_id,
                "activity_source": row.activity_source,
                "activity_id": row.activity_id,
                "target_competency_keys": row.target_competency_keys_json,
            },
        )
        await self._event(
            dossier,
            event_type="RetrainingAssigned",
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
            payload={
                "assignment_id": row.assignment_id,
                "activity_id": row.activity_id,
                "status": row.status,
            },
        )
        return self._retraining_payload(row)

    async def submit_appeal(
        self,
        *,
        actor: ReadinessActor,
        enrollment_id: str,
        command: AppealInput,
        idempotency_key: str,
    ) -> dict[str, Any]:
        dossier = await self._session.scalar(
            select(ReadinessDossier)
            .where(ReadinessDossier.organization_id == actor.organization_id)
            .where(ReadinessDossier.enrollment_id == enrollment_id)
            .with_for_update()
            .limit(1)
        )
        if dossier is None:
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]", "训练档案尚未生成。", 404
            )
        await self._require_dossier_access(
            actor,
            dossier,
            capability="readiness.appeal.submit",
            command="submit_appeal",
        )
        if actor.actor_id != dossier.learner_id:
            raise ReadinessError(
                "[APPEAL_LEARNER_MISMATCH]", "只能为自己的训练档案提交申诉。", 404
            )
        if dossier.version != command.dossier_version:
            raise ReadinessError(
                "[DOSSIER_VERSION_CONFLICT]",
                "训练档案已更新，请刷新后重新提交申诉。",
                412,
                details={"actual_version": dossier.version},
            )
        fingerprint = _fingerprint(command.model_dump(mode="json"))
        key_hash = _secret_hash(idempotency_key)
        existing = await self._session.scalar(
            select(ReadinessAppeal)
            .where(ReadinessAppeal.organization_id == dossier.organization_id)
            .where(ReadinessAppeal.learner_id == dossier.learner_id)
            .where(ReadinessAppeal.idempotency_key_hash == key_hash)
            .limit(1)
        )
        if existing is not None:
            if existing.command_fingerprint != fingerprint:
                self._idempotency_conflict()
            return self._appeal_payload(existing)
        await self._require_appeal_target(dossier, command)
        row = ReadinessAppeal(
            appeal_id=_id(),
            organization_id=dossier.organization_id,
            dossier_id=dossier.dossier_id,
            learner_id=dossier.learner_id,
            target_type=command.target_type,
            target_id=command.target_id,
            dossier_version=command.dossier_version,
            reason_category=command.reason_category,
            statement=command.statement.strip(),
            status="submitted",
            version=1,
            idempotency_key_hash=key_hash,
            command_fingerprint=fingerprint,
            created_at=_now(),
            updated_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.appeal.submit",
            object_type="readiness_appeal",
            object_id=row.appeal_id,
            command="submit_appeal",
            result="succeeded",
            idempotency_key=idempotency_key,
            trace_id=actor.trace_id,
            details={
                "dossier_id": dossier.dossier_id,
                "target_type": row.target_type,
                "target_id": row.target_id,
            },
        )
        await self._event(
            dossier,
            event_type="ReadinessAppealSubmitted",
            actor_id=actor.actor_id,
            trace_id=actor.trace_id,
            payload={"appeal_id": row.appeal_id, "target_type": row.target_type},
        )
        return self._appeal_payload(row)

    async def resolve_appeal(
        self,
        *,
        actor: ReadinessActor,
        appeal_id: str,
        command: AppealResolutionInput,
    ) -> dict[str, Any]:
        appeal = await self._session.scalar(
            select(ReadinessAppeal)
            .where(ReadinessAppeal.appeal_id == appeal_id)
            .with_for_update()
            .limit(1)
        )
        if appeal is None or appeal.organization_id != actor.organization_id:
            raise ReadinessError(
                "[APPEAL_NOT_FOUND]", "申诉不存在或不可访问。", 404
            )
        dossier = await self._load_for_command(
            actor=actor,
            dossier_id=appeal.dossier_id,
            capability="readiness.appeal.resolve",
            command="resolve_appeal",
        )
        if appeal.version != command.expected_version:
            raise ReadinessError(
                "[APPEAL_VERSION_CONFLICT]",
                "申诉已更新，请刷新后继续。",
                412,
            )
        status_by_action = {
            "begin_review": "under_review",
            "request_regrade": "regrade_pending",
            "resolve": "resolved",
            "reject": "rejected",
            "reopen_review": "resolved",
        }
        appeal.status = status_by_action[command.action]
        appeal.assigned_to = actor.actor_id
        appeal.resolution = command.resolution.strip()
        appeal.version += 1
        appeal.updated_at = _now()
        if appeal.status in {"resolved", "rejected"}:
            appeal.resolved_at = _now()
        if command.action == "reopen_review":
            dossier.state = "stale"
            dossier.stale_reason = "申诉处理要求重新复核训练档案。"
            dossier.reopened_at = _now()
            dossier.version += 1
            snapshot = (
                await self._session.get(
                    ReadinessDossierSnapshot, dossier.current_snapshot_id
                )
                if dossier.current_snapshot_id
                else None
            )
            if snapshot is not None and snapshot.stale_at is None:
                snapshot.stale_at = _now()
                snapshot.stale_reason = dossier.stale_reason
        await self._session.flush([appeal, dossier])
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.appeal.resolve",
            object_type="readiness_appeal",
            object_id=appeal.appeal_id,
            command=command.action,
            result="succeeded",
            reason=command.resolution,
            after_version=appeal.version,
            trace_id=actor.trace_id,
            details={"status": appeal.status, "dossier_id": dossier.dossier_id},
        )
        return self._appeal_payload(appeal)

    async def record_ai_summary(
        self,
        *,
        actor_id: str,
        dossier_id: str,
        snapshot_id: str,
        draft: AISummaryDraft | None,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        dossier = await self._session.get(ReadinessDossier, dossier_id)
        snapshot = await self._session.get(ReadinessDossierSnapshot, snapshot_id)
        if (
            dossier is None
            or snapshot is None
            or snapshot.dossier_id != dossier_id
            or snapshot.organization_id != dossier.organization_id
        ):
            raise ReadinessError(
                "[DOSSIER_SNAPSHOT_NOT_FOUND]", "训练档案快照不存在。", 404
            )
        revision_no = int(
            await self._session.scalar(
                select(func.max(ReadinessAISummary.revision_no)).where(
                    ReadinessAISummary.snapshot_id == snapshot_id
                )
            )
            or 0
        ) + 1
        allowed_ids = set(snapshot.evidence_ids_json)
        referenced = (
            {
                evidence_id
                for fact in draft.facts
                for evidence_id in fact.evidence_ids
            }
            if draft is not None
            else set()
        )
        if draft is None:
            status = "failed"
            final_error = error_code or "summary_generation_failed"
            payload = None
        elif not referenced or not referenced.issubset(allowed_ids):
            status = "rejected"
            final_error = "summary_evidence_reference_invalid"
            payload = None
        else:
            status = "ready"
            final_error = None
            payload = draft.model_dump(mode="json")
        row = ReadinessAISummary(
            summary_id=_id(),
            organization_id=dossier.organization_id,
            dossier_id=dossier_id,
            snapshot_id=snapshot_id,
            revision_no=revision_no,
            status=status,
            payload_json=payload,
            evidence_ids_json=sorted(referenced),
            error_code=final_error,
            created_by=actor_id,
            created_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        if status == "ready" and snapshot.stale_at is None:
            snapshot.ai_summary_revision_id = row.summary_id
        await self._session.flush([snapshot])
        return self._summary_payload(row)

    async def create_calibration_session(
        self,
        *,
        actor: ReadinessActor,
        command: CalibrationSessionInput,
    ) -> dict[str, Any]:
        await self._require_capability(
            actor,
            "readiness.calibration",
            object_type="calibration_session",
            object_id=command.competency_key,
            command="create_calibration_session",
        )
        if command.competency_key not in STANDARD_COMPETENCY_KEYS:
            raise ReadinessError(
                "[CALIBRATION_COMPETENCY_UNKNOWN]",
                "校准能力不在首发标准目录中。",
                422,
            )
        decisions = list(
            (
                await self._session.execute(
                    select(ReadinessReviewDecision).where(
                        ReadinessReviewDecision.organization_id
                        == actor.organization_id
                    )
                )
            ).scalars()
        )
        relevant = [
            item
            for item in decisions
            if not item.competency_keys_json
            or command.competency_key in item.competency_keys_json
        ]
        distribution = Counter(item.decision_type for item in relevant)
        disagreements = [
            {
                "dossier_id": dossier_id,
                "decision_types": sorted(types),
            }
            for dossier_id, types in self._decision_types_by_dossier(relevant).items()
            if len(types) > 1
        ]
        row = ReadinessCalibrationSession(
            session_id=_id(),
            organization_id=actor.organization_id,
            competency_key=command.competency_key,
            status="open",
            sample_evidence_ids_json=list(command.sample_evidence_ids),
            decision_distribution_json=dict(distribution),
            disagreements_json=disagreements,
            action_items_json=list(command.action_items),
            created_by=actor.actor_id,
            created_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])
        await self._audit(
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.calibration",
            object_type="calibration_session",
            object_id=row.session_id,
            command="create_calibration_session",
            result="succeeded",
            trace_id=actor.trace_id,
            details={"competency_key": row.competency_key},
        )
        return {
            "session_id": row.session_id,
            "competency_key": row.competency_key,
            "status": row.status,
            "sample_evidence_ids": row.sample_evidence_ids_json,
            "decision_distribution": row.decision_distribution_json,
            "disagreements": row.disagreements_json,
            "action_items": row.action_items_json,
            "created_at": row.created_at,
        }

    async def export_dossier(
        self,
        *,
        actor: ReadinessActor,
        dossier_id: str,
    ) -> dict[str, Any]:
        dossier = await self._load_for_command(
            actor=actor,
            dossier_id=dossier_id,
            capability="readiness.export",
            command="export_dossier",
        )
        projection = await self._projection(
            dossier,
            learner_safe=False,
            actor=actor,
        )
        exported_at = _now()
        await self._audit(
            organization_id=dossier.organization_id,
            actor_id=actor.actor_id,
            capability="readiness.export",
            object_type="readiness_dossier",
            object_id=dossier.dossier_id,
            command="export_dossier",
            result="succeeded",
            trace_id=actor.trace_id,
            details={"watermarked": True, "exported_at": exported_at.isoformat()},
        )
        return {
            "watermark": {
                "exported_by": actor.actor_id,
                "exported_at": exported_at,
                "classification": "内部培训资料",
            },
            "dossier": projection,
        }

    async def _projection(
        self,
        dossier: ReadinessDossier,
        *,
        learner_safe: bool,
        actor: ReadinessActor | None = None,
    ) -> dict[str, Any]:
        snapshot = (
            await self._session.get(
                ReadinessDossierSnapshot, dossier.current_snapshot_id
            )
            if dossier.current_snapshot_id is not None
            else None
        )
        if snapshot is None:
            raise ReadinessError(
                "[DOSSIER_PROJECTION_PENDING]",
                "训练档案正在生成，请稍后刷新。",
                409,
            )
        projection = dict(snapshot.projection_json)
        decisions = list(
            (
                await self._session.execute(
                    select(ReadinessReviewDecision)
                    .where(ReadinessReviewDecision.dossier_id == dossier.dossier_id)
                    .order_by(ReadinessReviewDecision.created_at.desc())
                )
            ).scalars()
        )
        assignments = list(
            (
                await self._session.execute(
                    select(ReadinessRetrainingAssignment)
                    .where(
                        ReadinessRetrainingAssignment.dossier_id
                        == dossier.dossier_id
                    )
                    .order_by(ReadinessRetrainingAssignment.assigned_at.desc())
                )
            ).scalars()
        )
        appeals = list(
            (
                await self._session.execute(
                    select(ReadinessAppeal)
                    .where(ReadinessAppeal.dossier_id == dossier.dossier_id)
                    .order_by(ReadinessAppeal.created_at.desc())
                )
            ).scalars()
        )
        summary = (
            await self._session.get(ReadinessAISummary, snapshot.ai_summary_revision_id)
            if snapshot.ai_summary_revision_id
            else None
        )
        active_decision = next(
            (
                item
                for item in decisions
                if item.decision_id == dossier.active_decision_id
            ),
            None,
        )
        eligibility = dict(projection.get("eligibility") or {})
        safe_summary = {
            "eligibility": eligibility,
            "completed_required_activities": sum(
                1
                for item in projection.get("activities", [])
                if item.get("required") and item.get("status") == "completed"
            ),
            "total_required_activities": sum(
                1 for item in projection.get("activities", []) if item.get("required")
            ),
            "evidence_count": len(projection.get("evidence", [])),
            "stale_reason": dossier.stale_reason,
        }
        if not learner_safe:
            safe_summary.update(
                risk_band=projection.get("risk_band"),
                risk_reasons=projection.get("risk_reasons", []),
            )
        return {
            "contract_version": "1",
            "generated_at": _now(),
            "data_freshness": "stale" if dossier.state == "stale" else "fresh",
            "capabilities": self._projection_capabilities(
                dossier,
                learner_safe,
                actor,
            ),
            "dossier_id": dossier.dossier_id,
            "dossier_version": dossier.version,
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_version": snapshot.snapshot_version,
            "snapshot_stale": dossier.state == "stale",
            "learner": projection.get("learner", {}),
            "path": projection.get("path", {}),
            "status": dossier.state,
            "status_label": self._status_label(dossier.state),
            "summary": safe_summary,
            "competencies": projection.get("competencies", []),
            "evidence": (
                [
                    self._learner_evidence_payload(item)
                    for item in projection.get("evidence", [])
                ]
                if learner_safe
                else projection.get("evidence", [])
            ),
            "activities": (
                projection.get("activities", []) if not learner_safe else []
            ),
            "ai_assessment": (
                self._summary_payload(summary, learner_safe=learner_safe)
                if summary is not None
                else {
                    "status": "not_generated",
                    "label": "未生成辅助摘要",
                    "message": "可直接依据确定性档案完成人工复核。",
                }
            ),
            "human_decision": (
                self._decision_payload(
                    active_decision,
                    learner_safe=learner_safe,
                )
                if active_decision is not None
                else None
            ),
            "decision_history": [
                self._decision_payload(item, learner_safe=learner_safe)
                for item in decisions
            ],
            "retraining": [self._retraining_payload(item) for item in assignments],
            "appeals": [self._appeal_payload(item) for item in appeals],
            "next_actions": self._next_actions(
                dossier=dossier,
                eligibility=eligibility,
                assignments=assignments,
                learner_safe=learner_safe,
            ),
        }

    async def _ensure_policy(self, *, actor_id: str) -> ReadinessPolicyRevision:
        snapshot = readiness_policy_snapshot()
        expected_hash = canonical_hash(snapshot)
        row = await self._session.get(ReadinessPolicyRevision, POLICY_REVISION_ID)
        if row is None:
            row = ReadinessPolicyRevision(
                policy_revision_id=POLICY_REVISION_ID,
                stable_key=POLICY_KEY,
                revision_no=1,
                status="published",
                snapshot_json=snapshot,
                content_hash=expected_hash,
                created_by=actor_id,
                created_at=_now(),
            )
            self._session.add(row)
            await self._session.flush([row])
        elif row.content_hash != expected_hash or row.status != "published":
            raise ReadinessError(
                "[READINESS_POLICY_DRIFT]",
                "达标策略与冻结修订不一致，已停止生成新档案。",
                409,
            )
        return row

    async def _load_for_command(
        self,
        *,
        actor: ReadinessActor,
        dossier_id: str,
        capability: str,
        command: str,
    ) -> ReadinessDossier:
        dossier = await self._session.scalar(
            select(ReadinessDossier)
            .where(ReadinessDossier.dossier_id == dossier_id)
            .with_for_update()
            .limit(1)
        )
        if dossier is None or dossier.organization_id != actor.organization_id:
            await self._reject_audit(
                actor=actor,
                dossier=None,
                capability=capability,
                command=command,
                reason="对象不存在或跨组织访问。",
                object_id=dossier_id,
            )
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]",
                "训练档案不存在或不可访问。",
                404,
                audit_persisted=True,
            )
        await self._require_dossier_access(
            actor,
            dossier,
            capability=capability,
            command=command,
        )
        if not actor.is_human and capability == "readiness.review":
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability=capability,
                command=command,
                reason="正式训练结论只能由人工 Reviewer 作出。",
            )
            raise ReadinessError(
                "[READINESS_HUMAN_REVIEW_REQUIRED]",
                "正式训练结论只能由受权人工复核人作出。",
                403,
                audit_persisted=True,
            )
        return dossier

    async def _require_dossier_access(
        self,
        actor: ReadinessActor,
        dossier: ReadinessDossier,
        *,
        capability: str,
        command: str,
    ) -> None:
        if (
            capability not in actor.capabilities
            or not actor.allows_learner(dossier.learner_id)
        ):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability=capability,
                command=command,
                reason="缺少能力或对象不在 Team 范围内。",
            )
            raise ReadinessError(
                "[DOSSIER_NOT_FOUND]",
                "训练档案不存在或不可访问。",
                404,
                audit_persisted=True,
            )

    async def _require_capability(
        self,
        actor: ReadinessActor,
        capability: str,
        *,
        object_type: str,
        object_id: str,
        command: str,
    ) -> None:
        if capability in actor.capabilities:
            return
        await self._audit(
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=capability,
            object_type=object_type,
            object_id=object_id,
            command=command,
            result="denied",
            reason="当前账号缺少所需权限。",
            trace_id=actor.trace_id,
        )
        raise ReadinessError(
            "[READINESS_PERMISSION_DENIED]",
            "当前账号没有执行该操作的权限。",
            403,
            audit_persisted=True,
        )

    async def _require_current_snapshot(
        self,
        *,
        actor: ReadinessActor,
        dossier: ReadinessDossier,
        snapshot_id: str,
        expected_version: int,
        capability: str,
        command: str,
    ) -> ReadinessDossierSnapshot:
        if dossier.version != expected_version:
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability=capability,
                command=command,
                reason="客户端档案版本与当前版本不一致。",
            )
            raise ReadinessError(
                "[DOSSIER_VERSION_CONFLICT]",
                "训练档案已更新，请刷新后重新复核。",
                412,
                details={
                    "expected_version": expected_version,
                    "actual_version": dossier.version,
                },
                audit_persisted=True,
            )
        if dossier.state == "stale":
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability=capability,
                command=command,
                reason="当前冻结快照已收到新证据并标记过期。",
            )
            raise ReadinessError(
                "[DOSSIER_SNAPSHOT_STALE]",
                "复核期间收到新证据，请先刷新训练档案快照。",
                412,
                audit_persisted=True,
            )
        snapshot = await self._session.get(ReadinessDossierSnapshot, snapshot_id)
        if (
            snapshot is None
            or snapshot.dossier_id != dossier.dossier_id
            or dossier.current_snapshot_id != snapshot.snapshot_id
            or snapshot.stale_at is not None
        ):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability=capability,
                command=command,
                reason="请求引用的复核快照不是当前有效快照。",
            )
            raise ReadinessError(
                "[DOSSIER_SNAPSHOT_STALE]",
                "当前复核快照已变化，请刷新后继续。",
                412,
                audit_persisted=True,
            )
        return snapshot

    def _exception_impact(
        self,
        *,
        dossier: ReadinessDossier,
        snapshot: ReadinessDossierSnapshot,
        reason: str,
        notes: str | None,
        competency_keys: Sequence[str],
        evidence_ids: Sequence[str],
    ) -> dict[str, Any]:
        projection = dict(snapshot.projection_json)
        eligibility = dict(projection.get("eligibility") or {})
        return {
            "contract_version": "readiness_exception_impact_v1",
            "decision_type": "exception_approved",
            "dossier_id": dossier.dossier_id,
            "dossier_version": dossier.version,
            "snapshot_id": snapshot.snapshot_id,
            "path_revision_id": snapshot.path_revision_id,
            "learner_id": dossier.learner_id,
            "current_state": dossier.state,
            "eligibility": eligibility,
            "risk_band": projection.get("risk_band"),
            "risk_reasons": list(projection.get("risk_reasons") or []),
            "overridden_competency_gaps": list(
                eligibility.get("competency_gaps") or []
            ),
            "quality_conflict_evidence_ids": list(
                eligibility.get("quality_conflict_evidence_ids") or []
            ),
            "competency_keys": sorted(set(competency_keys)),
            "evidence_ids": sorted(set(evidence_ids)),
            "reason": reason.strip(),
            "notes_present": bool(notes and notes.strip()),
            "notes_hash": _fingerprint(notes.strip()) if notes and notes.strip() else None,
        }

    async def _consume_exception_preview(
        self,
        *,
        actor: ReadinessActor,
        dossier: ReadinessDossier,
        snapshot: ReadinessDossierSnapshot,
        command: ReviewDecisionInput,
    ) -> None:
        if (
            not command.exception_confirmed
            or command.preview_token is None
            or command.impact_hash is None
        ):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="例外批准缺少有效影响预览或二次确认。",
            )
            raise ReadinessError(
                "[READINESS_EXCEPTION_CONFIRMATION_REQUIRED]",
                "例外批准需要先预览影响，再明确确认同一份预览。",
                409,
                audit_persisted=True,
            )
        preview = await self._session.scalar(
            select(ReadinessExceptionPreview)
            .where(
                ReadinessExceptionPreview.preview_token_hash
                == _secret_hash(command.preview_token)
            )
            .with_for_update()
            .limit(1)
        )
        invalid = (
            preview is None
            or preview.organization_id != dossier.organization_id
            or preview.dossier_id != dossier.dossier_id
            or preview.snapshot_id != snapshot.snapshot_id
            or preview.dossier_version != dossier.version
            or preview.reviewer_id != actor.actor_id
            or preview.status != "previewed"
        )
        if invalid:
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="例外批准预览不存在、已使用或不属于当前复核上下文。",
            )
            raise ReadinessError(
                "[READINESS_EXCEPTION_PREVIEW_INVALID]",
                "例外批准预览已失效，请重新预览后确认。",
                409,
                audit_persisted=True,
            )
        assert preview is not None
        if _aware(preview.expires_at) <= _now():
            preview.status = "expired"
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="例外批准预览已过期。",
            )
            raise ReadinessError(
                "[READINESS_EXCEPTION_PREVIEW_EXPIRED]",
                "例外批准预览已过期，请重新预览后确认。",
                409,
                audit_persisted=True,
            )
        actual_impact = self._exception_impact(
            dossier=dossier,
            snapshot=snapshot,
            reason=command.reason,
            notes=command.notes,
            competency_keys=command.competency_keys,
            evidence_ids=command.evidence_ids,
        )
        actual_hash = _fingerprint(actual_impact)
        if (
            preview.impact_hash != command.impact_hash
            or actual_hash != command.impact_hash
        ):
            await self._reject_audit(
                actor=actor,
                dossier=dossier,
                capability="readiness.review",
                command="record_review_decision",
                reason="例外批准内容与已预览影响不一致。",
            )
            raise ReadinessError(
                "[READINESS_EXCEPTION_IMPACT_CHANGED]",
                "例外批准内容或档案影响已变化，请重新预览。",
                409,
                audit_persisted=True,
            )
        preview.status = "consumed"
        preview.consumed_at = _now()
        await self._session.flush([preview])

    async def _validate_snapshot_references(
        self,
        snapshot: ReadinessDossierSnapshot,
        *,
        competency_keys: Sequence[str],
        evidence_ids: Sequence[str],
    ) -> None:
        unknown_keys = sorted(set(competency_keys) - set(STANDARD_COMPETENCY_KEYS))
        unknown_evidence = sorted(set(evidence_ids) - set(snapshot.evidence_ids_json))
        if unknown_keys or unknown_evidence:
            raise ReadinessError(
                "[DOSSIER_REFERENCE_INVALID]",
                "复核引用不属于当前冻结档案快照。",
                422,
                details={
                    "competency_keys": unknown_keys,
                    "evidence_ids": unknown_evidence,
                },
            )

    async def _require_appeal_target(
        self, dossier: ReadinessDossier, command: AppealInput
    ) -> None:
        snapshot = (
            await self._session.get(
                ReadinessDossierSnapshot, dossier.current_snapshot_id
            )
            if dossier.current_snapshot_id
            else None
        )
        if snapshot is None:
            raise ReadinessError(
                "[DOSSIER_SNAPSHOT_NOT_FOUND]", "训练档案快照不存在。", 404
            )
        evidence = list(snapshot.projection_json.get("evidence") or [])
        evidence_ids = {str(item.get("evidence_id")) for item in evidence}
        outcome_ids = {str(item.get("outcome_id")) for item in evidence}
        decision_ids = set(
            (
                await self._session.scalars(
                    select(ReadinessReviewDecision.decision_id).where(
                        ReadinessReviewDecision.dossier_id == dossier.dossier_id
                    )
                )
            ).all()
        )
        valid = (
            command.target_id in decision_ids
            if command.target_type == "decision"
            else command.target_id in evidence_ids | outcome_ids
        )
        if not valid:
            raise ReadinessError(
                "[APPEAL_TARGET_INVALID]",
                "申诉目标不属于当前训练档案。",
                422,
            )

    async def _complete_retraining_assignments(
        self,
        dossier: ReadinessDossier,
        input_value: ReadinessProjectionInput,
        *,
        actor_id: str,
        trace_id: str | None,
    ) -> None:
        assignments = list(
            (
                await self._session.execute(
                    select(ReadinessRetrainingAssignment)
                    .where(
                        ReadinessRetrainingAssignment.dossier_id
                        == dossier.dossier_id
                    )
                    .where(ReadinessRetrainingAssignment.status == "assigned")
                )
            ).scalars()
        )
        activity_by_id = {item.activity_id: item for item in input_value.activities}
        for assignment in assignments:
            activity = activity_by_id.get(str(assignment.activity_id or ""))
            if (
                activity is None
                or activity.latest_outcome_id is None
                or activity.latest_outcome_at is None
                or _aware(activity.latest_outcome_at)
                <= _aware(assignment.assigned_at)
            ):
                continue
            if activity.latest_outcome_id in assignment.completed_outcome_ids_json:
                continue
            before_version = assignment.version
            assignment.status = "completed"
            assignment.version += 1
            assignment.completed_outcome_ids_json = [activity.latest_outcome_id]
            assignment.completed_at = _now()
            await self._session.flush([assignment])
            await self._audit(
                organization_id=dossier.organization_id,
                actor_id=actor_id,
                capability="readiness.project",
                object_type="retraining_assignment",
                object_id=assignment.assignment_id,
                command="complete_retraining",
                result="succeeded",
                before_version=before_version,
                after_version=assignment.version,
                trace_id=trace_id,
                details={
                    "dossier_id": dossier.dossier_id,
                    "outcome_id": activity.latest_outcome_id,
                },
            )
            await self._event(
                dossier,
                event_type="RetrainingCompleted",
                actor_id=actor_id,
                trace_id=trace_id,
                payload={
                    "assignment_id": assignment.assignment_id,
                    "outcome_id": activity.latest_outcome_id,
                },
                idempotency_discriminator=assignment.assignment_id,
            )

    async def _decision_replay(
        self,
        *,
        dossier: ReadinessDossier,
        idempotency_key: str,
        fingerprint: str,
    ) -> ReadinessReviewDecision | None:
        row = await self._session.scalar(
            select(ReadinessReviewDecision)
            .where(
                ReadinessReviewDecision.organization_id == dossier.organization_id
            )
            .where(ReadinessReviewDecision.dossier_id == dossier.dossier_id)
            .where(
                ReadinessReviewDecision.idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if row is not None and row.command_fingerprint != fingerprint:
            self._idempotency_conflict()
        return row

    async def _reject_audit(
        self,
        *,
        actor: ReadinessActor,
        dossier: ReadinessDossier | None,
        capability: str,
        command: str,
        reason: str,
        object_id: str | None = None,
    ) -> None:
        await self._audit(
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            capability=capability,
            object_type="readiness_dossier",
            object_id=(
                dossier.dossier_id
                if dossier is not None
                else object_id or "unknown"
            ),
            command=command,
            result="denied",
            reason=reason,
            actual_version=dossier.version if dossier is not None else None,
            trace_id=actor.trace_id,
        )

    async def _audit(
        self,
        *,
        organization_id: str,
        actor_id: str,
        capability: str,
        object_type: str,
        object_id: str,
        command: str,
        result: str,
        reason: str | None = None,
        before_version: int | None = None,
        after_version: int | None = None,
        actual_version: int | None = None,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(details or {})
        if actual_version is not None:
            payload["actual_version"] = actual_version
        row = ReadinessCommandAudit(
            audit_id=_id(),
            organization_id=organization_id,
            actor_id=actor_id,
            capability=capability,
            object_type=object_type,
            object_id=object_id,
            command=command,
            result=result,
            reason=reason,
            before_version=before_version,
            after_version=after_version,
            idempotency_key_hash=(
                _secret_hash(idempotency_key) if idempotency_key else None
            ),
            details_json=payload,
            trace_id=trace_id,
            occurred_at=_now(),
        )
        self._session.add(row)
        await self._session.flush([row])

    async def _event(
        self,
        dossier: ReadinessDossier,
        *,
        event_type: str,
        actor_id: str,
        trace_id: str | None,
        payload: dict[str, Any],
        idempotency_discriminator: str | None = None,
    ) -> None:
        idempotency_key = f"{dossier.dossier_id}:{event_type}:{dossier.version}"
        if idempotency_discriminator:
            idempotency_key = f"{idempotency_key}:{idempotency_discriminator}"
        await self._outbox.append(
            DomainEvent(
                event_type=event_type,
                schema_version=1,
                occurred_at=_now(),
                organization_id=dossier.organization_id,
                actor_id=actor_id,
                trace_id=trace_id,
                correlation_id=dossier.enrollment_id,
                causation_id=dossier.current_snapshot_id,
                idempotency_key=idempotency_key,
                aggregate_type="readiness_dossier",
                aggregate_id=dossier.dossier_id,
                aggregate_version=dossier.version,
                payload={"dossier_id": dossier.dossier_id, **payload},
            )
        )

    @staticmethod
    def _decision_payload(
        row: ReadinessReviewDecision,
        *,
        learner_safe: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision_id": row.decision_id,
            "snapshot_id": row.snapshot_id,
            "decision_type": row.decision_type,
            "decision_label": {
                "approve_foundation_ready": "基础训练已达标",
                "request_retraining": "需要补充训练",
                "request_more_evidence": "需要补充证据",
                "reject_due_to_integrity_issue": "证据完整性待处理",
                "close_without_decision": "本次复核已关闭",
                "exception_approved": "例外批准基础达标",
            }.get(row.decision_type, "复核结论"),
            "status": row.status,
            "reviewer_id": row.reviewer_id,
            "competency_keys": list(row.competency_keys_json),
            "evidence_ids": list(row.evidence_ids_json),
            "reason": row.reason,
            "created_at": row.created_at,
            "supersedes_decision_id": row.supersedes_decision_id,
        }
        if not learner_safe:
            payload["notes"] = row.notes
        return payload

    @staticmethod
    def _exception_preview_payload(
        row: ReadinessExceptionPreview,
        *,
        preview_token: str,
    ) -> dict[str, Any]:
        return {
            "contract_version": "readiness_exception_preview_v1",
            "preview_id": row.preview_id,
            "dossier_id": row.dossier_id,
            "snapshot_id": row.snapshot_id,
            "dossier_version": row.dossier_version,
            "status": row.status,
            "impact": row.impact_json,
            "impact_hash": row.impact_hash,
            "preview_token": preview_token,
            "expires_at": row.expires_at,
            "consumed_at": row.consumed_at,
        }

    @staticmethod
    def _retraining_payload(row: ReadinessRetrainingAssignment) -> dict[str, Any]:
        return {
            "assignment_id": row.assignment_id,
            "source_snapshot_id": row.source_snapshot_id,
            "activity_source": row.activity_source,
            "activity_id": row.activity_id,
            "activity_title": row.activity_title,
            "target_competency_keys": list(row.target_competency_keys_json),
            "source_evidence_ids": list(row.source_evidence_ids_json),
            "reason": row.reason,
            "due_at": row.due_at,
            "completion_rule": row.completion_rule_json,
            "status": row.status,
            "version": row.version,
            "completed_outcome_ids": list(row.completed_outcome_ids_json),
            "assigned_at": row.assigned_at,
            "completed_at": row.completed_at,
            "next_action": (
                {
                    "label": "开始补充训练",
                    "href": (
                        "/newcomer-training/activities/"
                        f"{row.activity_id}"
                    ),
                }
                if row.status == "assigned" and row.activity_id
                else {
                    "label": "等待管理员完善补练内容",
                    "href": None,
                }
                if row.status == "draft_pending_governance"
                else None
            ),
        }

    @staticmethod
    def _appeal_payload(row: ReadinessAppeal) -> dict[str, Any]:
        return {
            "appeal_id": row.appeal_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "reason_category": row.reason_category,
            "statement": row.statement,
            "status": row.status,
            "assigned_to": row.assigned_to,
            "resolution": row.resolution,
            "version": row.version,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "resolved_at": row.resolved_at,
        }

    @staticmethod
    def _summary_payload(
        row: ReadinessAISummary,
        *,
        learner_safe: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "summary_id": row.summary_id,
            "revision_no": row.revision_no,
            "status": row.status,
            "label": "AI 辅助摘要" if row.status == "ready" else "辅助摘要不可用",
            "message": (
                None
                if row.status == "ready"
                else "可直接依据确定性档案完成人工复核。"
            ),
            "created_at": row.created_at,
        }
        if not learner_safe:
            payload["draft"] = row.payload_json
            payload["evidence_ids"] = list(row.evidence_ids_json)
        return payload

    @staticmethod
    def _learner_evidence_payload(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "evidence_id",
            "competency_key",
            "competency_title",
            "source_activity_id",
            "outcome_id",
            "outcome_version",
            "evidence_type",
            "observed_score",
            "observed_max_score",
            "observed_result",
            "quality",
            "validity",
            "observed_at",
        )
        return {key: value.get(key) for key in allowed}

    @staticmethod
    def _projection_capabilities(
        dossier: ReadinessDossier,
        learner_safe: bool,
        actor: ReadinessActor | None,
    ) -> list[str]:
        if actor is None:
            return []
        if learner_safe:
            capabilities = []
            if "readiness.self.read" in actor.capabilities:
                capabilities.append("read_dossier")
            if "readiness.appeal.submit" in actor.capabilities:
                capabilities.append("submit_appeal")
            if dossier.state == "stale":
                capabilities.append("wait_for_refresh")
            return capabilities
        command_by_capability = {
            "readiness.dossier.read": "read_dossier",
            "readiness.review": "record_decision",
            "readiness.retraining.assign": "assign_retraining",
            "readiness.appeal.resolve": "resolve_appeal",
            "readiness.rebuild": "refresh_snapshot",
            "readiness.export": "export_dossier",
        }
        return [
            command
            for capability, command in command_by_capability.items()
            if capability in actor.capabilities
        ]

    @staticmethod
    def _status_label(state: str) -> str:
        return {
            "projecting": "正在生成档案",
            "incomplete": "训练证据待补充",
            "ready_for_review": "等待人工复核",
            "under_review": "复核中",
            "decided": "已形成复核结论",
            "stale": "收到新证据，待刷新复核",
            "projection_failed": "档案暂时无法更新",
        }.get(state, "状态待确认")

    @staticmethod
    def _next_actions(
        *,
        dossier: ReadinessDossier,
        eligibility: dict[str, Any],
        assignments: Sequence[ReadinessRetrainingAssignment],
        learner_safe: bool,
    ) -> list[dict[str, Any]]:
        if learner_safe:
            active = next(
                (
                    item
                    for item in assignments
                    if item.status in {"assigned", "draft_pending_governance"}
                ),
                None,
            )
            if active is not None:
                return [ReadinessService._retraining_payload(active)["next_action"]]
            if dossier.state == "stale":
                return [
                    {
                        "label": "等待复核材料更新",
                        "command": "wait_for_refresh",
                    }
                ]
            if not eligibility.get("eligible"):
                return [
                    {
                        "label": "继续完成训练",
                        "href": "/newcomer-training",
                        "command": "continue_training",
                    }
                ]
            return [
                {"label": "等待培训负责人复核", "command": "wait_for_review"}
            ]
        if dossier.state == "stale":
            return [
                {"label": "刷新档案快照", "command": "refresh_snapshot"}
            ]
        if eligibility.get("eligible"):
            return [
                {"label": "记录复核结论", "command": "record_decision"}
            ]
        return [{"label": "安排补充训练", "command": "assign_retraining"}]

    @staticmethod
    def _queue_reason(projection: dict[str, Any]) -> str:
        if projection.get("snapshot_stale"):
            return "复核材料在新证据到达后已过期，需要刷新。"
        eligibility = projection["summary"]["eligibility"]
        reasons = eligibility.get("reasons") or []
        if reasons:
            return str(reasons[0])
        if projection["status"] == "ready_for_review":
            return "训练证据已满足前置条件，等待人工复核。"
        return "训练档案需要培训负责人处理。"

    @staticmethod
    def _decision_types_by_dossier(
        decisions: Sequence[ReadinessReviewDecision],
    ) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for decision in decisions:
            result.setdefault(decision.dossier_id, set()).add(
                decision.decision_type
            )
        return result

    @staticmethod
    def _idempotency_conflict() -> None:
        raise ReadinessError(
            "[READINESS_IDEMPOTENCY_CONFLICT]",
            "相同幂等键对应了不同的复核命令。",
            409,
        )


__all__ = ["ReadinessService"]
