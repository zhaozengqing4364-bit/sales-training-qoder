"""Stable durable-task type identifiers for structured Coach workloads."""

COACH_CARD_GENERATION_TASK_TYPE = "ai_coach.cards.generate"
COACH_ANSWER_EVALUATION_TASK_TYPE = "ai_coach.answer.evaluate"
COACH_ASSISTANCE_TASK_TYPE = "ai_coach.assistance.generate"

__all__ = [
    "COACH_ANSWER_EVALUATION_TASK_TYPE",
    "COACH_ASSISTANCE_TASK_TYPE",
    "COACH_CARD_GENERATION_TASK_TYPE",
]
