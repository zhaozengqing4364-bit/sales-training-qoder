from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import LearningContent
from curriculum_practice.schemas import (
    LearningContentCreate,
    LearningContentUpdate,
)
from curriculum_practice.services.learning_chapter_service import (
    LearningChapterServiceMixin,
)
from curriculum_practice.services.learning_content_publish_gates import (
    learning_content_publish_decision,
)
from curriculum_practice.services.learning_content_revision_payloads import (
    learning_content_lifecycle_snapshot,
    learning_content_payload_hash,
)
from curriculum_practice.services.learning_content_revision_service import (
    LearningContentRevisionService,
)

SERVER_ERROR = "[LEARNING_CONTENT_SERVICE_FAILED]"


class LearningContentService(LearningChapterServiceMixin):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_contents(
        self, *, status: str | None = None
    ) -> Result[list[LearningContent]]:
        stmt = select(LearningContent)
        if status:
            stmt = stmt.where(LearningContent.status == status)
        try:
            result = await self._db.execute(
                stmt.order_by(LearningContent.updated_at.desc())
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(list(result.scalars().all()))

    async def get_content(self, content_id: str) -> Result[LearningContent]:
        try:
            content = await self._db.get(LearningContent, content_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if content is None:
            return Result.fail("[LEARNING_CONTENT_NOT_FOUND]")
        return Result.ok(content)

    async def create_content(
        self, payload: LearningContentCreate, *, actor_id: str | None
    ) -> Result[LearningContent]:
        content = LearningContent(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(content)
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def update_content(
        self,
        content: LearningContent,
        payload: LearningContentUpdate,
        *,
        actor_id: str | None,
    ) -> Result[LearningContent]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        if content.status == "published":
            actor_result = await self._actor_result(actor_id)
            if not actor_result.is_success or actor_result.value is None:
                return Result.fail(actor_result.fallback or "[LEARNING_CONTENT_ACTOR_REQUIRED]")
            chapters_result = await self.list_chapters(content.learning_content_id)
            if not chapters_result.is_success:
                return Result.fail(chapters_result.fallback or SERVER_ERROR)
            try:
                await LearningContentRevisionService(self._db).stage_future_revision(
                    content,
                    chapters_result.value or [],
                    payload,
                    actor=actor_result.value,
                )
                await self._db.commit()
                await self._db.refresh(content)
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)
            return Result.ok(content)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(content, field, value)
        content.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def archive_content(
        self, content: LearningContent, *, actor_id: str | None
    ) -> Result[LearningContent]:
        content.status = "archived"
        content.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def delete_content(self, content: LearningContent) -> Result[None]:
        editable_result = self._editable_result(content)
        if not editable_result.is_success:
            return Result.fail(editable_result.fallback or "[LEARNING_CONTENT_NOT_EDITABLE]")
        if content.status != "draft":
            return Result.fail("[LEARNING_CONTENT_NOT_EDITABLE]")
        try:
            await self._db.delete(content)
            await self._db.commit()
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(None)

    async def publish_content(
        self, content: LearningContent, *, actor_id: str | None
    ) -> Result[LearningContent]:
        if content.status == "archived":
            return Result.fail("[LEARNING_CONTENT_NOT_EDITABLE]")
        actor_result = await self._actor_result(actor_id)
        if not actor_result.is_success or actor_result.value is None:
            return Result.fail(actor_result.fallback or "[LEARNING_CONTENT_ACTOR_REQUIRED]")
        if content.status == "published":
            try:
                working_result = await LearningContentRevisionService(
                    self._db
                ).stage_publish_working_revision(content, actor=actor_result.value)
                if not working_result.is_success:
                    return Result.fail(
                        working_result.fallback
                        or "[LEARNING_CONTENT_PUBLISH_GATE_FAILED]"
                    )
                if working_result.value:
                    await self._db.commit()
                    await self._db.refresh(content)
                    return Result.ok(content)
            except SQLAlchemyError:
                await self._db.rollback()
                return Result.fail(SERVER_ERROR)
        chapters_result = await self.list_chapters(content.learning_content_id)
        if not chapters_result.is_success:
            return Result.fail(chapters_result.fallback or SERVER_ERROR)
        chapters = chapters_result.value or []
        decision = learning_content_publish_decision(content, chapters)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[LEARNING_CONTENT_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        if content.status != "published":
            content.status = "published"
            content.published_by = actor_id
            content.published_at = datetime.now(UTC)
        content.content_hash = learning_content_payload_hash(
            learning_content_lifecycle_snapshot(content, chapters)
        )
        content.updated_by = actor_id
        try:
            await LearningContentRevisionService(
                self._db
            ).stage_initial_published_revision(
                content,
                chapters,
                actor=actor_result.value,
            )
            await self._db.commit()
            await self._db.refresh(content)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(content)

    async def _actor_result(self, actor_id: str | None) -> Result[User]:
        if actor_id is None:
            return Result.fail("[LEARNING_CONTENT_ACTOR_REQUIRED]")
        try:
            actor = await self._db.get(User, actor_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if actor is None:
            return Result.fail("[LEARNING_CONTENT_ACTOR_REQUIRED]")
        return Result.ok(actor)

