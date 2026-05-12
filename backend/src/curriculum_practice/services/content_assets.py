from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from curriculum_practice.models import CaseItem, RoleProfile
from curriculum_practice.schemas import CaseItemCreate, RoleProfileCreate

HASH_EXCLUDED_FIELDS = {
    "case_item_id",
    "role_profile_id",
    "version",
    "content_hash",
    "status",
    "published_at",
    "published_by",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
}


@runtime_checkable
class ModelDumpable(Protocol):
    def model_dump(self) -> dict[str, Any]: ...


class ContentAssetPublishError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class ContentAssetNotEditableError(ValueError):
    pass


class ContentAssetService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_case_items(self) -> list[CaseItem]:
        result = await self._db.execute(
            select(CaseItem).order_by(CaseItem.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_case_item(self, case_item_id: str) -> CaseItem | None:
        return await self._db.get(CaseItem, case_item_id)

    async def create_case_item(
        self, payload: CaseItemCreate, *, actor_id: str | None
    ) -> CaseItem:
        item = CaseItem(**payload.model_dump(), created_by=actor_id, updated_by=actor_id)
        self._db.add(item)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def update_case_item(
        self, item: CaseItem, payload: CaseItemCreate, *, actor_id: str | None
    ) -> CaseItem:
        if item.status != "draft":
            raise ContentAssetNotEditableError
        for field, value in payload.model_dump().items():
            setattr(item, field, value)
        item.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def archive_case_item(
        self, item: CaseItem, *, actor_id: str | None
    ) -> CaseItem:
        item.status = "archived"
        item.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def list_role_profiles(self) -> list[RoleProfile]:
        result = await self._db.execute(
            select(RoleProfile).order_by(RoleProfile.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_role_profile(self, role_profile_id: str) -> RoleProfile | None:
        return await self._db.get(RoleProfile, role_profile_id)

    async def create_role_profile(
        self, payload: RoleProfileCreate, *, actor_id: str | None
    ) -> RoleProfile:
        item = RoleProfile(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(item)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def update_role_profile(
        self, item: RoleProfile, payload: RoleProfileCreate, *, actor_id: str | None
    ) -> RoleProfile:
        if item.status != "draft":
            raise ContentAssetNotEditableError
        for field, value in payload.model_dump().items():
            setattr(item, field, value)
        item.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def archive_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        item.status = "archived"
        item.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def publish_case_item(
        self, item: CaseItem, *, actor_id: str | None
    ) -> CaseItem:
        expected_hash = case_item_content_hash(_case_item_payload(item))
        if item.content_hash != expected_hash:
            raise ContentAssetPublishError(
                "content_hash_mismatch",
                "CaseItem content_hash does not match current content.",
            )
        if not _has_disclosure_phase(item.allowed_disclosure_policy):
            raise ContentAssetPublishError(
                "disclosure_policy_invalid",
                "CaseItem allowed_disclosure_policy must contain at least one phase.",
            )
        item.status = "published"
        item.published_by = actor_id
        item.published_at = datetime.now(UTC)
        item.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def publish_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        expected_hash = role_profile_content_hash(_role_profile_payload(item))
        if item.content_hash != expected_hash:
            raise ContentAssetPublishError(
                "content_hash_mismatch",
                "RoleProfile content_hash does not match current content.",
            )
        if item.persona_ref:
            persona = await self._db.get(Persona, item.persona_ref)
            if persona is None or persona.status != "active":
                raise ContentAssetPublishError(
                    "persona_ref_unavailable",
                    "RoleProfile persona_ref must point to an active Persona.",
                )
        item.status = "published"
        item.published_by = actor_id
        item.published_at = datetime.now(UTC)
        item.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def read_snapshot_reference(
        self, asset_type: str, asset_id: str
    ) -> dict[str, object] | None:
        if asset_type == "case_item":
            item = await self._db.get(CaseItem, asset_id)
            if item is None:
                return None
            return {
                "case_item_id": item.case_item_id,
                "status": item.status,
                "version": item.version,
                "content_hash": item.content_hash,
            }
        if asset_type == "role_profile":
            item = await self._db.get(RoleProfile, asset_id)
            if item is None:
                return None
            return {
                "role_profile_id": item.role_profile_id,
                "status": item.status,
                "version": item.version,
                "content_hash": item.content_hash,
            }
        return None


def case_item_content_hash(payload: object) -> str:
    return _content_hash(_without_hash_excluded_fields(_to_dict(payload)))


def role_profile_content_hash(payload: object) -> str:
    return _content_hash(_without_hash_excluded_fields(_to_dict(payload)))


def _case_item_payload(item: CaseItem) -> dict[str, object]:
    return {
        "industry": item.industry,
        "company_profile": item.company_profile,
        "customer_role": item.customer_role,
        "pain_points": list(item.pain_points or []),
        "objections": list(item.objections or []),
        "hidden_information": item.hidden_information,
        "success_criteria": list(item.success_criteria or []),
        "allowed_disclosure_policy": item.allowed_disclosure_policy or {},
    }


def _role_profile_payload(item: RoleProfile) -> dict[str, object]:
    return {
        "role_type": item.role_type,
        "role_name": item.role_name,
        "persona_ref": item.persona_ref,
        "communication_style": item.communication_style,
        "pressure_level": item.pressure_level,
        "knowledge_boundary": list(item.knowledge_boundary or []),
        "behavior_rules": list(item.behavior_rules or []),
        "voice_style_hint": item.voice_style_hint,
    }


def _has_disclosure_phase(policy: object) -> bool:
    return isinstance(policy, dict) and isinstance(policy.get("phases"), list) and bool(policy["phases"])


def _content_hash(payload: object) -> str:
    return (
        "sha256:"
        + sha256(
            dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
    )


def _without_hash_excluded_fields(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: _without_hash_excluded_fields(value)
            for key, value in payload.items()
            if key not in HASH_EXCLUDED_FIELDS
        }
    if isinstance(payload, list):
        return [_without_hash_excluded_fields(item) for item in payload]
    return payload


def _to_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, ModelDumpable):
        dumped = value.model_dump()
        return dumped
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }
