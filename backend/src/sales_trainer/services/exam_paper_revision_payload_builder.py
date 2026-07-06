from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import orm_scalar
from sales_trainer.models import SalesTrainerExamPaper, SalesTrainerUnit
from sales_trainer.schemas import ExamPaperUpdate, UnitQuestionBinding
from sales_trainer.services.asset_revision_service import AssetChangeClass
from sales_trainer.services.exam_paper_config import decimal_or_none, quiz_config
from sales_trainer.services.exam_paper_revision_payloads import (
    freeze_paper_question_revisions,
    paper_revision_unit_bindings,
)
from sales_trainer.services.exam_paper_store import ensure_unique_paper_key
from sales_trainer.services.unit_service import UnitService


class ExamPaperRevisionPayloadBuilder:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build(
        self,
        paper: SalesTrainerExamPaper,
        unit: SalesTrainerUnit,
        previous_snapshot: dict[str, Any],
        payload: ExamPaperUpdate,
        *,
        actor: User,
        unit_service: UnitService,
    ) -> dict[str, Any]:
        data = payload.model_dump(exclude_unset=True)
        paper_key = str(data.get("paper_key") or previous_snapshot["paper_key"])
        if paper_key != paper.paper_key:
            await ensure_unique_paper_key(self._db, paper_key)
        pass_threshold = data.get(
            "pass_threshold",
            previous_snapshot.get("pass_threshold"),
        )
        next_questions = _next_revision_questions(payload, data, previous_snapshot)
        await unit_service._validate_payload(
            "quiz",
            quiz_config(decimal_or_none(pass_threshold)),
            [_unit_question_binding(item) for item in next_questions],
            actor=actor,
            target_unit_id=str(unit.unit_id),
        )
        return await freeze_paper_question_revisions(
            self._db,
            {
                **previous_snapshot,
                "paper_id": orm_scalar(paper.paper_id, str),
                "paper_key": paper_key,
                "title": data.get("title", previous_snapshot.get("title")),
                "description": data.get(
                    "description",
                    previous_snapshot.get("description"),
                ),
                "module_key": data.get(
                    "module_key",
                    previous_snapshot.get("module_key"),
                ),
                "unit_id": orm_scalar(unit.unit_id, str),
                "unit_status": "published",
                "status": "published",
                "pass_threshold": (
                    float(pass_threshold) if pass_threshold is not None else None
                ),
                "question_ids": [str(item["question_id"]) for item in next_questions],
                "questions": next_questions,
            },
        )

    async def apply(
        self,
        paper: SalesTrainerExamPaper,
        unit: SalesTrainerUnit,
        payload: dict[str, Any],
        *,
        actor: User,
        unit_service: UnitService,
    ) -> None:
        pass_threshold = decimal_or_none(payload.get("pass_threshold"))
        setattr(paper, "paper_key", str(payload["paper_key"]))
        setattr(paper, "title", str(payload["title"]))
        setattr(paper, "description", payload.get("description"))
        setattr(paper, "module_key", str(payload["module_key"]))
        setattr(paper, "pass_threshold", pass_threshold)
        setattr(paper, "status", "published")
        setattr(paper, "updated_by", str(actor.user_id))
        setattr(unit, "name", str(payload["title"]))
        setattr(unit, "description", payload.get("description"))
        setattr(unit, "config", quiz_config(pass_threshold))
        setattr(unit, "status", "published")
        setattr(unit, "updated_by", str(actor.user_id))
        await unit_service._replace_questions(
            orm_scalar(unit.unit_id, str),
            paper_revision_unit_bindings(payload),
        )


def paper_change_class(
    previous_snapshot: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if previous_snapshot.get("pass_threshold") != next_snapshot.get("pass_threshold"):
        return "scoring_high_risk"
    if previous_snapshot.get("questions") != next_snapshot.get("questions"):
        return "scoring_high_risk"
    if previous_snapshot.get("module_key") != next_snapshot.get("module_key"):
        return "binding"
    return "semantic"


def _next_revision_questions(
    payload: ExamPaperUpdate,
    data: dict[str, Any],
    previous_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    if "questions" not in data:
        return [
            dict(item)
            for item in previous_snapshot.get("questions") or []
            if isinstance(item, dict)
        ]
    return [
        {
            "question_id": item.question_id,
            "order_index": item.order_index,
            "points": item.points,
        }
        for item in payload.questions or []
    ]


def _unit_question_binding(item: dict[str, Any]) -> UnitQuestionBinding:
    return UnitQuestionBinding(
        question_id=str(item["question_id"]),
        order_index=int(item["order_index"]),
        points=int(item["points"]),
    )
