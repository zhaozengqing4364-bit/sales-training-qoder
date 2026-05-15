from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from json import dumps
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.error_handling.result import Result
from curriculum_practice.models import QuestionCategory, QuestionItem, TestBankImportJob
from curriculum_practice.schemas import (
    GateResult,
    PublishGateDecision,
    QuestionCategoryCreate,
    QuestionCategoryResponse,
    QuestionCategoryUpdate,
    QuestionItemCreate,
    QuestionItemResponse,
    QuestionItemUpdate,
    TestBankImportJobResponse,
    TestBankImportResultResponse,
)
from curriculum_practice.services.test_bank_importer import (
    ImportRowError,
    TestBankImporter,
)

SERVER_ERROR = "[TEST_BANK_SERVICE_FAILED]"


class TestBankService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_categories(self) -> Result[list[QuestionCategory]]:
        try:
            result = await self._db.execute(
                select(QuestionCategory).order_by(
                    QuestionCategory.parent_id.asc(),
                    QuestionCategory.order_index.asc(),
                    QuestionCategory.created_at.asc(),
                )
            )
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        return Result.ok(list(result.scalars().all()))

    async def get_category(self, category_id: str) -> Result[QuestionCategory]:
        try:
            category = await self._db.get(QuestionCategory, category_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if category is None:
            return Result.fail("[QUESTION_CATEGORY_NOT_FOUND]")
        return Result.ok(category)

    async def create_category(
        self, payload: QuestionCategoryCreate, *, actor_id: str | None
    ) -> Result[QuestionCategory]:
        if payload.parent_id is not None:
            parent_result = await self.get_category(payload.parent_id)
            if not parent_result.is_success:
                return Result.fail(parent_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]")
        category = QuestionCategory(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
        )
        self._db.add(category)
        try:
            await self._db.commit()
            await self._db.refresh(category)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(category)

    async def update_category(
        self,
        category: QuestionCategory,
        payload: QuestionCategoryUpdate,
        *,
        actor_id: str | None,
    ) -> Result[QuestionCategory]:
        data = payload.model_dump(exclude_unset=True)
        parent_id = data.get("parent_id")
        if parent_id is not None:
            if parent_id == category.category_id:
                return Result.fail("[QUESTION_CATEGORY_PARENT_INVALID]")
            parent_result = await self.get_category(str(parent_id))
            if not parent_result.is_success:
                return Result.fail(parent_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]")
        for field, value in data.items():
            setattr(category, field, value)
        category.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(category)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(category)

    async def delete_category(self, category: QuestionCategory) -> Result[None]:
        child_count = await self._count_categories(parent_id=category.category_id)
        if child_count is None:
            return Result.fail(SERVER_ERROR)
        if child_count > 0:
            return Result.fail("[QUESTION_CATEGORY_HAS_CHILDREN]")
        question_count = await self._count_questions(category_id=category.category_id)
        if question_count is None:
            return Result.fail(SERVER_ERROR)
        if question_count > 0:
            return Result.fail("[QUESTION_CATEGORY_HAS_QUESTIONS]")
        try:
            await self._db.delete(category)
            await self._db.commit()
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(None)

    async def list_questions(
        self,
        *,
        category_id: str | None = None,
        difficulty: str | None = None,
        status: str | None = None,
        tag: str | None = None,
    ) -> Result[list[QuestionItem]]:
        stmt = select(QuestionItem)
        if category_id:
            stmt = stmt.where(QuestionItem.category_id == category_id)
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
        question = QuestionItem(
            **payload.model_dump(), created_by=actor_id, updated_by=actor_id
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
        if question.status != "draft":
            return Result.fail("[QUESTION_ITEM_NOT_EDITABLE]")
        data = payload.model_dump(exclude_unset=True)
        category_id = data.get("category_id")
        if category_id is not None:
            category_result = await self.get_category(str(category_id))
            if not category_result.is_success:
                return Result.fail(category_result.fallback or "[QUESTION_CATEGORY_NOT_FOUND]")
        for field, value in data.items():
            setattr(question, field, value)
        question.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def publish_question(
        self, question: QuestionItem, *, actor_id: str | None
    ) -> Result[QuestionItem]:
        if question.status == "archived":
            return Result.fail("[QUESTION_ITEM_NOT_EDITABLE]")
        decision = _publish_decision(question)
        if not decision.can_publish:
            return Result(
                value=decision,
                fallback="[QUESTION_ITEM_PUBLISH_GATE_FAILED]",
                is_success=False,
            )
        question.status = "published"
        question.published_by = actor_id
        question.published_at = datetime.now(UTC)
        question.content_hash = _question_hash(question)
        question.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def archive_question(
        self, question: QuestionItem, *, actor_id: str | None
    ) -> Result[QuestionItem]:
        question.status = "archived"
        question.updated_by = actor_id
        try:
            await self._db.commit()
            await self._db.refresh(question)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(question)

    async def create_import_job(
        self,
        *,
        filename: str,
        actor_id: str | None,
    ) -> Result[TestBankImportJob]:
        job = TestBankImportJob(filename=filename, created_by=actor_id)
        self._db.add(job)
        try:
            await self._db.commit()
            await self._db.refresh(job)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(job)

    async def get_import_job(self, task_id: str) -> Result[TestBankImportJob]:
        try:
            job = await self._db.get(TestBankImportJob, task_id)
        except SQLAlchemyError:
            return Result.fail(SERVER_ERROR)
        if job is None:
            return Result.fail("[TEST_BANK_IMPORT_JOB_NOT_FOUND]")
        return Result.ok(job)

    async def run_import_job(
        self,
        job: TestBankImportJob,
        *,
        raw: bytes,
        actor_id: str | None,
    ) -> Result[TestBankImportJob]:
        categories = await self.list_categories()
        if not categories.is_success:
            return Result.fail(categories.fallback or SERVER_ERROR)
        job.status = "processing"
        await self._persist_job(job)

        importer = TestBankImporter(
            known_category_ids={category.category_id for category in categories.value or []}
        )
        parsed = importer.parse(raw, filename=job.filename)
        imported_count = 0
        errors: list[ImportRowError] = list(parsed.errors)
        for item in parsed.items:
            create_result = await self.create_question(item, actor_id=actor_id)
            if create_result.is_success:
                imported_count += 1
            else:
                errors.append(
                    ImportRowError(
                        row=0,
                        field="file",
                        message=create_result.fallback or "question import failed",
                    )
                )
        job.status = "completed"
        job.imported = imported_count
        job.failed = len({error.row for error in errors})
        job.errors = [
            {"row": error.row, "field": error.field, "message": error.message}
            for error in errors
        ]
        return await self._persist_job(job)

    async def _count_categories(self, *, parent_id: str) -> int | None:
        try:
            result = await self._db.execute(
                select(func.count()).select_from(QuestionCategory).where(
                    QuestionCategory.parent_id == parent_id
                )
            )
        except SQLAlchemyError:
            return None
        return int(result.scalar_one())

    async def _count_questions(self, *, category_id: str) -> int | None:
        try:
            result = await self._db.execute(
                select(func.count()).select_from(QuestionItem).where(
                    QuestionItem.category_id == category_id
                )
            )
        except SQLAlchemyError:
            return None
        return int(result.scalar_one())

    async def _persist_job(self, job: TestBankImportJob) -> Result[TestBankImportJob]:
        try:
            await self._db.commit()
            await self._db.refresh(job)
        except SQLAlchemyError:
            await self._db.rollback()
            return Result.fail(SERVER_ERROR)
        return Result.ok(job)


def serialize_category(category: QuestionCategory) -> QuestionCategoryResponse:
    return QuestionCategoryResponse.model_validate(category)


def serialize_question(question: QuestionItem) -> QuestionItemResponse:
    return QuestionItemResponse.model_validate(question)


def serialize_import_job(job: TestBankImportJob) -> TestBankImportJobResponse:
    return TestBankImportJobResponse(
        task_id=job.task_id,
        status=job.status,
        result=TestBankImportResultResponse(
            imported=job.imported,
            failed=job.failed,
            errors=job.errors or [],
        ),
    )


def _publish_decision(question: QuestionItem) -> PublishGateDecision:
    results: list[GateResult] = []
    if not (question.reference_answer or "").strip():
        results.append(
            _gate(
                "reference_answer",
                "missing_reference_answer",
                "QuestionItem requires a reference answer before publish.",
            )
        )
    criteria_dimensions = (question.scoring_criteria or {}).get("dimensions")
    if not isinstance(criteria_dimensions, list) or not criteria_dimensions:
        results.append(
            _gate(
                "scoring_criteria",
                "invalid_scoring_criteria",
                "QuestionItem scoring_criteria.dimensions must be non-empty.",
            )
        )
    if not isinstance(question.scoring_dimensions, list) or not question.scoring_dimensions:
        results.append(
            _gate(
                "scoring_dimensions",
                "invalid_scoring_dimensions",
                "QuestionItem scoring_dimensions must be non-empty.",
            )
        )
    if question.safety_flagged:
        results.append(
            _gate(
                "question_safety",
                "security_flagged_question",
                "Security flagged questions cannot be published.",
            )
        )
    return PublishGateDecision(can_publish=not results, results=results)


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )


def _question_hash(question: QuestionItem) -> str:
    payload: dict[str, Any] = {
        "category_id": question.category_id,
        "title": question.title,
        "stem": question.stem,
        "reference_answer": question.reference_answer,
        "scoring_criteria": question.scoring_criteria,
        "scoring_dimensions": question.scoring_dimensions,
        "tags": question.tags,
        "difficulty": question.difficulty,
        "department": question.department,
        "version": question.version,
    }
    return "sha256:" + sha256(
        dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
