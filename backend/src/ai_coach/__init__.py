"""Structured AI Coach domain."""

from ai_coach.contracts import (
    CoachProfileSnapshot,
    RequestCoachAssistanceInput,
    SubmitCoachAnswerInput,
)
from ai_coach.errors import AICoachError

__all__ = [
    "AICoachError",
    "CoachProfileSnapshot",
    "RequestCoachAssistanceInput",
    "SubmitCoachAnswerInput",
]
