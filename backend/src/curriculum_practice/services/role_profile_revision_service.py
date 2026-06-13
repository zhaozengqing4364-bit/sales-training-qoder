from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from common.db.models import User
from common.monitoring.logger import get_trace_id
from curriculum_practice.models import RoleProfile
from curriculum_practice.schemas import RoleProfileCreate
from curriculum_practice.services.content_asset_payloads import (
    apply_role_profile_revision_payload,
    role_profile_content_hash,
    role_profile_lifecycle_snapshot,
    role_profile_revision_payload_from_update,
)
from curriculum_practice.services.content_asset_revision_metadata import (
    ROLE_PROFILE_RESOURCE_TYPE,
    ROLE_PROFILE_TARGET_TYPE,
    role_profile_change_class,
    role_profile_lifecycle_metadata,
)
from curriculum_practice.services.sales_trainer_revision_adapter import (
    OperationLogService,
    SalesTrainerAssetRevision,
    SalesTrainerAssetRevisionService,
)


class RoleProfileRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._revisions = SalesTrainerAssetRevisionService(db)

    async def save_future_revision(
        self,
        item: RoleProfile,
        payload: RoleProfileCreate,
        *,
        actor: User,
    ) -> SalesTrainerAssetRevision:
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=ROLE_PROFILE_RESOURCE_TYPE,
            logical_id=str(item.role_profile_id),
        )
        previous_snapshot = _snapshot_from_revision(active, item)
        next_snapshot = role_profile_revision_payload_from_update(item, payload)
        revision = await self._revisions.save_working_revision(
            resource_type=ROLE_PROFILE_RESOURCE_TYPE,
            logical_id=str(item.role_profile_id),
            payload=next_snapshot,
            actor=actor,
            change_class=role_profile_change_class(previous_snapshot, next_snapshot),
            source_revision_id=str(active.revision_id) if active is not None else None,
            reason="save edited role profile revision",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="role_profile_revision_saved",
            target_type=ROLE_PROFILE_TARGET_TYPE,
            target_id=str(item.role_profile_id),
            request_id=trace_id,
            metadata={
                **role_profile_lifecycle_metadata(previous_snapshot, next_snapshot),
                "source_revision_id": revision.source_revision_id,
                "working_revision_id": revision.revision_id,
                "change_class": revision.change_class,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return revision

    async def ensure_initial_published_revision(
        self,
        item: RoleProfile,
        *,
        actor: User,
    ) -> None:
        active = await self._revisions.active_revision(
            resource_type=ROLE_PROFILE_RESOURCE_TYPE,
            logical_id=str(item.role_profile_id),
        )
        if active is not None:
            return
        trace_id = get_trace_id()
        next_snapshot = role_profile_lifecycle_snapshot(item)
        result = await self._revisions.create_published_revision(
            resource_type=ROLE_PROFILE_RESOURCE_TYPE,
            logical_id=str(item.role_profile_id),
            payload=next_snapshot,
            actor=actor,
            change_class="semantic",
            reason="initial role profile publish",
            trace_id=trace_id,
        )
        await self._logs.record(
            actor=actor,
            action="role_profile_published",
            target_type=ROLE_PROFILE_TARGET_TYPE,
            target_id=str(item.role_profile_id),
            request_id=trace_id,
            metadata={
                **role_profile_lifecycle_metadata(next_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": result.revision.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )

    async def publish_working_revision(
        self,
        item: RoleProfile,
        *,
        actor: User,
    ) -> bool:
        working = await self._revisions.latest_working_revision(
            resource_type=ROLE_PROFILE_RESOURCE_TYPE,
            logical_id=str(item.role_profile_id),
        )
        if working is None:
            return False
        payload = _payload_dict(working.payload_json)
        if role_profile_content_hash(payload) != payload.get("content_hash"):
            return False
        if not await self._persona_ref_available(payload.get("persona_ref")):
            return False
        trace_id = get_trace_id()
        active = await self._revisions.active_revision(
            resource_type=ROLE_PROFILE_RESOURCE_TYPE,
            logical_id=str(item.role_profile_id),
        )
        previous_snapshot = _payload_dict(active.payload_json) if active else payload
        apply_role_profile_revision_payload(
            item,
            payload,
            actor_id=str(actor.user_id),
            published_at=datetime.now(UTC),
        )
        result = await self._revisions.publish_working_revision(
            working,
            actor=actor,
            reason="publish edited role profile revision",
            trace_id=trace_id,
        )
        next_snapshot = role_profile_lifecycle_snapshot(item)
        await self._logs.record(
            actor=actor,
            action="role_profile_revision_published",
            target_type=ROLE_PROFILE_TARGET_TYPE,
            target_id=str(item.role_profile_id),
            request_id=trace_id,
            metadata={
                **role_profile_lifecycle_metadata(previous_snapshot, next_snapshot),
                "before_revision_id": result.previous_revision_id,
                "after_revision_id": working.revision_id,
                "trace_id": trace_id,
                "future_only": True,
            },
        )
        return True

    async def _persona_ref_available(self, persona_ref: Any) -> bool:
        if not isinstance(persona_ref, str) or not persona_ref:
            return True
        persona = await self._db.get(Persona, persona_ref)
        return persona is not None and persona.status == "active"


def _snapshot_from_revision(
    revision: SalesTrainerAssetRevision | None,
    item: RoleProfile,
) -> dict[str, Any]:
    if revision is None:
        return role_profile_lifecycle_snapshot(item)
    return _payload_dict(revision.payload_json)


def _payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}
