from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import PracticeTemplateUpdate, PublishGateDecision
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.practice_template_publish_gate_factory import (
    build_practice_template_gate_service,
)
from curriculum_practice.services.practice_template_revision_metadata import (
    PRACTICE_TEMPLATE_RESOURCE_TYPE,
    PRACTICE_TEMPLATE_TARGET_TYPE,
    template_change_class,
    template_lifecycle_metadata,
)
from curriculum_practice.services.practice_template_revision_payloads import (
    apply_template_revision_payload,
    candidate_from_payload,
    candidate_from_template,
    template_lifecycle_snapshot,
    template_publish_payload,
    template_revision_payload_from_update,
)
from curriculum_practice.services.published_asset_refs import (
    resolve_template_situation_pack_code,
)
from curriculum_practice.services.publishing_gates import PublishingGateService
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.operation_log_service import OperationLogService


class PracticeTemplateRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def stage_future_revision(
        self,
        template: PracticeTemplate,
        payload: PracticeTemplateUpdate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=PRACTICE_TEMPLATE_RESOURCE_TYPE,
            logical_id=str(template.template_id),
        )
        previous_snapshot = _snapshot_from_revision(active, template)
        next_snapshot = template_revision_payload_from_update(template, payload)
        revision = await self._revisions.save_working_revision(
            resource_type=PRACTICE_TEMPLATE_RESOURCE_TYPE,
            logical_id=str(template.template_id),
            payload=next_snapshot,
            actor=actor,
            change_class=template_change_class(previous_snapshot, next_snapshot),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason="save edited practice template revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="practice_template_revision_saved",
            target_type=PRACTICE_TEMPLATE_TARGET_TYPE,
            target_id=str(template.template_id),
            request_id=trace_id,
            metadata={
                **template_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return revision

    async def stage_initial_published_revision(
        self,
        template: PracticeTemplate,
        *,
        actor: User,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=PRACTICE_TEMPLATE_RESOURCE_TYPE,
            logical_id=str(template.template_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = template_lifecycle_snapshot(template)
        result = await self._revisions.create_published_revision(
            resource_type=PRACTICE_TEMPLATE_RESOURCE_TYPE,
            logical_id=str(template.template_id),
            payload=next_snapshot,
            actor=actor,
            change_class="binding",
            reason="initial practice template publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="practice_template_published",
            target_type=PRACTICE_TEMPLATE_TARGET_TYPE,
            target_id=str(template.template_id),
            request_id=trace_id,
            metadata={
                **template_lifecycle_metadata(next_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )

    async def stage_publish_working_revision(
        self,
        template: PracticeTemplate,
        *,
        actor: User,
    ) -> tuple[bool, PublishGateDecision]:
        working = await self._revisions.latest_working_revision(
            resource_type=PRACTICE_TEMPLATE_RESOURCE_TYPE,
            logical_id=str(template.template_id),
        )
        ok_decision = PublishGateDecision(can_publish=True, results=[])
        if working is None:
            return False, ok_decision
        payload = _payload_dict(working.payload_json)
        gate_service = await self._gate_service()
        candidate = candidate_from_payload(payload)
        decision = await gate_service.validate(candidate)
        if not decision.can_publish:
            return False, decision

        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=PRACTICE_TEMPLATE_RESOURCE_TYPE,
            logical_id=str(template.template_id),
        )
        previous_snapshot = _payload_dict(active.payload_json) if active else payload
        resolved_at = datetime.now(UTC).isoformat()
        published_asset_refs = await gate_service.build_published_asset_refs(
            candidate,
            resolved_at=resolved_at,
        )
        situation_pack_code = await resolve_template_situation_pack_code(
            candidate,
            reference_reader=CurriculumAssetReferenceReader(
                self._db
            ).read_publish_gate_reference,
        )
        published_payload = template_publish_payload(
            payload,
            published_asset_refs=published_asset_refs,
            situation_pack_code=situation_pack_code,
        )
        working.payload_json = published_payload
        working.payload_hash = _revision_storage_hash(published_payload)
        apply_template_revision_payload(
            template,
            published_payload,
            actor_id=str(actor.user_id),
            published_asset_refs=published_asset_refs,
            situation_pack_code=situation_pack_code,
            published_at=datetime.now(UTC),
        )
        result = await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason="publish edited practice template revision",
            trace_id=trace_id,
        )
        next_snapshot = template_lifecycle_snapshot(template)
        await self._logs.record(
            actor=actor,
            action="practice_template_revision_published",
            target_type=PRACTICE_TEMPLATE_TARGET_TYPE,
            target_id=str(template.template_id),
            request_id=trace_id,
            metadata={
                **template_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return True, decision

    async def validate_current_template(
        self,
        template: PracticeTemplate,
    ) -> tuple[PublishGateDecision, dict[str, dict[str, Any]], str]:
        gate_service = await self._gate_service()
        candidate = candidate_from_template(template)
        decision = await gate_service.validate(candidate)
        if not decision.can_publish:
            return decision, {}, ""
        resolved_at = datetime.now(UTC).isoformat()
        published_asset_refs = await gate_service.build_published_asset_refs(
            candidate,
            resolved_at=resolved_at,
        )
        situation_pack_code = await resolve_template_situation_pack_code(
            candidate,
            reference_reader=CurriculumAssetReferenceReader(
                self._db
            ).read_publish_gate_reference,
        )
        return decision, published_asset_refs, situation_pack_code

    async def _gate_service(self) -> PublishingGateService:
        return await build_practice_template_gate_service(self._db)


def _snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    template: PracticeTemplate,
) -> dict[str, Any]:
    if revision is None:
        return template_lifecycle_snapshot(template)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _revision_storage_hash(payload: dict[str, Any]) -> str:
    raw = dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()
