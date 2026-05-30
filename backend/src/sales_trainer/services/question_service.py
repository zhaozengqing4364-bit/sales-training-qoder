from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from curriculum_practice.models import QuestionCategory, QuestionItem
from curriculum_practice.schemas import (
    QuestionCategoryCreate,
    QuestionCategoryUpdate,
    QuestionItemCreate,
    QuestionItemUpdate,
)
from curriculum_practice.services.test_bank import TestBankService
from sales_trainer.rules import DEFAULT_QUESTION_DIMENSION
from sales_trainer.schemas import (
    SalesTrainerQuestionCategoryCreate,
    SalesTrainerQuestionCategoryUpdate,
    SalesTrainerQuestionCreate,
    SalesTrainerQuestionUpdate,
)

SALES_TRAINER_QUESTION_SCOPE = "sales_trainer"


class SalesTrainerQuestionServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class SalesTrainerQuestionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._test_bank = TestBankService(db)

    async def list_categories(self) -> tuple[list[QuestionCategory], int]:
        result = await self._test_bank.list_categories_by_scope(
            usage_scope=SALES_TRAINER_QUESTION_SCOPE
        )
        if not result.is_success:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_CATEGORY_LIST_FAILED]",
                "销售训练题目分类读取失败。",
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
                "销售训练题目分类创建失败。",
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
                "销售训练题目分类更新失败。",
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
                "销售训练题目读取失败。",
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
            _to_question_item_create(payload),
            actor_id=actor_id,
        )
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_CREATE_FAILED]",
                "销售训练题目创建失败。",
                status_code=400,
            )
        return result.value

    async def get_question(self, question_id: str) -> QuestionItem:
        result = await self._test_bank.get_question(question_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_NOT_FOUND]",
                "销售训练题目不存在。",
                status_code=404,
            )
        question = result.value
        if question.usage_scope != SALES_TRAINER_QUESTION_SCOPE:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_ITEM_NOT_FOUND]",
                "销售训练题目不存在。",
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
        update_payload = _to_question_item_update(question, payload)
        result = await self._test_bank.update_question(
            question,
            update_payload,
            actor_id=actor_id,
        )
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_UPDATE_FAILED]",
                "销售训练题目更新失败。",
                status_code=409 if result.fallback == "[QUESTION_ITEM_NOT_EDITABLE]" else 400,
            )
        return result.value

    async def publish_question(self, question_id: str, *, actor_id: str) -> QuestionItem:
        question = await self.get_question(question_id)
        result = await self._test_bank.publish_question(question, actor_id=actor_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_PUBLISH_FAILED]",
                "销售训练题目发布失败。",
                status_code=400,
            )
        return result.value

    async def archive_question(self, question_id: str, *, actor_id: str) -> QuestionItem:
        question = await self.get_question(question_id)
        result = await self._test_bank.archive_question(question, actor_id=actor_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_ITEM_ARCHIVE_FAILED]",
                "销售训练题目归档失败。",
                status_code=400,
            )
        return result.value

    async def _require_category(self, category_id: str) -> QuestionCategory:
        result = await self._test_bank.get_category(category_id)
        if not result.is_success or result.value is None:
            raise SalesTrainerQuestionServiceError(
                result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]",
                "销售训练题目分类不存在。",
                status_code=404,
            )
        category = result.value
        if category.usage_scope != SALES_TRAINER_QUESTION_SCOPE:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_CATEGORY_NOT_FOUND]",
                "销售训练题目分类不存在。",
                status_code=404,
            )
        return category


def serialize_sales_trainer_category(category: QuestionCategory) -> dict[str, Any]:
    return {
        "category_id": category.category_id,
        "parent_id": category.parent_id,
        "name": category.name,
        "description": category.description,
        "usage_scope": category.usage_scope,
        "order_index": category.order_index,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


def serialize_sales_trainer_question(question: QuestionItem) -> dict[str, Any]:
    criteria = question.scoring_criteria or {}
    question_type = str(criteria.get("question_type") or "short_answer")
    return {
        "question_id": question.question_id,
        "title": question.title,
        "stem": question.stem,
        "reference_answer": question.reference_answer,
        "category_id": question.category_id,
        "question_type": question_type,
        "difficulty": question.difficulty,
        "status": question.status,
        "tags": question.tags or [],
        "scoring_dimensions": question.scoring_dimensions or [],
        "scoring_criteria": criteria,
        "safety_flagged": question.safety_flagged,
        "department": question.department,
        "usage_scope": question.usage_scope,
        "version": question.version,
        "content_hash": question.content_hash,
        "published_at": question.published_at,
        "created_at": question.created_at,
        "updated_at": question.updated_at,
        "options": criteria.get("options") or [],
        "correct_answer": criteria.get("correct_answer"),
        "correct_answers": criteria.get("correct_answers") or [],
        "correct_bool": criteria.get("correct_bool"),
        "explanation": criteria.get("explanation"),
        "ai_scoring": criteria.get("ai_scoring"),
    }


def _to_question_item_create(payload: SalesTrainerQuestionCreate) -> QuestionItemCreate:
    criteria, dimensions, reference_answer = _build_question_contract(payload)
    return QuestionItemCreate(
        category_id=payload.category_id,
        title=payload.title,
        stem=payload.stem,
        reference_answer=reference_answer,
        scoring_criteria=criteria,
        scoring_dimensions=dimensions,
        tags=payload.tags,
        usage_scope=SALES_TRAINER_QUESTION_SCOPE,
        difficulty=payload.difficulty,
        safety_flagged=payload.safety_flagged,
        department=payload.department,
    )


def _to_question_item_update(
    current: QuestionItem,
    payload: SalesTrainerQuestionUpdate,
) -> QuestionItemUpdate:
    merged = _merge_question_payload(current, payload)
    criteria, dimensions, reference_answer = _build_question_contract(merged)
    incoming = payload.model_dump(exclude_unset=True)
    data: dict[str, Any] = {
        "reference_answer": reference_answer,
        "scoring_criteria": criteria,
        "scoring_dimensions": dimensions,
        "usage_scope": SALES_TRAINER_QUESTION_SCOPE,
    }
    for field in (
        "title",
        "stem",
        "category_id",
        "tags",
        "difficulty",
        "safety_flagged",
        "department",
    ):
        if field in incoming:
            data[field] = incoming[field]
    return QuestionItemUpdate(**data)


def _merge_question_payload(
    current: QuestionItem,
    payload: SalesTrainerQuestionUpdate,
) -> SalesTrainerQuestionCreate:
    criteria = current.scoring_criteria or {}
    return SalesTrainerQuestionCreate(
        title=payload.title or str(current.title),
        stem=payload.stem or str(current.stem),
        category_id=payload.category_id or str(current.category_id),
        question_type=payload.question_type
        or str(criteria.get("question_type") or "short_answer"),
        difficulty=payload.difficulty or str(current.difficulty),
        tags=payload.tags if payload.tags is not None else list(current.tags or []),
        department=payload.department if payload.department is not None else current.department,
        safety_flagged=payload.safety_flagged
        if payload.safety_flagged is not None
        else bool(current.safety_flagged),
        options=payload.options
        if payload.options is not None
        else list(criteria.get("options") or []),
        correct_answer=payload.correct_answer
        if payload.correct_answer is not None
        else criteria.get("correct_answer"),
        correct_answers=payload.correct_answers
        if payload.correct_answers is not None
        else list(criteria.get("correct_answers") or []),
        correct_bool=payload.correct_bool
        if payload.correct_bool is not None
        else criteria.get("correct_bool"),
        reference_answer=payload.reference_answer
        if payload.reference_answer is not None
        else current.reference_answer,
        scoring_dimensions=payload.scoring_dimensions
        if payload.scoring_dimensions is not None
        else list(current.scoring_dimensions or []),
        explanation=payload.explanation
        if payload.explanation is not None
        else criteria.get("explanation"),
        ai_scoring=payload.ai_scoring
        if payload.ai_scoring is not None
        else _existing_ai_scoring_config(criteria),
    )


def _build_question_contract(
    payload: SalesTrainerQuestionCreate,
) -> tuple[dict[str, Any], list[str], str]:
    dimensions = _normalized_dimensions(payload.scoring_dimensions)
    explanation = (payload.explanation or "").strip()
    if payload.question_type == "single_choice":
        options = _normalized_options(payload.options)
        if not options:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_OPTIONS_REQUIRED]",
                "单选题必须配置选项。",
                status_code=422,
            )
        if not payload.correct_answer or payload.correct_answer not in {
            option["value"] for option in options
        }:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_CORRECT_ANSWER_INVALID]",
                "单选题正确答案必须命中选项值。",
                status_code=422,
            )
        return (
            {
                "question_type": "single_choice",
                "options": options,
                "correct_answer": payload.correct_answer,
                "dimensions": dimensions,
                **({"explanation": explanation} if explanation else {}),
            },
            dimensions,
            _choice_reference_answer(options, [payload.correct_answer]),
        )
    if payload.question_type == "multiple_choice":
        options = _normalized_options(payload.options)
        option_values = {option["value"] for option in options}
        correct_answers = _dedupe(payload.correct_answers)
        if not options:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_OPTIONS_REQUIRED]",
                "多选题必须配置选项。",
                status_code=422,
            )
        if not correct_answers or any(value not in option_values for value in correct_answers):
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_CORRECT_ANSWER_INVALID]",
                "多选题正确答案必须全部命中选项值。",
                status_code=422,
            )
        return (
            {
                "question_type": "multiple_choice",
                "options": options,
                "correct_answers": correct_answers,
                "dimensions": dimensions,
                **({"explanation": explanation} if explanation else {}),
            },
            dimensions,
            _choice_reference_answer(options, correct_answers),
        )
    if payload.question_type == "true_false":
        if payload.correct_bool is None:
            raise SalesTrainerQuestionServiceError(
                "[QUESTION_CORRECT_ANSWER_INVALID]",
                "判断题必须配置正确/错误。",
                status_code=422,
            )
        return (
            {
                "question_type": "true_false",
                "correct_bool": payload.correct_bool,
                "dimensions": dimensions,
                **({"explanation": explanation} if explanation else {}),
            },
            dimensions,
            "正确" if payload.correct_bool else "错误",
        )
    reference_answer = (payload.reference_answer or "").strip()
    if not reference_answer:
        raise SalesTrainerQuestionServiceError(
            "[QUESTION_REFERENCE_ANSWER_REQUIRED]",
            "简答题必须配置参考答案。",
            status_code=422,
        )
    return (
        {
            "question_type": "short_answer",
            "dimensions": dimensions,
            **({"explanation": explanation} if explanation else {}),
            **(
                {"ai_scoring": payload.ai_scoring.model_dump(exclude_none=True)}
                if payload.ai_scoring is not None
                else {}
            ),
        },
        dimensions,
        reference_answer,
    )


def _normalized_options(options: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for option in options:
        if hasattr(option, "model_dump"):
            option = option.model_dump()
        if not isinstance(option, dict):
            continue
        value = str(option.get("value") or "").strip()
        label = str(option.get("label") or "").strip()
        if not value or not label or value in seen:
            continue
        normalized.append({"value": value, "label": label})
        seen.add(value)
    return normalized


def _normalized_dimensions(values: list[str]) -> list[str]:
    normalized = _dedupe(values)
    return normalized or [DEFAULT_QUESTION_DIMENSION]


def _dedupe(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _choice_reference_answer(options: list[dict[str, str]], answers: list[str]) -> str:
    labels = [
        f"{option['value']}. {option['label']}"
        for option in options
        if option["value"] in set(answers)
    ]
    return "；".join(labels)


def _existing_ai_scoring_config(criteria: dict[str, Any]) -> dict[str, Any] | None:
    value = criteria.get("ai_scoring")
    return dict(value) if isinstance(value, dict) else None
