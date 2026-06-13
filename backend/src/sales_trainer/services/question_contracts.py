from __future__ import annotations

from typing import Any

from sales_trainer.rules import DEFAULT_QUESTION_DIMENSION
from sales_trainer.schemas import (
    SalesTrainerQuestionCreate,
    SalesTrainerQuestionUpdate,
)
from sales_trainer.services.curriculum_practice_adapter import (
    QuestionItem,
    QuestionItemCreate,
    QuestionItemUpdate,
)
from sales_trainer.services.question_errors import SalesTrainerQuestionServiceError

SALES_TRAINER_QUESTION_SCOPE = "sales_trainer"


def to_question_item_create(payload: SalesTrainerQuestionCreate) -> QuestionItemCreate:
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


def to_question_item_update(
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
        return _single_choice_contract(payload, dimensions, explanation)
    if payload.question_type == "multiple_choice":
        return _multiple_choice_contract(payload, dimensions, explanation)
    if payload.question_type == "true_false":
        return _true_false_contract(payload, dimensions, explanation)
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


def _single_choice_contract(
    payload: SalesTrainerQuestionCreate,
    dimensions: list[str],
    explanation: str,
) -> tuple[dict[str, Any], list[str], str]:
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


def _multiple_choice_contract(
    payload: SalesTrainerQuestionCreate,
    dimensions: list[str],
    explanation: str,
) -> tuple[dict[str, Any], list[str], str]:
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


def _true_false_contract(
    payload: SalesTrainerQuestionCreate,
    dimensions: list[str],
    explanation: str,
) -> tuple[dict[str, Any], list[str], str]:
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
