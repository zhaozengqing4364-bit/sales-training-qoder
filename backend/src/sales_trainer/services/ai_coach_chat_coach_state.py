from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sales_trainer.schemas import (
    AiCoachNextActionV1,
    AiCoachScoreResultV1,
    BusinessEtiquetteAiCoachProgressResponse,
)

AiCoachDifficultyV1 = Literal["warmup", "normal", "challenge"]


class AiCoachCoachStateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_step_count: int = Field(0, ge=0)
    answered_card_count: int = Field(0, ge=0)
    correct_streak: int = Field(0, ge=0)
    incorrect_streak: int = Field(0, ge=0)
    current_focus: str | None = Field(None, max_length=120)
    difficulty: AiCoachDifficultyV1 = "warmup"
    last_action: AiCoachNextActionV1 | None = None
    can_auto_advance: bool = False
    stopped_reason: str | None = Field(None, max_length=200)
    score_total: float = Field(0, ge=0)
    score_count: int = Field(0, ge=0)
    business_etiquette_progress: BusinessEtiquetteAiCoachProgressResponse | None = None

    @property
    def average_score(self) -> float:
        if self.score_count <= 0:
            return 0.0
        return self.score_total / self.score_count


def coach_state_from_snapshot(snapshot: object) -> AiCoachCoachStateV1:
    if snapshot is None:
        return AiCoachCoachStateV1()
    try:
        return AiCoachCoachStateV1.model_validate(snapshot)
    except ValidationError:
        return AiCoachCoachStateV1()


def update_state_after_score(
    state: AiCoachCoachStateV1,
    *,
    score_result: AiCoachScoreResultV1,
    mastery_threshold: float,
) -> AiCoachCoachStateV1:
    mastered = score_result.score >= mastery_threshold
    correct_streak = state.correct_streak + 1 if mastered else 0
    incorrect_streak = 0 if mastered else state.incorrect_streak + 1
    return state.model_copy(
        update={
            "answered_card_count": state.answered_card_count + 1,
            "correct_streak": correct_streak,
            "incorrect_streak": incorrect_streak,
            "score_total": state.score_total + score_result.score,
            "score_count": state.score_count + 1,
        }
    )


def update_state_after_action(
    state: AiCoachCoachStateV1,
    *,
    action: AiCoachNextActionV1,
    can_auto_advance: bool,
    stopped_reason: str | None = None,
) -> AiCoachCoachStateV1:
    next_count = state.auto_step_count
    if action not in {"ask_user_choice", "end_session"}:
        next_count += 1
    next_can_auto_advance = can_auto_advance and action not in {
        "ask_user_choice",
        "summarize",
        "end_session",
    }
    return state.model_copy(
        update={
            "auto_step_count": next_count,
            "last_action": action,
            "can_auto_advance": next_can_auto_advance,
            "stopped_reason": stopped_reason,
            "difficulty": _difficulty_after_action(state.difficulty, action),
        }
    )


def _difficulty_after_action(
    current: AiCoachDifficultyV1,
    action: AiCoachNextActionV1,
) -> AiCoachDifficultyV1:
    match action:
        case "increase_difficulty":
            return "challenge"
        case "remediate":
            return "warmup"
        case "continue_drill" | "switch_scenario":
            return "normal" if current == "warmup" else current
        case "summarize" | "ask_user_choice" | "end_session":
            return current
