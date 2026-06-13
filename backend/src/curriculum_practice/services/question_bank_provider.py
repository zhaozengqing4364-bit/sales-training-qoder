from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.question_bank.ports import (
    ResolvedQuestion,
    register_question_bank_provider,
)
from curriculum_practice.models import QuestionItem

SALES_TRAINER_QUESTION_SCOPE = "sales_trainer"


class CurriculumQuestionBankProvider:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_published_questions(
        self,
        question_ids: list[str],
    ) -> dict[str, ResolvedQuestion]:
        if not question_ids:
            return {}
        result = await self._db.execute(
            select(QuestionItem).where(
                QuestionItem.question_id.in_(question_ids),
                QuestionItem.status == "published",
                QuestionItem.usage_scope == SALES_TRAINER_QUESTION_SCOPE,
            )
        )
        return {
            str(question.question_id): _to_resolved_question(question)
            for question in result.scalars().all()
        }

    async def get_questions(
        self,
        question_ids: list[str],
    ) -> dict[str, ResolvedQuestion]:
        if not question_ids:
            return {}
        result = await self._db.execute(
            select(QuestionItem).where(QuestionItem.question_id.in_(question_ids))
        )
        return {
            str(question.question_id): _to_resolved_question(question)
            for question in result.scalars().all()
        }


def register_curriculum_question_bank_provider() -> None:
    register_question_bank_provider(
        SALES_TRAINER_QUESTION_SCOPE,
        CurriculumQuestionBankProvider,
    )


def _to_resolved_question(question: QuestionItem) -> ResolvedQuestion:
    return ResolvedQuestion(
        question_id=str(question.question_id),
        title=str(question.title),
        stem=str(question.stem),
        reference_answer=question.reference_answer,
        scoring_criteria=dict(question.scoring_criteria or {}),
        scoring_dimensions=list(question.scoring_dimensions or []),
    )
