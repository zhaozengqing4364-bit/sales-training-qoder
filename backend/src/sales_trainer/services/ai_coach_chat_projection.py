from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from sales_trainer.ai_coach_chat_models import (
    SalesTrainerAiCoachChatMessage,
    SalesTrainerAiCoachUiEvent,
)
from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatMessagePublicV1,
    AiCoachChatSessionPhaseV1,
    AiCoachChatSessionPublicV1,
    AiCoachChatUiEventInternalV1,
    AiCoachCoachStatePublicV1,
    AiCoachExplanationCardPayloadV1,
    AiCoachFollowupPromptPayloadV1,
    AiCoachQuizCardPayloadInternalV1,
    AiCoachQuizCardPayloadPublicV1,
    AiCoachQuizResultPayloadV1,
    AiCoachSummaryCardPayloadV1,
    AiCoachUiEventPublicPayloadV1,
    AiCoachUiEventPublicV1,
)
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    AiCoachAnswerPayloadV1,
    AiCoachInteractionInternalV1,
    AiCoachInteractionPublicV1,
    AiCoachPublicInteractionOptionV1,
    AiCoachScoreResultV1,
)
from sales_trainer.services.ai_coach_chat_coach_state import coach_state_from_snapshot


class AiCoachChatProjectionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachChatProjection:
    def build_stored_event_payload(
        self,
        *,
        event_id: str,
        session: SalesTrainerAiCoachSession,
        event: AiCoachChatUiEventInternalV1,
        card_number: int,
    ) -> dict[str, Any]:
        match event.type:
            case "quiz_card":
                payload = event.payload
                if not isinstance(payload, AiCoachQuizCardPayloadInternalV1):
                    raise AiCoachChatProjectionError(
                        "[AI_COACH_INTERACTION_INVALID]",
                        "quiz_card payload 非法。",
                        502,
                    )
                public = self.project_interaction(
                    payload.interaction,
                    event_id=event_id,
                    session=session,
                    card_number=card_number,
                )
                return {
                    "interaction_snapshot": payload.interaction.model_dump(mode="json"),
                    "public_interaction": public.model_dump(mode="json"),
                    "explanation": payload.explanation,
                }
            case _:
                return event.payload.model_dump(mode="json")

    def public_payload_for_event(
        self,
        event_type: str,
        stored_payload: dict[str, Any],
    ) -> AiCoachUiEventPublicPayloadV1:
        match event_type:
            case "quiz_card":
                return AiCoachQuizCardPayloadPublicV1(
                    interaction=AiCoachInteractionPublicV1.model_validate(
                        stored_payload.get("public_interaction")
                    ),
                    explanation=stored_payload.get("explanation"),
                )
            case "explanation_card":
                return AiCoachExplanationCardPayloadV1.model_validate(stored_payload)
            case "summary_card":
                return AiCoachSummaryCardPayloadV1.model_validate(stored_payload)
            case "followup_prompt":
                return AiCoachFollowupPromptPayloadV1.model_validate(stored_payload)
            case "quiz_result":
                return AiCoachQuizResultPayloadV1.model_validate(stored_payload)
            case _:
                return AiCoachExplanationCardPayloadV1(
                    title="AI 教练",
                    body="这条消息暂不支持渲染。",
                )

    def project_session(
        self,
        session: SalesTrainerAiCoachSession,
        messages: list[SalesTrainerAiCoachChatMessage],
        events: list[SalesTrainerAiCoachUiEvent],
    ) -> AiCoachChatSessionPublicV1:
        public_events = [self.project_event(event) for event in events]
        return AiCoachChatSessionPublicV1(
            session_id=str(session.session_id),
            module_key=str(session.module_key),
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=[
                AiCoachChatMessagePublicV1(
                    message_id=str(message.message_id),
                    role=message.role,
                    content=message.content,
                    order_index=int(message.order_index),
                    created_at=message.created_at,
                )
                for message in messages
            ],
            ui_events=public_events,
            coach_state=self.project_coach_state(session, public_events),
        )

    def project_coach_state(
        self,
        session: SalesTrainerAiCoachSession,
        events: list[AiCoachUiEventPublicV1] | None = None,
    ) -> AiCoachCoachStatePublicV1:
        state = coach_state_from_snapshot(getattr(session, "coach_state", None))
        raw_active_event_id = self._active_event_id(events or [])
        active_event_id = (
            None
            if state.last_action in {"summarize", "end_session"}
            else raw_active_event_id
        )
        return AiCoachCoachStatePublicV1(
            session_phase=self._session_phase(
                status=session.status,
                active_event_id=active_event_id,
                last_action=state.last_action,
                events=events or [],
            ),
            active_event_id=active_event_id,
            auto_step_count=state.auto_step_count,
            answered_card_count=state.answered_card_count,
            correct_streak=state.correct_streak,
            incorrect_streak=state.incorrect_streak,
            current_focus=state.current_focus,
            difficulty=state.difficulty,
            last_action=state.last_action,
            can_auto_advance=state.can_auto_advance,
            stopped_reason=state.stopped_reason,
        )

    @staticmethod
    def _active_event_id(events: list[AiCoachUiEventPublicV1]) -> str | None:
        for event in events:
            if (
                event.type == "quiz_card"
                and event.status == "pending"
                and event.answer_payload is None
                and event.score_result is None
            ):
                return event.event_id
        return None

    @staticmethod
    def _session_phase(
        *,
        status: str,
        active_event_id: str | None,
        last_action: str | None,
        events: list[AiCoachUiEventPublicV1],
    ) -> AiCoachChatSessionPhaseV1:
        if status == "completed":
            return "completed"
        if active_event_id is not None:
            return "answering"
        if last_action in {"summarize", "end_session"}:
            return "summarizing"
        if any(event.type == "followup_prompt" and event.status == "pending" for event in events):
            return "choosing"
        if any(event.type == "quiz_card" and event.status == "scored" for event in events):
            return "reviewing"
        return "starting"

    def project_event(
        self,
        event: SalesTrainerAiCoachUiEvent,
    ) -> AiCoachUiEventPublicV1:
        answer_payload = None
        score_result = None
        if event.answer_payload:
            answer_payload = AiCoachAnswerPayloadV1.model_validate(event.answer_payload)
        if event.score_result:
            score_result = AiCoachScoreResultV1.model_validate(event.score_result)
        return AiCoachUiEventPublicV1(
            event_id=str(event.event_id),
            message_id=str(event.message_id),
            type=event.event_type,
            status=event.status,
            payload=self.public_payload_for_event(event.event_type, event.payload_json),
            answer_payload=answer_payload,
            score_result=score_result,
            order_index=int(event.order_index),
            created_at=event.created_at,
        )

    def internal_interaction_from_event(
        self,
        event: SalesTrainerAiCoachUiEvent,
    ) -> AiCoachInteractionInternalV1:
        try:
            return AiCoachInteractionInternalV1.model_validate(
                event.payload_json.get("interaction_snapshot")
            )
        except ValidationError as exc:
            raise AiCoachChatProjectionError(
                "[AI_COACH_INTERACTION_INVALID]",
                "互动卡片内部快照损坏，无法评分。",
                409,
            ) from exc

    def project_interaction(
        self,
        internal: AiCoachInteractionInternalV1,
        *,
        event_id: str,
        session: SalesTrainerAiCoachSession,
        card_number: int,
    ) -> AiCoachInteractionPublicV1:
        options = None
        if internal.options:
            options = [
                AiCoachPublicInteractionOptionV1(
                    option_id=option.option_id,
                    text=option.text,
                )
                for option in internal.options
            ]
        constraints: dict[str, int] = {}
        if internal.interaction_type == "single_choice":
            constraints = {"min_selected": 1, "max_selected": 1}
        elif internal.interaction_type == "multiple_choice":
            constraints = {"min_selected": 1, "max_selected": len(options or [])}
        else:
            constraints = {"min_length": 1, "max_length": 8000}
        return AiCoachInteractionPublicV1(
            interaction_id=event_id,
            session_id=str(session.session_id),
            turn_number=card_number,
            interaction_type=internal.interaction_type,
            stem=internal.stem,
            options=options,
            answer_constraints=constraints,
        )
