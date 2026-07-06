from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from common.db.models import User
from curriculum_practice.models import RoleProfile
from curriculum_practice.schemas import RoleProfileCreate
from curriculum_practice.services.content_asset_errors import (
    ContentAssetAlreadyDraftError,
    ContentAssetNotEditableError,
    ContentAssetPublishError,
    ContentAssetReferencedByTemplatesError,
)
from curriculum_practice.services.content_asset_payloads import (
    copy_suffix,
    role_profile_content_hash,
    role_profile_payload,
)
from curriculum_practice.services.content_asset_references import (
    list_published_template_references,
)
from curriculum_practice.services.orm_payload_typing import (
    orm_optional_str,
    orm_str,
    set_orm_field,
)
from curriculum_practice.services.role_profile_revision_service import (
    RoleProfileRevisionService,
)
from curriculum_practice.services.voice_clone import VoiceCloneResult, VoiceCloneService


class RoleProfileAssetService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_role_profiles(
        self, *, status: str | None = None, query: str | None = None
    ) -> list[RoleProfile]:
        stmt = select(RoleProfile)
        if status:
            stmt = stmt.where(RoleProfile.status == status)
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    RoleProfile.role_name.ilike(pattern),
                    RoleProfile.role_type.ilike(pattern),
                    RoleProfile.communication_style.ilike(pattern),
                )
            )
        result = await self._db.execute(stmt.order_by(RoleProfile.updated_at.desc()))
        return list(result.scalars().all())

    async def get_role_profile(self, role_profile_id: str) -> RoleProfile | None:
        return await self._db.get(RoleProfile, role_profile_id)

    async def create_role_profile(
        self, payload: RoleProfileCreate, *, actor_id: str | None
    ) -> RoleProfile:
        await self._ensure_persona_ref_available(payload.persona_ref)
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
        if item.status == "archived":
            raise ContentAssetNotEditableError
        await self._ensure_persona_ref_available(payload.persona_ref)
        if item.status == "published":
            await RoleProfileRevisionService(self._db).save_future_revision(
                item,
                payload,
                actor=await self._require_actor(actor_id),
            )
            await self._db.commit()
            await self._db.refresh(item)
            return item
        for field, value in payload.model_dump().items():
            setattr(item, field, value)
        set_orm_field(item, "updated_by", actor_id)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def archive_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        set_orm_field(item, "status", "archived")
        set_orm_field(item, "updated_by", actor_id)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def register_role_profile_voice(
        self,
        item: RoleProfile,
        *,
        voice_service: VoiceCloneService,
        voice_name: str,
        audio_bytes: bytes,
        content_type: str,
        voice_sample_url: str,
        actor_id: str | None,
    ) -> VoiceCloneResult:
        if item.status != "draft":
            raise ContentAssetNotEditableError
        result = await voice_service.create_voice(
            voice_name=voice_name,
            audio_bytes=audio_bytes,
            content_type=content_type,
        )
        if not result.ok or not result.voice_id:
            return result
        set_orm_field(item, "voice_id", result.voice_id)
        set_orm_field(item, "voice_sample_url", voice_sample_url)
        set_orm_field(
            item,
            "content_hash",
            role_profile_content_hash(role_profile_payload(item)),
        )
        set_orm_field(item, "updated_by", actor_id)
        await self._db.commit()
        await self._db.refresh(item)
        return result

    async def publish_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        revision_service = RoleProfileRevisionService(self._db)
        if item.status == "published":
            actor = await self._require_actor(actor_id)
            if await revision_service.publish_working_revision(item, actor=actor):
                await self._db.commit()
                await self._db.refresh(item)
                return item
        expected_hash = role_profile_content_hash(role_profile_payload(item))
        if item.content_hash != expected_hash:
            raise ContentAssetPublishError(
                "content_hash_mismatch",
                "RoleProfile content_hash does not match current content.",
            )
        await self._ensure_persona_ref_available(orm_optional_str(item.persona_ref))
        set_orm_field(item, "status", "published")
        set_orm_field(item, "published_by", actor_id)
        set_orm_field(item, "published_at", datetime.now(UTC))
        set_orm_field(item, "updated_by", actor_id)
        initial_actor = await self._optional_actor(actor_id)
        if initial_actor is not None:
            await revision_service.ensure_initial_published_revision(
                item,
                actor=initial_actor,
            )
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def duplicate_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        payload = role_profile_payload(item)
        payload["role_name"] = copy_suffix(orm_str(item.role_name))
        content_hash = role_profile_content_hash(payload)
        duplicate = RoleProfile(
            role_profile_id=str(uuid.uuid4()),
            role_type=item.role_type,
            role_name=str(payload["role_name"]),
            persona_ref=item.persona_ref,
            communication_style=item.communication_style,
            pressure_level=item.pressure_level,
            knowledge_boundary=list(item.knowledge_boundary or []),
            behavior_rules=list(item.behavior_rules or []),
            voice_style_hint=item.voice_style_hint,
            version=1,
            content_hash=content_hash,
            status="draft",
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._db.add(duplicate)
        await self._db.commit()
        await self._db.refresh(duplicate)
        return duplicate

    async def unpublish_role_profile(
        self, item: RoleProfile, *, actor_id: str | None, acknowledge: bool = False
    ) -> RoleProfile:
        if item.status == "draft":
            raise ContentAssetAlreadyDraftError
        if item.status == "archived":
            raise ContentAssetNotEditableError
        references = await list_published_template_references(
            self._db,
            asset_type="role_profile",
            asset_id=str(item.role_profile_id),
        )
        if references and not acknowledge:
            raise ContentAssetReferencedByTemplatesError(references)
        set_orm_field(item, "status", "draft")
        set_orm_field(item, "published_at", None)
        set_orm_field(item, "published_by", None)
        set_orm_field(item, "updated_by", actor_id)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def _ensure_persona_ref_available(self, persona_ref: str | None) -> None:
        if not persona_ref:
            return
        persona = await self._db.get(Persona, persona_ref)
        if persona is None or persona.status != "active":
            raise ContentAssetPublishError(
                "persona_ref_unavailable",
                "RoleProfile persona_ref must point to an active Persona.",
            )

    async def _require_actor(self, actor_id: str | None) -> User:
        actor = await self._optional_actor(actor_id)
        if actor is None:
            raise ContentAssetNotEditableError
        return actor

    async def _optional_actor(self, actor_id: str | None) -> User | None:
        if actor_id is None:
            return None
        return await self._db.get(User, actor_id)
