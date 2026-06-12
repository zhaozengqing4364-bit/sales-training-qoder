from __future__ import annotations

from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachCoachAction
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import AiCoachNextActionV1
from sales_trainer.services.ai_coach_chat_coach_state import AiCoachCoachStateV1


class AiCoachChatActionStore:
    def add_action(
        self,
        session: SalesTrainerAiCoachSession,
        *,
        trigger_type: str,
        trigger_event_id: str | None,
        action: AiCoachNextActionV1,
        reason: str,
        status: str,
        state_before: AiCoachCoachStateV1,
        state_after: AiCoachCoachStateV1,
        assistant_message_id: str | None = None,
        error_code: str | None = None,
    ) -> SalesTrainerAiCoachCoachAction:
        return SalesTrainerAiCoachCoachAction(
            session_id=session.session_id,
            trigger_type=trigger_type,
            trigger_event_id=trigger_event_id,
            action=action,
            reason=reason,
            status=status,
            state_before=state_before.model_dump(mode="json"),
            state_after=state_after.model_dump(mode="json"),
            assistant_message_id=assistant_message_id,
            error_code=error_code,
        )
