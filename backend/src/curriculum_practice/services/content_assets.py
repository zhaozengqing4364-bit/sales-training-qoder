from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import CaseItem, RoleProfile
from curriculum_practice.schemas import CaseItemCreate, RoleProfileCreate
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.case_item_revision_service import (
    CaseItemRevisionService,
)
from curriculum_practice.services.content_asset_duplicates import (
    build_case_item_duplicate,
)
from curriculum_practice.services.content_asset_errors import (
    ContentAssetAlreadyDraftError,
    ContentAssetNotEditableError,
    ContentAssetPublishError,
    ContentAssetReferencedByTemplatesError,
)
from curriculum_practice.services.content_asset_payloads import (
    case_item_content_hash,
    case_item_payload,
    has_disclosure_phase,
    role_profile_content_hash,
)
from curriculum_practice.services.content_asset_payloads import (
    copy_suffix as _copy_suffix,
)
from curriculum_practice.services.content_asset_references import (
    list_published_template_references,
)
from curriculum_practice.services.orm_payload_typing import set_orm_field
from curriculum_practice.services.role_profile_asset_service import (
    RoleProfileAssetService,
)
from curriculum_practice.services.voice_clone import VoiceCloneResult, VoiceCloneService

__all__ = [
    "ContentAssetAlreadyDraftError",
    "ContentAssetNotEditableError",
    "ContentAssetPublishError",
    "ContentAssetReferencedByTemplatesError",
    "ContentAssetService",
    "_copy_suffix",
    "case_item_content_hash",
    "role_profile_content_hash",
]


class ContentAssetService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._role_profiles = RoleProfileAssetService(db)

    async def list_case_items(
        self, *, status: str | None = None, query: str | None = None
    ) -> list[CaseItem]:
        stmt = select(CaseItem)
        if status:
            stmt = stmt.where(CaseItem.status == status)
        if query:
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    CaseItem.industry.ilike(pattern),
                    CaseItem.customer_role.ilike(pattern),
                    CaseItem.company_profile.ilike(pattern),
                )
            )
        result = await self._db.execute(stmt.order_by(CaseItem.updated_at.desc()))
        return list(result.scalars().all())

    async def get_case_item(self, case_item_id: str) -> CaseItem | None:
        return await self._db.get(CaseItem, case_item_id)

    async def create_case_item(
        self, payload: CaseItemCreate, *, actor_id: str | None
    ) -> CaseItem:
        item = CaseItem(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(item)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def update_case_item(
        self, item: CaseItem, payload: CaseItemCreate, *, actor_id: str | None
    ) -> CaseItem:
        if item.status == "archived":
            raise ContentAssetNotEditableError
        if item.status == "published":
            await CaseItemRevisionService(self._db).save_future_revision(
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

    async def archive_case_item(
        self, item: CaseItem, *, actor_id: str | None
    ) -> CaseItem:
        set_orm_field(item, "status", "archived")
        set_orm_field(item, "updated_by", actor_id)
        await self._db.commit()
        await self._db.refresh(item)
        return item

    async def list_role_profiles(
        self, *, status: str | None = None, query: str | None = None
    ) -> list[RoleProfile]:
        return await self._role_profiles.list_role_profiles(status=status, query=query)

    async def get_role_profile(self, role_profile_id: str) -> RoleProfile | None:
        return await self._role_profiles.get_role_profile(role_profile_id)

    async def create_role_profile(
        self, payload: RoleProfileCreate, *, actor_id: str | None
    ) -> RoleProfile:
        return await self._role_profiles.create_role_profile(payload, actor_id=actor_id)

    async def update_role_profile(
        self, item: RoleProfile, payload: RoleProfileCreate, *, actor_id: str | None
    ) -> RoleProfile:
        return await self._role_profiles.update_role_profile(
            item, payload, actor_id=actor_id
        )

    async def archive_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        return await self._role_profiles.archive_role_profile(item, actor_id=actor_id)

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
        return await self._role_profiles.register_role_profile_voice(
            item,
            voice_service=voice_service,
            voice_name=voice_name,
            audio_bytes=audio_bytes,
            content_type=content_type,
            voice_sample_url=voice_sample_url,
            actor_id=actor_id,
        )

    async def publish_case_item(
        self, item: CaseItem, *, actor_id: str | None
    ) -> CaseItem:
        revision_service = CaseItemRevisionService(self._db)
        if item.status == "published":
            actor = await self._require_actor(actor_id)
            if await revision_service.publish_working_revision(item, actor=actor):
                await self._db.commit()
                await self._db.refresh(item)
                return item
        expected_hash = case_item_content_hash(case_item_payload(item))
        if item.content_hash != expected_hash:
            raise ContentAssetPublishError(
                "content_hash_mismatch",
                "CaseItem content_hash does not match current content.",
            )
        if not has_disclosure_phase(item.allowed_disclosure_policy):
            raise ContentAssetPublishError(
                "disclosure_policy_invalid",
                "CaseItem allowed_disclosure_policy must contain at least one phase.",
            )
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

    async def publish_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        return await self._role_profiles.publish_role_profile(item, actor_id=actor_id)

    async def duplicate_case_item(
        self, item: CaseItem, *, actor_id: str | None
    ) -> CaseItem:
        duplicate = build_case_item_duplicate(item, actor_id=actor_id)
        self._db.add(duplicate)
        await self._db.commit()
        await self._db.refresh(duplicate)
        return duplicate

    async def duplicate_role_profile(
        self, item: RoleProfile, *, actor_id: str | None
    ) -> RoleProfile:
        return await self._role_profiles.duplicate_role_profile(item, actor_id=actor_id)

    async def unpublish_case_item(
        self, item: CaseItem, *, actor_id: str | None, acknowledge: bool = False
    ) -> CaseItem:
        return cast(
            CaseItem,
            await self._unpublish_content_asset(
                item,
                asset_type="case_item",
                asset_id=str(item.case_item_id),
                actor_id=actor_id,
                acknowledge=acknowledge,
            ),
        )

    async def unpublish_role_profile(
        self, item: RoleProfile, *, actor_id: str | None, acknowledge: bool = False
    ) -> RoleProfile:
        return await self._role_profiles.unpublish_role_profile(
            item,
            actor_id=actor_id,
            acknowledge=acknowledge,
        )

    async def list_template_references(
        self,
        *,
        asset_type: Literal["case_item", "role_profile", "examiner_agent"],
        asset_id: str,
    ) -> list[dict[str, str]]:
        return await list_published_template_references(
            self._db, asset_type=asset_type, asset_id=asset_id
        )

    async def _unpublish_content_asset(
        self,
        item: CaseItem | RoleProfile,
        *,
        asset_type: Literal["case_item", "role_profile"],
        asset_id: str,
        actor_id: str | None,
        acknowledge: bool,
    ) -> CaseItem | RoleProfile:
        if item.status == "draft":
            raise ContentAssetAlreadyDraftError
        if item.status == "archived":
            raise ContentAssetNotEditableError
        references = await self.list_template_references(
            asset_type=asset_type,
            asset_id=asset_id,
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

    async def _require_actor(self, actor_id: str | None) -> User:
        actor = await self._optional_actor(actor_id)
        if actor is None:
            raise ContentAssetNotEditableError
        return actor

    async def _optional_actor(self, actor_id: str | None) -> User | None:
        if actor_id is None:
            return None
        return await self._db.get(User, actor_id)

    async def read_snapshot_reference(
        self, asset_type: str, asset_id: str
    ) -> dict[str, object] | None:
        return await CurriculumAssetReferenceReader(self._db).read_reference(
            asset_type,
            asset_id,
        )
