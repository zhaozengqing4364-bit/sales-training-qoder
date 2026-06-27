from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
)

AssetRevisionStatus = Literal["working", "published", "archived"]
AssetChangeClass = Literal[
    "non_semantic",
    "semantic",
    "binding",
    "scoring_high_risk",
]


@dataclass(frozen=True, slots=True)
class AssetPublishResult:
    revision: SalesTrainerAssetRevision
    previous_revision_id: str | None


class SalesTrainerAssetRevisionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_working_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
        payload: dict[str, Any],
        actor: User,
        change_class: AssetChangeClass,
        source_revision_id: str | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> SalesTrainerAssetRevision:
        await self._archive_existing_working_revisions(
            resource_type=resource_type,
            logical_id=logical_id,
        )
        revision = SalesTrainerAssetRevision(
            resource_type=resource_type,
            logical_id=logical_id,
            revision_no=await self._next_revision_no(
                resource_type=resource_type,
                logical_id=logical_id,
            ),
            status="working",
            payload_json=deepcopy(payload),
            payload_hash=_payload_hash(payload),
            change_class=change_class,
            source_revision_id=source_revision_id,
            reason=reason,
            trace_id=trace_id,
            created_by=str(actor.user_id),
        )
        self._db.add(revision)
        await self._db.flush()
        return revision

    async def create_published_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
        payload: dict[str, Any],
        actor: User,
        change_class: AssetChangeClass,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        revision = SalesTrainerAssetRevision(
            resource_type=resource_type,
            logical_id=logical_id,
            revision_no=await self._next_revision_no(
                resource_type=resource_type,
                logical_id=logical_id,
            ),
            status="published",
            payload_json=deepcopy(payload),
            payload_hash=_payload_hash(payload),
            change_class=change_class,
            reason=reason,
            trace_id=trace_id,
            created_by=str(actor.user_id),
            published_by=str(actor.user_id),
            published_at=datetime.now(UTC),
        )
        self._db.add(revision)
        await self._db.flush()
        previous_revision_id = await self._activate(
            revision,
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
        return AssetPublishResult(
            revision=revision,
            previous_revision_id=previous_revision_id,
        )

    async def latest_working_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
    ) -> SalesTrainerAssetRevision | None:
        result = await self._db.execute(
            select(SalesTrainerAssetRevision)
            .where(
                SalesTrainerAssetRevision.resource_type == resource_type,
                SalesTrainerAssetRevision.logical_id == logical_id,
                SalesTrainerAssetRevision.status == "working",
            )
            .order_by(SalesTrainerAssetRevision.revision_no.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def active_revision(
        self,
        *,
        resource_type: str,
        logical_id: str,
    ) -> SalesTrainerAssetRevision | None:
        result = await self._db.execute(
            select(SalesTrainerAssetRevision)
            .join(
                SalesTrainerAssetActiveRevision,
                SalesTrainerAssetActiveRevision.active_revision_id
                == SalesTrainerAssetRevision.revision_id,
            )
            .where(
                SalesTrainerAssetActiveRevision.resource_type == resource_type,
                SalesTrainerAssetActiveRevision.logical_id == logical_id,
            )
        )
        return result.scalar_one_or_none()

    async def revision_by_id(
        self,
        revision_id: str,
    ) -> SalesTrainerAssetRevision | None:
        return await self._db.get(SalesTrainerAssetRevision, revision_id)

    async def list_revisions(
        self,
        *,
        resource_type: str,
        logical_id: str,
    ) -> list[SalesTrainerAssetRevision]:
        result = await self._db.execute(
            select(SalesTrainerAssetRevision)
            .where(
                SalesTrainerAssetRevision.resource_type == resource_type,
                SalesTrainerAssetRevision.logical_id == logical_id,
            )
            .order_by(SalesTrainerAssetRevision.revision_no.desc())
        )
        return list(result.scalars().all())

    async def rollback_to_revision(
        self,
        revision: SalesTrainerAssetRevision,
        *,
        actor: User,
        reason: str,
        trace_id: str | None = None,
        expected_resource_type: str | None = None,
        expected_logical_id: str | None = None,
    ) -> AssetPublishResult:
        if revision.status != "published":
            raise SalesTrainerAssetRevisionError(
                "[ASSET_REVISION_NOT_ROLLBACKABLE]",
                "只能回滚到已发布修订。",
            )
        if (
            expected_resource_type is not None
            and revision.resource_type != expected_resource_type
        ) or (expected_logical_id is not None and revision.logical_id != expected_logical_id):
            raise SalesTrainerAssetRevisionError(
                "[ASSET_REVISION_TARGET_MISMATCH]",
                "回滚目标与当前资产不匹配。",
            )
        previous_revision_id = await self._activate(
            revision,
            actor=actor,
            reason=reason,
            trace_id=trace_id,
        )
        return AssetPublishResult(
            revision=revision,
            previous_revision_id=previous_revision_id,
        )

    async def publish_working_revision(
        self,
        revision: SalesTrainerAssetRevision,
        *,
        actor: User,
        reason: str | None = None,
        trace_id: str | None = None,
    ) -> AssetPublishResult:
        if revision.status != "working":
            raise SalesTrainerAssetRevisionError(
                "[ASSET_REVISION_NOT_PUBLISHABLE]",
                "只能发布工作修订。",
            )
        _set_orm_field(revision, "status", "published")
        _set_orm_field(revision, "published_by", str(actor.user_id))
        _set_orm_field(revision, "published_at", datetime.now(UTC))
        previous_revision_id = await self._activate(
            revision,
            actor=actor,
            reason=reason or _orm_optional_str(revision.reason),
            trace_id=trace_id or _orm_optional_str(revision.trace_id),
        )
        await self._db.flush()
        return AssetPublishResult(
            revision=revision,
            previous_revision_id=previous_revision_id,
        )

    async def _archive_existing_working_revisions(
        self,
        *,
        resource_type: str,
        logical_id: str,
    ) -> None:
        result = await self._db.execute(
            select(SalesTrainerAssetRevision).where(
                SalesTrainerAssetRevision.resource_type == resource_type,
                SalesTrainerAssetRevision.logical_id == logical_id,
                SalesTrainerAssetRevision.status == "working",
            )
        )
        for revision in result.scalars().all():
            _set_orm_field(revision, "status", "archived")
        await self._db.flush()

    async def _next_revision_no(self, *, resource_type: str, logical_id: str) -> int:
        current = await self._db.scalar(
            select(func.max(SalesTrainerAssetRevision.revision_no)).where(
                SalesTrainerAssetRevision.resource_type == resource_type,
                SalesTrainerAssetRevision.logical_id == logical_id,
            )
        )
        return int(current or 0) + 1

    async def _activate(
        self,
        revision: SalesTrainerAssetRevision,
        *,
        actor: User,
        reason: str | None,
        trace_id: str | None,
    ) -> str | None:
        result = await self._db.execute(
            select(SalesTrainerAssetActiveRevision).where(
                SalesTrainerAssetActiveRevision.resource_type == revision.resource_type,
                SalesTrainerAssetActiveRevision.logical_id == revision.logical_id,
            )
        )
        active_ref = result.scalar_one_or_none()
        previous_revision_id = (
            str(active_ref.active_revision_id) if active_ref is not None else None
        )
        if active_ref is None:
            active_ref = SalesTrainerAssetActiveRevision(
                resource_type=revision.resource_type,
                logical_id=revision.logical_id,
                active_revision_id=revision.revision_id,
                activated_by=str(actor.user_id),
                activation_reason=reason,
                trace_id=trace_id,
            )
            self._db.add(active_ref)
        else:
            _set_orm_field(active_ref, "active_revision_id", revision.revision_id)
            _set_orm_field(active_ref, "activated_by", str(actor.user_id))
            _set_orm_field(active_ref, "activation_reason", reason)
            _set_orm_field(active_ref, "trace_id", trace_id)
            _set_orm_field(active_ref, "activated_at", datetime.now(UTC))
        await self._db.flush()
        return previous_revision_id

    @staticmethod
    def snapshot(row: SalesTrainerAssetRevision | None) -> dict[str, Any] | None:
        if row is None:
            return None
        created_at = getattr(row, "created_at", None)
        published_at = getattr(row, "published_at", None)
        return {
            "revision_id": row.revision_id,
            "resource_type": row.resource_type,
            "logical_id": row.logical_id,
            "revision_no": row.revision_no,
            "status": row.status,
            "payload_hash": row.payload_hash,
            "payload": deepcopy(row.payload_json),
            "change_class": row.change_class,
            "source_revision_id": row.source_revision_id,
            "reason": row.reason,
            "trace_id": row.trace_id,
            "created_by": row.created_by,
            "published_by": row.published_by,
            "created_at": created_at.isoformat() if created_at else None,
            "published_at": published_at.isoformat() if published_at else None,
        }


def _set_orm_field(row: object, name: str, value: object) -> None:
    setattr(row, name, value)


def _orm_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SalesTrainerAssetRevisionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)
