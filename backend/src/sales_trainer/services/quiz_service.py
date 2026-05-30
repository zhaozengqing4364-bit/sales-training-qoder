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
                    answer_payload=_answer_payload_snapshot(
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
        result = await self._db.execute(
            select(SalesTrainerQuizAnswer)
            .where(SalesTrainerQuizAnswer.attempt_id == attempt.attempt_id)
            .order_by(SalesTrainerQuizAnswer.created_at.asc())
        )
        answers = list(result.scalars().all())
        user = await self._db.get(User, attempt.user_id)
        return {
            "attempt_id": attempt.attempt_id,
            "unit_id": attempt.unit_id,
            "user_id": attempt.user_id,
            "user_name": user.name if user else None,
            "user_email": user.email if user else None,
            "user_department": user.department if user else None,
            "total_score": float(attempt.total_score)
            if attempt.total_score is not None
            else None,
            "max_score": float(attempt.max_score)
            if attempt.max_score is not None
            else None,
            "passed": attempt.passed,
            "status": attempt.status,
            "submitted_at": attempt.submitted_at,
            "answers": [
                {
                    "answer_id": answer.answer_id,
                    "question_id": answer.question_id,
                    "question_type": answer.question_type,
                    "answer_payload": _answer_value(answer.answer_payload),
                    "question_title": _answer_snapshot_value(
                        answer.answer_payload, "title"
                    ),
                    "question_stem": _answer_snapshot_value(
                        answer.answer_payload, "stem"
                    ),
                    "options": _answer_snapshot_list(answer.answer_payload, "options"),
                    "correct_answer": _answer_snapshot_value(
                        answer.answer_payload, "correct_answer"
                    ),
                    "reference_answer": _answer_snapshot_value(
                        answer.answer_payload, "reference_answer"
                    ),
                    "explanation": _answer_snapshot_value(
                        answer.answer_payload, "explanation"
                    ),
                    "scoring_feedback": _answer_scoring_value(
                        answer.answer_payload, "feedback"
                    ),
                    "scoring_reason": _answer_scoring_value(
                        answer.answer_payload, "reason"
                    ),
                    "normalized_score": _answer_scoring_number(
                        answer.answer_payload, "normalized_score"
                    ),
                    "is_correct": answer.is_correct,
                    "score": float(answer.score) if answer.score is not None else None,
                    "created_at": answer.created_at,
                }
                for answer in answers
            ],
        }

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


def _answer_payload_snapshot(
    question: Any,
    *,
    answer_payload: Any,
    points: int,
    is_correct: bool | None,
    score: float | None,
    scoring_feedback: str | None,
    scoring_reason: str | None,
    normalized_score: float | None,
) -> dict[str, Any]:
    criteria = question.scoring_criteria or {}
    question_type = str(criteria.get("question_type") or "short_answer")
    return {
        "value": answer_payload,
        "question_snapshot": {
            "question_id": str(question.question_id),
            "title": question.title,
            "stem": question.stem,
            "question_type": question_type,
            "options": criteria.get("options") or [],
            "correct_answer": _correct_answer_snapshot(criteria, question_type),
            "reference_answer": question.reference_answer,
            "explanation": criteria.get("explanation"),
            "scoring_dimensions": question.scoring_dimensions or [],
            "points": points,
        },
        "scoring": {
            "is_correct": is_correct,
            "score": score,
            "normalized_score": normalized_score,
            "feedback": scoring_feedback,
            "reason": scoring_reason,
        },
    }


def _correct_answer_snapshot(criteria: dict[str, Any], question_type: str) -> Any:
    if question_type == "multiple_choice":
        return criteria.get("correct_answers") or []
    if question_type == "true_false":
        return criteria.get("correct_bool")
    return criteria.get("correct_answer")


def _answer_value(payload: Any) -> Any:
    if isinstance(payload, dict) and "value" in payload:
        return payload.get("value")
    return payload


def _answer_snapshot(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    snapshot = payload.get("question_snapshot")
    return snapshot if isinstance(snapshot, dict) else {}


def _answer_snapshot_value(payload: Any, key: str) -> Any:
    return _answer_snapshot(payload).get(key)


def _answer_snapshot_list(payload: Any, key: str) -> list[dict[str, Any]]:
    value = _answer_snapshot(payload).get(key)
    return value if isinstance(value, list) else []


def _answer_scoring(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    scoring = payload.get("scoring")
    return scoring if isinstance(scoring, dict) else {}


def _answer_scoring_value(payload: Any, key: str) -> str | None:
    value = _answer_scoring(payload).get(key)
    return value if isinstance(value, str) else None


def _answer_scoring_number(payload: Any, key: str) -> float | None:
    value = _answer_scoring(payload).get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
