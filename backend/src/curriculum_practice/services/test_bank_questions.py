from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.error_handling.result import Result
from curriculum_practice.models import QuestionCategory, QuestionItem
from curriculum_practice.schemas import (
    PublishGateDecision,
    QuestionItemCreate,
    QuestionItemUpdate,
)
from curriculum_practice.services.orm_payload_typing import set_orm_field
from curriculum_practice.services.test_bank_constants import SERVER_ERROR
from curriculum_practice.services.test_bank_question_revision_payloads import (
    question_item_lifecycle_snapshot,
)
from curriculum_practice.services.test_bank_question_revision_service import (
    TestBankQuestionRevisionService,
)
from curriculum_practice.services.test_bank_question_rules import (
    criteria_with_dimensions,
    publish_decision,
    question_hash,
)


class TestBankQuestionServiceMixin:
    _db: AsyncSession

    async def get_category(self, category_id: str) -> Result[QuestionCategory]:
        raise NotImplementedError

    async def list_questions(
        self,
        *,
        category_id: str | None = None,
        difficulty: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        usage_scope: str | None = None,
    ) -> Result[list[QuestionItem]]:
        stmt = select(QuestionItem)
        if category_id:
            stmt = stmt.where(QuestionItem.category_id == category_id)
        if usage_scope:
            stmt = stmt.where(QuestionItem.usage_scope == usage_scope)
        if difficulty:
            stmt = stmt.where(QuestionItem.difficulty == difficulty)
        if status:
            stmt = stmt.where(QuestionItem.status == status)
        try:
            result = await self._db.execute(stmt.order_by(QuestionItem.updated_at.desc()))
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        questions = list(result.scalars().all())
        if tag:
            questions = [question for question in questions if tag in (question.tags or [])]
        return Result.ok(questions)

    async def get_question(self, question_id: str) -> Result[QuestionItem]:
        try:
            question = await self._db.get(QuestionItem, question_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if question is None:
            return Result.fail("[QUESTION_ITEM_NOT_FOUND]")
        return Result.ok(question)

    async def create_question(
        self, payload: QuestionItemCreate, *, actor_id: str | None
    ) -> Result[QuestionItem]:
        category_result = await self.get_category(payload.category_id)
        if not category_result.is_success:
            return Result.fail(category_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]")
        data = payload.model_dump()
        data["scoring_criteria"] = criteria_with_dimensions(
            data.get("scoring_criteria"), data.get("scoring_dimensions")
        )
        question = QuestionItem(
            **data, created_by=actor_id, updated_by=actor_id
        )
        self._db.add(question)
        try:
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def update_question(
        self,
        question: QuestionItem,
        payload: QuestionItemUpdate,
        *,
        actor_id: str | None,
    ) -> Result[QuestionItem]:
        if question.status == "published":
            return await self._stage_question_revision_update(
                question,
                payload,
                actor_id=actor_id,
            )
        if question.status != "draft":
            return Result.fail("[QUESTION_ITEM_NOT_EDITABLE]")
        data = payload.model_dump(exclude_unset=True)
        category_id = data.get("category_id")
        if category_id is not None:
            category_result = await self.get_category(str(category_id))
            if not category_result.is_success:
                return Result.fail(category_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]")
        if "scoring_dimensions" in data:
            data["scoring_criteria"] = criteria_with_dimensions(
                data.get("scoring_criteria", question.scoring_criteria),
                data.get("scoring_dimensions"),
            )
        for field, value in data.items():
            setattr(question, field, value)
        set_orm_field(question, "updated_by", actor_id)
        try:
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def publish_question(
        self, question: QuestionItem, *, actor_id: str | None
    ) -> Result[QuestionItem | PublishGateDecision]:
        if question.status == "archived":
            return Result.fail("[QUESTION_ITEM_NOT_EDITABLE]")
        actor_result = await self._actor_result(actor_id)
        if not actor_result.is_success or actor_result.value is None:
            return Result.fail(actor_result.fallback or "[QUESTION_ITEM_ACTOR_REQUIRED]")
        if question.status == "published":
            result = await self._publish_question_working_revision(
                question,
                actor=actor_result.value,
            )
            if not result.is_success:
                return Result(
                    value=(
                        result.value
                        if isinstance(result.value, PublishGateDecision)
                        else None
                    ),
                    fallback=result.fallback,
                    is_success=False,
                )
            if isinstance(result.value, QuestionItem):
                return Result.ok(result.value)
        decision = publish_decision(question)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[QUESTION_ITEM_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        previous_snapshot = question_item_lifecycle_snapshot(question)
        set_orm_field(question, "status", "published")
        set_orm_field(question, "published_by", actor_id)
        set_orm_field(question, "published_at", datetime.now(UTC))
        set_orm_field(question, "content_hash", question_hash(question))
        set_orm_field(question, "updated_by", actor_id)
        try:
            await TestBankQuestionRevisionService(
                self._db
            ).stage_initial_published_revision(
                question,
                actor=actor_result.value,
                previous_snapshot=previous_snapshot,
            )
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def archive_question(
        self, question: QuestionItem, *, actor_id: str | None
    ) -> Result[QuestionItem]:
        set_orm_field(question, "status", "archived")
        set_orm_field(question, "updated_by", actor_id)
        try:
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def _stage_question_revision_update(
        self,
        question: QuestionItem,
        payload: QuestionItemUpdate,
        *,
        actor_id: str | None,
    ) -> Result[QuestionItem]:
        actor_result = await self._actor_result(actor_id)
        if not actor_result.is_success or actor_result.value is None:
            return Result.fail(actor_result.fallback or "[QUESTION_ITEM_ACTOR_REQUIRED]")
        category_result = await self._validate_question_category_update(payload)
        if not category_result.is_success:
            return Result.fail(category_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]")
        try:
            await TestBankQuestionRevisionService(self._db).stage_future_revision(
                question,
                payload,
                actor=actor_result.value,
            )
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def _publish_question_working_revision(
        self,
        question: QuestionItem,
        *,
        actor: User,
    ) -> Result[QuestionItem | PublishGateDecision | bool]:
        try:
            working_result = await TestBankQuestionRevisionService(
                self._db
            ).stage_publish_working_revision(question, actor=actor)
            if not working_result.is_success:
                return Result(
                    value=(
                        working_result.value
                        if isinstance(working_result.value, PublishGateDecision)
                        else None
                    ),
                    fallback=working_result.fallback,
                    is_success=False,
                )
            if working_result.value:
                await self._db.commit()
                await self._db.refresh(question)
                return Result.ok(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(False)

    async def _actor_result(self, actor_id: str | None) -> Result[User]:
        if actor_id is None:
            return Result.fail("[QUESTION_ITEM_ACTOR_REQUIRED]")
        try:
            actor = await self._db.get(User, actor_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if actor is None:
            return Result.fail("[QUESTION_ITEM_ACTOR_REQUIRED]")
        return Result.ok(actor)

    async def _validate_question_category_update(
        self,
        payload: QuestionItemUpdate,
    ) -> Result[None]:
        data = payload.model_dump(exclude_unset=True)
        category_id = data.get("category_id")
        if category_id is None:
            return Result.ok(None)
        category_result = await self.get_category(str(category_id))
        if not category_result.is_success:
            return Result.fail(
                category_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]"
            )
        return Result.ok(None)
