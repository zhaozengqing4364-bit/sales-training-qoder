from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAssetRevision,
    SalesTrainerExamPaper,
    SalesTrainerQuizAnswer,
    SalesTrainerQuizAttempt,
)
from sales_trainer.schemas import QuizAnswerSubmit
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.paper_snapshot_scoring import (
    RevisionQuestion,
    answer_payload_snapshot,
    float_or_none,
    grade_snapshot_question,
    optional_str,
    question_type,
)
from sales_trainer.services.path_attempt_context_service import (
    PathAttemptContextPayload,
)
from sales_trainer.services.short_answer_scoring_service import (
    ShortAnswerScoringService,
)


class PaperSnapshotAttemptService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        short_answer_scoring_service: ShortAnswerScoringService | None = None,
    ) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._short_answer_scoring = (
            short_answer_scoring_service or ShortAnswerScoringService()
        )

    async def submit_attempt(
        self,
        paper: SalesTrainerExamPaper,
        revision: SalesTrainerAssetRevision,
        *,
        answers: list[QuizAnswerSubmit],
        actor: User,
        attempt_context: PathAttemptContextPayload | None = None,
    ) -> SalesTrainerQuizAttempt:
        revision_payload = _revision_payload(revision)
        questions = _revision_questions(revision_payload)
        answer_map = {answer.question_id: answer.answer_payload for answer in answers}
        unknown_answer_ids = sorted(set(answer_map) - {item.question_id for item in questions})
        if unknown_answer_ids:
            raise PaperSnapshotAttemptError(
                "[QUIZ_ANSWER_QUESTION_NOT_IN_UNIT]",
                "提交答案包含未绑定到当前考卷修订的题目。",
                422,
            )
        if _has_incomplete_answers(questions, answer_map):
            raise PaperSnapshotAttemptError(
                "[QUIZ_ANSWER_INCOMPLETE]",
                "请完成全部题目后再提交。",
                422,
            )
        attempt = SalesTrainerQuizAttempt(
            unit_id=paper.unit_id,
            user_id=str(actor.user_id),
            paper_revision_id=revision.revision_id,
            status="submitted",
        )
        self._db.add(attempt)
        await self._db.flush()
        await self._score_answers(
            attempt,
            questions,
            answer_map,
            revision_payload,
            attempt_context,
        )
        await self._logs.record(
            actor=actor,
            action="quiz_submitted",
            target_type="sales_trainer_quiz_attempt",
            target_id=attempt.attempt_id,
            metadata={
                "unit_id": paper.unit_id,
                "paper_id": paper.paper_id,
                "paper_revision_id": revision.revision_id,
                "path_revision_id": _context_value(attempt_context, "path_revision_id"),
                "path_revision_no": _context_value(attempt_context, "path_revision_no"),
                "path_key": _context_value(attempt_context, "path_key"),
                "module_key": _context_value(attempt_context, "module_key"),
                "legacy_snapshot_only": _context_value(
                    attempt_context,
                    "legacy_snapshot_only",
                ),
                "question_count": len(questions),
            },
        )
        await self._db.commit()
        await self._db.refresh(attempt)
        return attempt

    async def _score_answers(
        self,
        attempt: SalesTrainerQuizAttempt,
        questions: list[RevisionQuestion],
        answer_map: dict[str, Any],
        revision_payload: dict[str, Any],
        attempt_context: PathAttemptContextPayload | None,
    ) -> None:
        scored_values: list[float] = []
        max_score = 0.0
        has_unscored = False
        for question in questions:
            answer_payload = answer_map.get(question.question_id)
            is_correct, score = grade_snapshot_question(
                question,
                answer_payload=answer_payload,
            )
            feedback: str | None = None
            reason: str | None = None
            normalized_score: float | None = None
            if score is None and question_type(question) == "short_answer":
                result = await self._short_answer_scoring.score(
                    question,
                    answer_text=str(answer_payload or ""),
                )
                if result.is_success and result.value is not None:
                    outcome = result.value
                    normalized_score = float(outcome.score)
                    score = float(question.points) * normalized_score / 100
                    is_correct = outcome.passed
                    feedback = outcome.feedback
                    reason = outcome.reason
            if score is None:
                has_unscored = True
            else:
                scored_values.append(float(score))
                max_score += float(question.points)
            self._db.add(
                SalesTrainerQuizAnswer(
                    attempt_id=attempt.attempt_id,
                    question_id=question.question_id,
                    question_type=question_type(question),
                    answer_payload=answer_payload_snapshot(
                        question,
                        answer_payload=answer_payload,
                        attempt_context=attempt_context,
                        is_correct=is_correct,
                        score=float(score) if score is not None else None,
                        scoring_feedback=feedback,
                        scoring_reason=reason,
                        normalized_score=normalized_score,
                    ),
                    is_correct=is_correct,
                    score=Decimal(str(score)) if score is not None else None,
                )
            )
        if scored_values and not has_unscored:
            attempt.total_score = Decimal(str(sum(scored_values)))
            attempt.max_score = Decimal(str(max_score))
            threshold = float_or_none(revision_payload.get("pass_threshold"))
            attempt.passed = (
                sum(scored_values) >= threshold if threshold is not None else None
            )
            attempt.status = "scored"


class PaperSnapshotAttemptError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _revision_payload(revision: SalesTrainerAssetRevision) -> dict[str, Any]:
    return revision.payload_json if isinstance(revision.payload_json, dict) else {}


def _revision_questions(payload: dict[str, Any]) -> list[RevisionQuestion]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return []
    return [
        _revision_question(item)
        for item in questions
        if isinstance(item, dict) and isinstance(item.get("question_snapshot"), dict)
    ]


def _revision_question(item: dict[str, Any]) -> RevisionQuestion:
    snapshot = dict(item.get("question_snapshot") or {})
    return RevisionQuestion(
        question_id=str(item["question_id"]),
        title=str(snapshot.get("title") or ""),
        stem=str(snapshot.get("stem") or ""),
        reference_answer=optional_str(snapshot.get("reference_answer")),
        scoring_criteria=dict(snapshot.get("scoring_criteria") or {}),
        scoring_dimensions=[
            str(value) for value in snapshot.get("scoring_dimensions") or []
        ],
        points=int(item["points"]),
        order_index=int(item["order_index"]),
        question_revision_id=optional_str(item.get("question_revision_id")),
        question_payload_hash=optional_str(item.get("question_payload_hash")),
    )


def _has_incomplete_answers(
    questions: list[RevisionQuestion],
    answer_map: dict[str, Any],
) -> bool:
    return any(
        _is_incomplete_answer(question, answer_map.get(question.question_id))
        for question in questions
    )


def _is_incomplete_answer(question: RevisionQuestion, answer_payload: Any) -> bool:
    if answer_payload is None:
        return True
    if question_type(question) == "multiple_choice":
        return not isinstance(answer_payload, list) or len(answer_payload) == 0
    return not str(answer_payload).strip()


def _context_value(
    attempt_context: PathAttemptContextPayload | None,
    key: str,
) -> str | int | bool | None:
    if attempt_context is None:
        return None
    value = attempt_context.get(key)
    return value if isinstance(value, str | int | bool) or value is None else None
