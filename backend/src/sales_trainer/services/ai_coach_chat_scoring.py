from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachUiEvent
from sales_trainer.schemas import AiCoachAnswerPayloadV1, AiCoachScoreResultV1
from sales_trainer.services.ai_coach_chat_projection import (
    AiCoachChatProjection,
    AiCoachChatProjectionError,
)
from sales_trainer.services.ai_coach_session_service import (
    AiCoachSessionService,
    AiCoachSessionServiceError,
)


class AiCoachChatScoringError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachChatScorer:
    def __init__(self, db: AsyncSession) -> None:
        self._projection = AiCoachChatProjection()
        self._scoring = AiCoachSessionService(db)

    async def score_quiz_event(
        self,
        event: SalesTrainerAiCoachUiEvent,
        *,
        answer_payload: AiCoachAnswerPayloadV1 | dict[str, object],
    ) -> AiCoachScoreResultV1:
        if event.status != "pending" or event.answer_payload:
            raise AiCoachChatScoringError(
                "[AI_COACH_CHAT_EVENT_ALREADY_SUBMITTED]",
                "该互动卡片已经提交过。",
                409,
            )
        if event.event_type != "quiz_card":
            raise AiCoachChatScoringError(
                "[AI_COACH_CHAT_EVENT_NOT_ANSWERABLE]",
                "该 UI 事件不支持提交答案。",
                409,
            )
        try:
            payload = (
                answer_payload
                if isinstance(answer_payload, AiCoachAnswerPayloadV1)
                else AiCoachAnswerPayloadV1.model_validate(answer_payload)
            )
            internal = self._projection.internal_interaction_from_event(event)
            AiCoachSessionService._validate_answer_payload(internal, payload)
        except (ValidationError, AiCoachSessionServiceError, AiCoachChatProjectionError) as exc:
            raise self._scoring_error(exc) from exc
        return self._scoring.score_choice(
            answer_payload=payload,
            answer_key=internal.answer_key,
            scoring_rubric=internal.scoring_rubric,
            feedback_guidance=internal.feedback_guidance,
        )

    @staticmethod
    def _scoring_error(exc: Exception) -> AiCoachChatScoringError:
        if hasattr(exc, "code") and hasattr(exc, "message"):
            return AiCoachChatScoringError(
                str(getattr(exc, "code")),
                str(getattr(exc, "message")),
                int(getattr(exc, "status_code", 400)),
            )
        return AiCoachChatScoringError(
            "[AI_COACH_ANSWER_PAYLOAD_INVALID]",
            "AI 教练提交内容不符合要求。",
            422,
        )
