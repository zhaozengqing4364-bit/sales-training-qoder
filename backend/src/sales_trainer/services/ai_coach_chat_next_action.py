from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from sales_trainer.schemas import (
    AiCoachConfig,
    AiCoachNextActionV1,
    AiCoachScoreResultV1,
)
from sales_trainer.services.ai_coach_chat_coach_state import AiCoachCoachStateV1


class AiCoachNextActionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AiCoachNextActionV1
    reason: str = Field(..., min_length=1, max_length=1000)
    should_generate: bool = True
    stopped_reason: str | None = Field(None, max_length=200)


class AiCoachNextActionDecider:
    def decide_after_score(
        self,
        *,
        config: AiCoachConfig,
        state: AiCoachCoachStateV1,
        score_result: AiCoachScoreResultV1 | dict[str, object],
    ) -> AiCoachNextActionDecision:
        parsed_score = (
            score_result
            if isinstance(score_result, AiCoachScoreResultV1)
            else AiCoachScoreResultV1.model_validate(score_result)
        )
        if not config.proactive_coaching_enabled or not config.auto_advance_enabled:
            return self._decision(
                config,
                action="end_session",
                reason="主动教练未启用，仅保存当前评分。",
                should_generate=False,
                stopped_reason="auto_advance_disabled",
            )
        if state.auto_step_count >= config.max_auto_steps_per_session:
            return self._decision(
                config,
                action="summarize",
                reason="已达到本轮自动推进步数上限，需要阶段复盘。",
            )
        if state.answered_card_count >= config.max_turns:
            return self._decision(
                config,
                action="summarize",
                reason="已达到本轮最大训练轮数，需要结束并复盘。",
            )
        if (
            config.summary_when_mastery_reached
            and state.answered_card_count >= config.min_turns
            and state.average_score >= config.mastery_threshold
        ):
            return self._decision(
                config,
                action="summarize",
                reason="已达到最低训练轮数且平均分达到掌握阈值。",
            )
        if state.incorrect_streak >= config.incorrect_streak_to_pause:
            return self._decision(
                config,
                action="ask_user_choice",
                reason="连续答错达到暂停阈值，需要让学员选择下一步。",
            )
        if state.incorrect_streak >= config.incorrect_streak_to_remediate:
            if config.remediation_strategy == "ask_user_choice":
                return self._decision(
                    config,
                    action="ask_user_choice",
                    reason="本题未达到掌握阈值，补救策略要求先让学员选择下一步。",
                )
            return self._decision(
                config,
                action="remediate",
                reason="本题未达到掌握阈值，需要先补救讲解再相似重练。",
            )
        if state.correct_streak >= config.correct_streak_to_increase_difficulty:
            return self._decision(
                config,
                action="increase_difficulty",
                reason="连续答对达到加难阈值，下一题提高情境复杂度。",
            )
        if parsed_score.score >= config.mastery_threshold:
            return self._decision(
                config,
                action="continue_drill",
                reason="本题已达到掌握阈值，继续同主题训练。",
            )
        return self._decision(
            config,
            action="remediate",
            reason="本题低于掌握阈值，需要补救讲解。",
        )

    def _decision(
        self,
        config: AiCoachConfig,
        *,
        action: AiCoachNextActionV1,
        reason: str,
        should_generate: bool = True,
        stopped_reason: str | None = None,
    ) -> AiCoachNextActionDecision:
        allowed_action = self._allowed_action(config, action)
        return AiCoachNextActionDecision(
            action=allowed_action,
            reason=reason,
            should_generate=should_generate,
            stopped_reason=stopped_reason,
        )

    @staticmethod
    def _allowed_action(
        config: AiCoachConfig,
        action: AiCoachNextActionV1,
    ) -> AiCoachNextActionV1:
        if action in config.allowed_next_actions:
            return action
        for fallback in ("ask_user_choice", "summarize", "end_session"):
            if fallback in config.allowed_next_actions:
                return fallback
        return config.allowed_next_actions[0]
