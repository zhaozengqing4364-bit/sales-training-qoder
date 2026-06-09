from __future__ import annotations

from sales_trainer.schemas import (
    ExamPaperCreate,
    ExamPaperQuestionBinding,
    ExamPaperUpdate,
    SalesTrainerUnitCreate,
    SalesTrainerUnitUpdate,
    UnitQuestionBinding,
)
from sales_trainer.services.exam_paper_config import quiz_config


def paper_unit_create(payload: ExamPaperCreate) -> SalesTrainerUnitCreate:
    return SalesTrainerUnitCreate(
        name=payload.title,
        description=payload.description,
        unit_type="quiz",
        config=quiz_config(payload.pass_threshold),
        questions=_question_bindings(payload.questions),
    )


def paper_unit_update(payload: ExamPaperUpdate) -> SalesTrainerUnitUpdate:
    return SalesTrainerUnitUpdate(
        name=payload.title,
        description=payload.description,
        config=quiz_config(payload.pass_threshold),
        questions=(
            _question_bindings(payload.questions)
            if payload.questions is not None
            else None
        ),
    )


def _question_bindings(
    items: list[ExamPaperQuestionBinding],
) -> list[UnitQuestionBinding]:
    return [
        UnitQuestionBinding(
            question_id=item.question_id,
            order_index=item.order_index,
            points=item.points,
        )
        for item in items
    ]
