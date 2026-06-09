from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    PracticeTemplateCreate,
    PracticeTemplateUpdate,
    PublishGateDecision,
)
from curriculum_practice.services.practice_template_revision_metadata import (
    template_payload_hash,
)
from curriculum_practice.services.practice_template_revision_payloads import (
    published_ref as published_ref,
)
from curriculum_practice.services.practice_template_revision_payloads import (
    serialize_template as serialize_template,
)
from curriculum_practice.services.practice_template_revision_payloads import (
    template_lifecycle_snapshot,
)
from curriculum_practice.services.practice_template_revision_service import (
    PracticeTemplateRevisionService,
)


class PracticeTemplateNotEditableError(ValueError):
    pass


class PracticeTemplateService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_templates(self) -> list[PracticeTemplate]:
        result = await self._db.execute(
            select(PracticeTemplate).order_by(PracticeTemplate.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_template(self, template_id: str) -> PracticeTemplate | None:
        return await self._db.get(PracticeTemplate, template_id)

    async def create_template(
        self, payload: PracticeTemplateCreate, *, actor_id: str | None
    ) -> PracticeTemplate:
        template = PracticeTemplate(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(template)
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def import_template(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
    ) -> PracticeTemplate:
        """Create a draft-equivalent template from a validated import bundle."""

        template = PracticeTemplate(
            **payload,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self._db.add(template)
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def update_template(
        self,
        template: PracticeTemplate,
        payload: PracticeTemplateUpdate,
        *,
        actor_id: str | None,
    ) -> PracticeTemplate:
        if template.status == "archived":
            raise PracticeTemplateNotEditableError
        if template.status == "published":
            actor = await self._actor(actor_id)
            await PracticeTemplateRevisionService(self._db).stage_future_revision(
                template,
                payload,
                actor=actor,
            )
            await self._db.commit()
            await self._db.refresh(template)
            return template
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(template, field, value)
        template.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def archive_template(
        self, template: PracticeTemplate, *, actor_id: str | None
    ) -> PracticeTemplate:
        template.status = "archived"
        template.updated_by = actor_id
        await self._db.commit()
        await self._db.refresh(template)
        return template

    async def publish_template(
        self, template: PracticeTemplate, *, actor_id: str | None
    ) -> tuple[PracticeTemplate | None, PublishGateDecision]:
        if template.status == "archived":
            raise PracticeTemplateNotEditableError
        actor = await self._actor(actor_id)
        revision_service = PracticeTemplateRevisionService(self._db)
        if template.status == "published":
            working_applied, working_decision = (
                await revision_service.stage_publish_working_revision(
                    template,
                    actor=actor,
                )
            )
            if not working_decision.can_publish:
                return None, working_decision
            if working_applied:
                await self._db.commit()
                await self._db.refresh(template)
                return template, working_decision

        decision, published_asset_refs, situation_pack_code = (
            await revision_service.validate_current_template(template)
        )
        if not decision.can_publish:
            return None, decision

        template.status = "published"
        template.published_by = actor_id
        template.published_at = datetime.now(UTC)
        template.content_hash = template_payload_hash(
            template_lifecycle_snapshot(template)
        )
        template.situation_pack_code = situation_pack_code
        template.published_asset_refs = published_asset_refs
        await revision_service.stage_initial_published_revision(template, actor=actor)
        await self._db.commit()
        await self._db.refresh(template)
        return template, decision

    async def _actor(self, actor_id: str | None) -> User:
        if actor_id is None:
            raise PracticeTemplateNotEditableError
        try:
            actor = await self._db.get(User, actor_id)
        except SQLAlchemyError as exc:
            raise PracticeTemplateNotEditableError from exc
        if actor is None:
            raise PracticeTemplateNotEditableError
        return actor
