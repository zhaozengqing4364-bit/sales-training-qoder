from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from curriculum_practice.models import QuestionCategory, QuestionItem
from curriculum_practice.schemas import QuestionCategoryCreate, QuestionCategoryUpdate
from curriculum_practice.services.test_bank import TestBankService
from sales_trainer.schemas import (
    SalesTrainerQuestionCategoryCreate,
    SalesTrainerQuestionCategoryUpdate,
    SalesTrainerQuestionCreate,
    SalesTrainerQuestionUpdate,
)
from sales_trainer.services.question_contracts import (
    SALES_TRAINER_QUESTION_SCOPE,
    to_question_item_create,
    to_question_item_update,
)
from sales_trainer.services.question_errors import SalesTrainerQuestionServiceError
from sales_trainer.services.question_payloads import (
    question_lifecycle_snapshot,
    serialize_sales_trainer_category,
    serialize_sales_trainer_question,
)
from sales_trainer.services.question_revision_service import (
    SalesTrainerQuestionRevisionService,
)

__all__ = [
    "SalesTrainerQuestionService",
    "SalesTrainerQuestionServiceError",
    "serialize_sales_trainer_category",
    "serialize_sales_trainer_question",
]


class SalesTrainerQuestionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._test_bank = TestBankService(db)
        self._revisions = SalesTrainerQuestionRevisionService(db)

    async def list_categories(self) -> tuple[list[QuestionCategory], int]:
        result = await self._test_bank.list_categories_by_scope(
            usage_scope=SALES_TRAINER_QUESTION_SCOPE
        )
        if not result.is_success:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_CATEGORY_LIST_FAILED]",
                "新人训练路径题目分类读取失败。",
                status_code=500,
            )
        categories = result.value or []
        return categories, len(categories)

    async def create_category(
        self,
        payload: SalesTrainerQuestionCategoryCreate,
        *,
        actor_id: str,
    ) -> QuestionCategory:
        result = await self._test_bank.create_category(
            QuestionCategoryCreate(
                **payload.model_dump(),
                usage_scope=SALES_TRAINER_QUESTION_SCOPE,
            ),
            actor_id=actor_id,
        )
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_CATEGORY_CREATE_FAILED]",
                "新人训练路径题目分类创建失败。",
                status_code=400,
            )
        return result.value

    async def update_category(
        self,
        category_id: str,
        payload: SalesTrainerQuestionCategoryUpdate,
        *,
        actor_id: str,
    ) -> QuestionCategory:
        category = await self._require_category(category_id)
        result = await self._test_bank.update_category(
            category,
            QuestionCategoryUpdate(
                **payload.model_dump(exclude_unset=True),
                usage_scope=SALES_TRAINER_QUESTION_SCOPE,
            ),
            actor_id=actor_id,
        )
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_CATEGORY_UPDATE_FAILED]",
                "新人训练路径题目分类更新失败。",
                status_code=400,
            )
        return result.value

    async def list_questions(
        self,
        *,
        category_id: str | None = None,
        difficulty: str | None = None,
        status: str | None = None,
        tag: str | None = None,
    ) -> tuple[list[QuestionItem], int]:
        result = await self._test_bank.list_questions(
            category_id=category_id,
            difficulty=difficulty,
            status=status,
            tag=tag,
            usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        )
        if not result.is_success:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_LIST_FAILED]",
                "新人训练路径题目读取失败。",
                status_code=500,
            )
        questions = result.value or []
        return questions, len(questions)

    async def create_question(
        self,
        payload: SalesTrainerQuestionCreate,
        *,
        actor_id: str,
    ) -> QuestionItem:
        await self._require_category(payload.category_id)
        result = await self._test_bank.create_question(
            to_question_item_create(payload),
            actor_id=actor_id,
        )
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_CREATE_FAILED]",
                "新人训练路径题目创建失败。",
                status_code=400,
            )
        return result.value

    async def get_question(self, question_id: str) -> QuestionItem:
        result = await self._test_bank.get_question(question_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_NOT_FOUND]",
                "新人训练路径题目不存在。",
                status_code=404,
            )
        question = result.value
        if question.usage_scope != SALES_TRAINER_QUESTION_SCOPE:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_ITEM_NOT_FOUND]",
                "新人训练路径题目不存在。",
                status_code=404,
            )
        return question

    async def update_question(
        self,
        question_id: str,
        payload: SalesTrainerQuestionUpdate,
        *,
        actor_id: str,
    ) -> QuestionItem:
        question = await self.get_question(question_id)
        if payload.category_id is not None:
            await self._require_category(payload.category_id)
        if question.status == "published":
            return await self._revisions.save_future_revision(
                question,
                payload,
                actor=await self._require_actor(actor_id),
            )
        if question.status != "draft":
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_ITEM_NOT_EDITABLE]",
                "归档题目不能修改；已发布题目编辑会生成新修订并只影响后续学员。",
                status_code=409,
            )
        result = await self._test_bank.update_question(
            question,
            to_question_item_update(question, payload),
            actor_id=actor_id,
        )
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_UPDATE_FAILED]",
                "新人训练路径题目更新失败。",
                status_code=400,
            )
        return result.value

    async def publish_question(self, question_id: str, *, actor_id: str) -> QuestionItem:
        question = await self.get_question(question_id)
        actor = await self._require_actor(actor_id)
        if question.status == "published" and await self._revisions.publish_working_revision(
            question,
            actor=actor,
        ):
            return question
        previous_snapshot = question_lifecycle_snapshot(question)
        result = await self._test_bank.publish_question(question, actor_id=actor_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_PUBLISH_FAILED]",
                "新人训练路径题目发布失败。",
                status_code=400,
            )
        await self._revisions.ensure_initial_published_revision(
            result.value,
            actor=actor,
            previous_snapshot=previous_snapshot,
        )
        return result.value

    async def archive_question(self, question_id: str, *, actor_id: str) -> QuestionItem:
        question = await self.get_question(question_id)
        result = await self._test_bank.archive_question(question, actor_id=actor_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_ARCHIVE_FAILED]",
                "新人训练路径题目归档失败。",
                status_code=400,
            )
        return result.value

    async def _require_category(self, category_id: str) -> QuestionCategory:
        result = await self._test_bank.get_category(category_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]",
                "新人训练路径题目分类不存在。",
                status_code=404,
            )
        category = result.value
        if category.usage_scope != SALES_TRAINER_QUESTION_SCOPE:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_CATEGORY_NOT_FOUND]",
                "新人训练路径题目分类不存在。",
                status_code=404,
            )
        return category

    async def _require_actor(self, actor_id: str) -> User:
        actor = await self._db.get(User, actor_id)
        if actor is None:
            raise SalesTrainerQuestionServiceError(
                "[ACTOR_NOT_FOUND]",
                "操作人不存在，无法记录发布治理审计。",
                status_code=403,
            )
        return actor
