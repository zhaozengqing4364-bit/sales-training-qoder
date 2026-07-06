from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Any

from curriculum_practice.models import QuestionItem
from curriculum_practice.schemas import GateResult, PublishGateDecision
from curriculum_practice.services.orm_payload_typing import (
    orm_dict,
    orm_int,
    orm_list,
    orm_optional_str,
    orm_str,
)


def publish_decision(question: QuestionItem) -> PublishGateDecision:
    results: list[GateResult] = []
    reference_answer = orm_optional_str(question.reference_answer) or ""
    if not reference_answer.strip():
        results.append(
            _gate(
                "reference_answer",
                "missing_reference_answer",
                "QuestionItem requires a reference answer before publish.",
            )
        )
    criteria_dimensions = orm_dict(question.scoring_criteria).get("dimensions")
    if not isinstance(criteria_dimensions, list) or not criteria_dimensions:
        results.append(
            _gate(
                "scoring_criteria",
                "invalid_scoring_criteria",
                "QuestionItem scoring_criteria.dimensions must be non-empty.",
            )
        )
    if not orm_list(question.scoring_dimensions):
        results.append(
            _gate(
                "scoring_dimensions",
                "invalid_scoring_dimensions",
                "QuestionItem scoring_dimensions must be non-empty.",
            )
        )
    if bool(question.safety_flagged):
        results.append(
            _gate(
                "question_safety",
                "security_flagged_question",
                "Security flagged questions cannot be published.",
            )
        )
    return PublishGateDecision(can_publish=not results, results=results)


def criteria_with_dimensions(
    scoring_criteria: object,
    scoring_dimensions: object,
) -> dict[str, Any]:
    criteria = dict(scoring_criteria) if isinstance(scoring_criteria, dict) else {}
    if not isinstance(scoring_dimensions, list) or not scoring_dimensions:
        return criteria
    criteria_dimensions = criteria.get("dimensions")
    if not isinstance(criteria_dimensions, list) or not criteria_dimensions:
        criteria["dimensions"] = list(scoring_dimensions)
    return criteria


def question_hash(question: QuestionItem) -> str:
    payload: dict[str, Any] = {
        "category_id": orm_str(question.category_id),
        "title": orm_str(question.title),
        "stem": orm_str(question.stem),
        "reference_answer": orm_optional_str(question.reference_answer),
        "scoring_criteria": orm_dict(question.scoring_criteria),
        "scoring_dimensions": orm_list(question.scoring_dimensions),
        "tags": orm_list(question.tags),
        "difficulty": orm_str(question.difficulty),
        "department": orm_optional_str(question.department),
        "version": orm_int(question.version),
    }
    return "sha256:" + sha256(
        dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )
