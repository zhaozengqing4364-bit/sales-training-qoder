from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.ai_coach_chat_models import (
    SalesTrainerAiCoachChatMessage,
    SalesTrainerAiCoachUiEvent,
)
from sales_trainer.ai_coach_chat_schemas import AiCoachChatUiEventInternalV1
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.services.ai_coach_chat_errors import service_error_from_exception
from sales_trainer.services.ai_coach_chat_projection import (
    AiCoachChatProjection,
    AiCoachChatProjectionError,
)
from sales_trainer.services.ai_coach_chat_store import AiCoachChatStore


class AiCoachChatEventWriter:
    def __init__(
        self,
        db: AsyncSession,
        projection: AiCoachChatProjection,
        store: AiCoachChatStore,
    ) -> None:
        self._db = db
        self._projection = projection
        self._store = store

    async def persist_ui_events(
        self,
        session: SalesTrainerAiCoachSession,
        assistant: SalesTrainerAiCoachChatMessage,
        events: list[AiCoachChatUiEventInternalV1],
    ) -> None:
        card_number = await self._store.next_card_number(str(session.session_id))
        for index, event in enumerate(events, start=1):
            event_id = str(uuid.uuid4())
            stored_payload = self.build_stored_event_payload(
                event_id=event_id,
                session=session,
                event=event,
                card_number=card_number,
            )
            if event.type == "quiz_card":
                card_number += 1
            self._db.add(
                SalesTrainerAiCoachUiEvent(
                    event_id=event_id,
                    session_id=session.session_id,
                    message_id=assistant.message_id,
                    event_type=event.type,
                    status="pending",
                    payload_json=stored_payload,
                    order_index=index,
                )
            )

    def build_stored_event_payload(
        self,
        *,
        event_id: str,
        session: SalesTrainerAiCoachSession,
        event: AiCoachChatUiEventInternalV1,
        card_number: int,
    ) -> dict[str, Any]:
        try:
            return self._projection.build_stored_event_payload(
                event_id=event_id,
                session=session,
                event=event,
                card_number=card_number,
            )
        except AiCoachChatProjectionError as exc:
            raise service_error_from_exception(exc) from exc
