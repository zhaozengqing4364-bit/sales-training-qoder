from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)
from sales_trainer.rules import resolve_quiz_pass_threshold
from sales_trainer.schemas import QuizAttemptCreate
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.question_bank_adapter import QuestionBankAdapter
from sales_trainer.services.quiz_attempt_payloads import (
    answer_payload_snapshot,
    serialize_quiz_attempt,
)
from sales_trainer.services.short_answer_scoring_service import (
    ShortAnswerScoringService,
)


class QuizServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class QuizService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        short_answer_scoring_service: ShortAnswerScoringService | None = None,
    ) -> None:
        self._db = db
        self._question_adapter = QuestionBankAdapter(db)
        self._logs = OperationLogService(db)
        self._short_answer_scoring = (
            short_answer_scoring_service or ShortAnswerScoringService()
        )

    async def submit_attempt(
        self,
        payload: QuizAttemptCreate,
        *,
        actor: User,
    ) -> SalesTrainerQuizAttempt:
        unit = await self._db.get(SalesTrainerUnit, payload.unit_id)
        if unit is None or unit.status != "published":
            raise QuizServiceError(
                "[SALES_TRAINER_UNIT_NOT_FOUND]",
                "训练单元不存在或未发布。",
                status_code=404,
            )
        if unit.unit_type != "quiz":
            raise QuizServiceError(
                "[SALES_TRAINER_UNIT_TYPE_MISMATCH]",
                "该训练单元不是做题模块。",
            )
        bindings = await self._load_bindings(unit.unit_id)
        if not bindings:
            raise QuizServiceError(
                "[SALES_TRAINER_QUIZ_HAS_NO_QUESTIONS]",
                "训练单元没有可作答题目。",
                status_code=409,
            )

        question_ids = [str(binding.question_id) for binding in bindings]
        question_map = await self._question_adapter.get_questions(question_ids)
        answer_map = {answer.question_id: answer.answer_payload for answer in payload.answers}
        unknown_answer_ids = sorted(set(answer_map) - set(question_ids))
        if unknown_answer_ids:
            raise QuizServiceError(
                "[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]",
                "提交答案包含未绑定到当前训练单元的题目。",
                status_code=422,
            )

        attempt = SalesTrainerQuizAttempt(
            unit_id=unit.unit_id,
            user_id=str(actor.user_id),
            status="submitted",
        )
        self._db.add(attempt)
        await self._db.flush()

        scored_values: list[float] = []
        max_score = 0.0
        has_unscored = False
        for binding in bindings:
            question = question_map.get(str(binding.question_id))
            if question is None:
                continue
            answer_payload = answer_map.get(str(binding.question_id))
            is_correct, score = self._question_adapter.grade(
                question,
                answer_payload=answer_payload,
                points=int(binding.points),
            )
            scoring_feedback: str | None = None
            scoring_reason: str | None = None
            normalized_score: float | None = None
            question_type = self._question_adapter.resolve_type(question)
            if score is None and question_type == "short_answer":
                scoring_result = await self._short_answer_scoring.score(
                    question,
                    answer_text=str(answer_payload or ""),
                )
                if scoring_result.is_success and scoring_result.value is not None:
                    outcome = scoring_result.value
                    normalized_score = float(outcome.score)
                    score = float(binding.points) * normalized_score / 100
                    is_correct = outcome.passed
                    scoring_feedback = outcome.feedback
                    scoring_reason = outcome.reason
            if score is None:
                has_unscored = True
            else:
                scored_values.append(float(score))
                max_score += float(binding.points)
            self._db.add(
                SalesTrainerQuizAnswer(
                    attempt_id=attempt.attempt_id,
                    question_id=str(question.question_id),
                    question_type=question_type,
                    answer_payload=answer_payload_snapshot(
                        question,
                        answer_payload=answer_payload,
                        points=int(binding.points),
                        is_correct=is_correct,
                        score=float(score) if score is not None else None,
                        scoring_feedback=scoring_feedback,
                        scoring_reason=scoring_reason,
                        normalized_score=normalized_score,
                    ),
                    is_correct=is_correct,
                    score=Decimal(str(score)) if score is not None else None,
                )
            )

        if scored_values and not has_unscored:
            attempt.total_score = Decimal(str(sum(scored_values)))
            attempt.max_score = Decimal(str(max_score))
            threshold = resolve_quiz_pass_threshold(unit.config)
            attempt.passed = sum(scored_values) >= threshold if threshold is not None else None
            attempt.status = "scored"
        else:
            attempt.status = "submitted"

        await self._logs.record(
            actor=actor,
            action="quiz_submitted",
            target_type="sales_trainer_quiz_attempt",
            target_id=attempt.attempt_id,
            metadata={"unit_id": unit.unit_id, "question_count": len(bindings)},
        )
        await self._db.commit()
        await self._db.refresh(attempt)
        return attempt

    async def get_attempt(
        self,
        attempt_id: str,
        *,
        actor: User,
        allow_admin: bool = False,
    ) -> SalesTrainerQuizAttempt | None:
        attempt = await self._db.get(SalesTrainerQuizAttempt, attempt_id)
        if attempt is None:
            return None
        if not allow_admin and attempt.user_id != str(actor.user_id):
            raise QuizServiceError("[ACCESS_DENIED]", "无权查看该做题记录。", 403)
        return attempt

    async def get_admin_attempt(
        self,
        attempt_id: str,
        *,
        actor: User,
        allow_admin: bool = False,
        team_department: str | None = None,
    ) -> SalesTrainerQuizAttempt | None:
        attempt = await self._db.get(SalesTrainerQuizAttempt, attempt_id)
        if attempt is None:
            return None
        if allow_admin:
            return attempt
        if team_department is not None and await self._attempt_in_department(
            attempt,
            team_department,
        ):
            return attempt
        if attempt.user_id != str(actor.user_id):
            raise QuizServiceError("[ACCESS_DENIED]", "无权查看该做题记录。", 403)
        return attempt

    async def list_attempts(
        self,
        *,
        user_id: str | None = None,
        unit_id: str | None = None,
        team_department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesTrainerQuizAttempt], int]:
        stmt = select(SalesTrainerQuizAttempt)
        count_stmt = select(func.count()).select_from(SalesTrainerQuizAttempt)
        if user_id:
            stmt = stmt.where(SalesTrainerQuizAttempt.user_id == user_id)
            count_stmt = count_stmt.where(SalesTrainerQuizAttempt.user_id == user_id)
        if unit_id:
            stmt = stmt.where(SalesTrainerQuizAttempt.unit_id == unit_id)
            count_stmt = count_stmt.where(SalesTrainerQuizAttempt.unit_id == unit_id)
        if team_department is not None:
            stmt = stmt.join(User, SalesTrainerQuizAttempt.user_id == User.user_id)
            count_stmt = count_stmt.join(
                User,
                SalesTrainerQuizAttempt.user_id == User.user_id,
            )
            stmt = stmt.where(User.department == team_department)
            count_stmt = count_stmt.where(User.department == team_department)
        result = await self._db.execute(
            stmt.order_by(SalesTrainerQuizAttempt.submitted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = await self._db.scalar(count_stmt)
        return list(result.scalars().all()), int(total or 0)

    async def serialize_attempt(
        self, attempt: SalesTrainerQuizAttempt
    ) -> dict[str, Any]:
        return await serialize_quiz_attempt(self._db, attempt)

    async def _load_bindings(self, unit_id: str) -> list[SalesTrainerUnitQuestion]:
        result = await self._db.execute(
            select(SalesTrainerUnitQuestion)
            .where(SalesTrainerUnitQuestion.unit_id == unit_id)
            .order_by(SalesTrainerUnitQuestion.order_index.asc())
            )
        return list(result.scalars().all())

    async def _attempt_in_department(
        self,
        attempt: SalesTrainerQuizAttempt,
        department: str,
    ) -> bool:
        result = await self._db.execute(
            select(User.department).where(User.user_id == attempt.user_id)
        )
        return result.scalar_one_or_none() == department
