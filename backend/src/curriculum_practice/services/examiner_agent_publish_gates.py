from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ScoringRuleset
from curriculum_practice.models import QuestionItem
from curriculum_practice.schemas import (
    GateResult,
    LearnerLevel,
    PublishGateDecision,
)

LEARNER_LEVELS = {"conservative", "beginner", "intermediate", "advanced"}


async def validate_examiner_agent_publish(
    db: AsyncSession,
    payload: Mapping[str, object],
) -> PublishGateDecision:
    results: list[GateResult] = []
    question_ids = _question_ids(payload.get("question_source_ids"))
    if not question_ids:
        results.append(
            _gate(
                "examiner_question_source",
                "[EXAMINER_QUESTION_SOURCE_EMPTY]",
                "ExaminerAgent requires at least one question source.",
            )
        )
    for question_id in question_ids:
        question = await db.get(QuestionItem, question_id)
        if question is None or question.status != "published":
            results.append(
                _gate(
                    "examiner_question_source",
                    "[EXAMINER_QUESTION_UNPUBLISHED]",
                    f"Question source {question_id} is missing or unpublished.",
                )
            )
            continue
        if question.safety_flagged:
            results.append(
                _gate(
                    "examiner_question_safety",
                    "[EXAMINER_QUESTION_SAFETY_FLAGGED]",
                    f"Question source {question_id} is safety flagged.",
                )
            )
    scoring_policy_id = payload.get("scoring_policy_id")
    ruleset = (
        await db.get(ScoringRuleset, scoring_policy_id)
        if isinstance(scoring_policy_id, str)
        else None
    )
    if ruleset is None or ruleset.status != "published" or not bool(ruleset.is_active):
        results.append(
            _gate(
                "examiner_scoring_policy",
                "[EXAMINER_SCORING_POLICY_INVALID]",
                "ExaminerAgent scoring policy must be an active published ruleset.",
            )
        )
    if not valid_examiner_timeout(payload.get("timeout_config")):
        results.append(
            _gate(
                "examiner_timeout_policy",
                "[EXAMINER_TIMEOUT_POLICY_INVALID]",
                "ExaminerAgent timeout_config.max_seconds must be between 1 and 1500.",
            )
        )
    if not valid_examiner_learner_strategy(payload.get("learner_level_strategy")):
        results.append(
            _gate(
                "examiner_learner_level_strategy",
                "[EXAMINER_LEARNER_LEVEL_STRATEGY_INVALID]",
                "ExaminerAgent learner level strategy is invalid.",
            )
        )
    return PublishGateDecision(can_publish=not results, results=results)


def examiner_timeout_seconds(config: object) -> int:
    if not isinstance(config, dict):
        return 0
    raw_max_seconds = config.get("max_seconds")
    if raw_max_seconds is None:
        return 0
    try:
        return int(raw_max_seconds)
    except (TypeError, ValueError):
        return 0


def resolve_examiner_learner_level(
    requested_level: LearnerLevel | None,
    strategy: object,
) -> LearnerLevel | None:
    if not isinstance(strategy, dict):
        return requested_level or "conservative"
    allowed_levels = strategy.get("allowed_levels")
    if not isinstance(allowed_levels, list):
        allowed_levels = list(LEARNER_LEVELS)
    raw_level = requested_level or strategy.get("default_level") or "conservative"
    if not isinstance(raw_level, str):
        return None
    if raw_level not in allowed_levels:
        return None
    match raw_level:
        case "conservative":
            return "conservative"
        case "beginner":
            return "beginner"
        case "intermediate":
            return "intermediate"
        case "advanced":
            return "advanced"
        case _:
            return None


def valid_examiner_timeout(config: object) -> bool:
    if not isinstance(config, dict):
        return False
    raw_max_seconds = config.get("max_seconds")
    if raw_max_seconds is None:
        return False
    try:
        max_seconds = int(raw_max_seconds)
    except (TypeError, ValueError):
        return False
    return 1 <= max_seconds <= 1500


def valid_examiner_learner_strategy(strategy: object) -> bool:
    if not isinstance(strategy, dict):
        return False
    default_level = strategy.get("default_level")
    allowed_levels = strategy.get("allowed_levels")
    return (
        isinstance(default_level, str)
        and default_level in LEARNER_LEVELS
        and isinstance(allowed_levels, list)
        and bool(allowed_levels)
        and all(
            isinstance(level, str) and level in LEARNER_LEVELS
            for level in allowed_levels
        )
        and default_level in allowed_levels
    )


def _question_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _gate(gate_name: str, reason_code: str, message: str) -> GateResult:
    return GateResult(
        gate_name=gate_name,
        status="failed",
        reason_code=reason_code,
        message=message,
    )
