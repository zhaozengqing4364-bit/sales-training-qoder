from __future__ import annotations

from typing import Any

from sales_trainer.models import SalesTrainerUnit, SalesTrainerUnitQuestion
from sales_trainer.schemas import SalesTrainerUnitUpdate, UnitQuestionBinding
from sales_trainer.services.asset_revision_service import AssetChangeClass
from sales_trainer.services.audit_metadata import unit_lifecycle_snapshot

UNIT_RESOURCE_TYPE = "sales_trainer_unit"


def unit_revision_payload_from_update(
    current: SalesTrainerUnit,
    current_questions: list[SalesTrainerUnitQuestion],
    payload: SalesTrainerUnitUpdate,
) -> dict[str, Any]:
    base = unit_lifecycle_snapshot(current, current_questions)
    data = payload.model_dump(exclude_unset=True, exclude={"questions"})
    next_questions = (
        _question_payloads(payload.questions)
        if "questions" in payload.model_fields_set and payload.questions is not None
        else list(base.get("questions") or [])
    )
    next_payload = {
        **base,
        **data,
        "status": "published",
        "questions": next_questions,
        "question_ids": [str(item["question_id"]) for item in next_questions],
    }
    return next_payload


def unit_question_bindings_from_payload(
    payload: dict[str, Any],
) -> list[UnitQuestionBinding]:
    questions = payload.get("questions")
    if not isinstance(questions, list):
        return []
    return [
        UnitQuestionBinding(
            question_id=str(item["question_id"]),
            order_index=int(item.get("order_index") or 1),
            points=int(float(item.get("points") or 10)),
        )
        for item in questions
        if isinstance(item, dict) and item.get("question_id")
    ]


def unit_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if _scoring_or_completion_changed(previous, next_snapshot):
        return "scoring_high_risk"
    if _binding_changed(previous, next_snapshot):
        return "binding"
    if previous.get("description") != next_snapshot.get("description"):
        return "semantic"
    if previous.get("name") != next_snapshot.get("name"):
        return "semantic"
    return "non_semantic"


def payload_dict(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _question_payloads(
    questions: list[UnitQuestionBinding],
) -> list[dict[str, Any]]:
    return [
        {
            "question_id": item.question_id,
            "order_index": item.order_index,
            "points": item.points,
        }
        for item in questions
    ]


def _scoring_or_completion_changed(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> bool:
    if previous.get("questions") != next_snapshot.get("questions"):
        return True
    previous_config = previous.get("config")
    next_config = next_snapshot.get("config")
    if not isinstance(previous_config, dict) or not isinstance(next_config, dict):
        return previous_config != next_config
    previous_quiz = previous_config.get("quiz")
    next_quiz = next_config.get("quiz")
    if isinstance(previous_quiz, dict) and isinstance(next_quiz, dict):
        if previous_quiz.get("pass_threshold") != next_quiz.get("pass_threshold"):
            return True
    previous_audio = previous_config.get("audio")
    next_audio = next_config.get("audio")
    if isinstance(previous_audio, dict) and isinstance(next_audio, dict):
        high_risk_keys = ("pass_threshold", "scoring_prompt_id")
        return any(previous_audio.get(key) != next_audio.get(key) for key in high_risk_keys)
    return False


def _binding_changed(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> bool:
    previous_config = previous.get("config")
    next_config = next_snapshot.get("config")
    if not isinstance(previous_config, dict) or not isinstance(next_config, dict):
        return False
    return previous_config.get("path") != next_config.get("path")
