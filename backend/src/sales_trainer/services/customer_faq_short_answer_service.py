from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.rules import DEFAULT_SHORT_ANSWER_PASS_THRESHOLD
from sales_trainer.schemas import (
    BusinessEtiquetteTrainingUnitConfig,
    CustomerFaqCard,
    CustomerFaqShortAnswerAttemptResponse,
    CustomerFaqShortAnswerResult,
    CustomerFaqShortAnswerSubmitRequest,
)
from sales_trainer.services.learning_topic_config_service import (
    CUSTOMER_FAQ_TOPIC_KEY,
    LearningTopicConfigError,
    NewcomerLearningTopicConfigService,
)
from sales_trainer.services.short_answer_scoring_service import (
    ShortAnswerScoringService,
)


class CustomerFaqShortAnswerServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class _CustomerFaqShortAnswerQuestion:
    card: CustomerFaqCard
    pass_threshold: float

    @property
    def question_id(self) -> str:
        return self.card.card_key

    @property
    def title(self) -> str:
        return self.card.question

    @property
    def stem(self) -> str:
        return f"请用自己的话回答客户问题：{self.card.question}"

    @property
    def reference_answer(self) -> str | None:
        return self.card.detailed_answer or self.card.short_answer

    @property
    def scoring_criteria(self) -> dict[str, Any]:
        return {
            "topic_key": CUSTOMER_FAQ_TOPIC_KEY,
            "customer_intent": self.card.customer_intent,
            "short_answer": self.card.short_answer,
            "key_points": list(self.card.key_points),
            "forbidden_claims": list(self.card.forbidden_claims),
            "difficulty_level": self.card.difficulty_level,
            "escalation_required": self.card.escalation_required,
            "ai_scoring": {
                "enabled": True,
                "pass_threshold": self.pass_threshold,
            },
        }

    @property
    def scoring_dimensions(self) -> list[str] | None:
        dimensions = ["核心口径", "关键要点", "禁答边界", "表达清晰"]
        if self.card.evidence_cases:
            dimensions.append("案例表达")
        return dimensions


class CustomerFaqShortAnswerService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        short_answer_scoring_service: ShortAnswerScoringService | None = None,
    ) -> None:
        self._db = db
        self._short_answer_scoring = (
            short_answer_scoring_service or ShortAnswerScoringService()
        )

    async def submit_unit_short_answer_attempt(
        self,
        unit_key: str,
        payload: CustomerFaqShortAnswerSubmitRequest,
    ) -> CustomerFaqShortAnswerAttemptResponse:
        try:
            topic, _revision = await NewcomerLearningTopicConfigService(
                self._db
            ).active_customer_faq_topic()
        except LearningTopicConfigError as exc:
            raise CustomerFaqShortAnswerServiceError(
                exc.code,
                exc.message,
                exc.status_code,
            ) from exc

        unit = _find_unit(topic.learning_units, unit_key)
        if unit is None:
            raise CustomerFaqShortAnswerServiceError(
                "[CUSTOMER_FAQ_UNIT_CONFIG_MISSING]",
                "客户常见问答学习单元不存在或未启用。",
                404,
            )
        if not unit.require_quiz:
            raise CustomerFaqShortAnswerServiceError(
                "[CUSTOMER_FAQ_UNIT_QUIZ_DISABLED]",
                "该客户常见问答学习单元未启用小测。",
                409,
            )

        cards_by_key = {
            card.card_key: card for card in topic.faq_cards if card.status == "published"
        }
        allowed_card_keys = [
            card_key for card_key in unit.source_card_keys if card_key in cards_by_key
        ]
        if not allowed_card_keys:
            raise CustomerFaqShortAnswerServiceError(
                "[CUSTOMER_FAQ_UNIT_CARDS_MISSING]",
                "该客户常见问答学习单元尚未绑定可测问题。",
                409,
            )
        answer_card_keys = {answer.card_key for answer in payload.answers}
        unknown_card_keys = sorted(answer_card_keys - set(allowed_card_keys))
        if unknown_card_keys:
            raise CustomerFaqShortAnswerServiceError(
                "[CUSTOMER_FAQ_QUIZ_CARD_NOT_IN_UNIT]",
                "提交答案包含不属于当前学习单元的问题。",
                422,
            )

        pass_threshold = unit.quiz_pass_threshold
        results: list[CustomerFaqShortAnswerResult] = []
        for answer in payload.answers:
            card = cards_by_key[answer.card_key]
            scoring_result = await self._short_answer_scoring.score(
                _CustomerFaqShortAnswerQuestion(
                    card=card,
                    pass_threshold=pass_threshold
                    if pass_threshold is not None
                    else DEFAULT_SHORT_ANSWER_PASS_THRESHOLD,
                ),
                answer_text=answer.answer_text,
            )
            if not scoring_result.is_success or scoring_result.value is None:
                raise CustomerFaqShortAnswerServiceError(
                    "[CUSTOMER_FAQ_SHORT_ANSWER_SCORING_FAILED]",
                    "客户常见问答简答评分暂不可用，请稍后重试。",
                    503,
                )
            outcome = scoring_result.value
            results.append(
                CustomerFaqShortAnswerResult(
                    card_key=card.card_key,
                    question=card.question,
                    answer_text=answer.answer_text,
                    score=round(float(outcome.score), 1),
                    max_score=100.0,
                    passed=outcome.passed,
                    feedback=outcome.feedback,
                    reason=outcome.reason,
                    scoring_source=outcome.scoring_source,
                    scoring_provider=outcome.scoring_provider,
                    scoring_model=outcome.scoring_model,
                    scoring_latency_ms=outcome.scoring_latency_ms,
                )
            )

        total_score = round(
            sum(item.score for item in results) / max(len(results), 1),
            1,
        )
        passed = (
            total_score >= float(pass_threshold) if pass_threshold is not None else None
        )
        return CustomerFaqShortAnswerAttemptResponse(
            learning_unit_key=unit.unit_key,
            learning_unit_title=unit.title,
            total_score=total_score,
            max_score=100.0,
            passed=passed,
            pass_threshold=pass_threshold,
            answers=results,
        )


def _find_unit(
    units: list[BusinessEtiquetteTrainingUnitConfig],
    unit_key: str,
) -> BusinessEtiquetteTrainingUnitConfig | None:
    return next(
        (unit for unit in units if unit.unit_key == unit_key and unit.enabled),
        None,
    )
