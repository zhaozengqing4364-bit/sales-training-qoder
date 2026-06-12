from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.ai_coach_chat_models import (
    SalesTrainerAiCoachChatMessage,
    SalesTrainerAiCoachUiEvent,
)
from sales_trainer.models import SalesTrainerAiCoachSession


class AiCoachChatStoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AiCoachChatStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def require_owned_session(
        self,
        session_id: str,
        user_id: str,
    ) -> SalesTrainerAiCoachSession:
        session = await self._db.get(SalesTrainerAiCoachSession, session_id)
        if session is None:
            raise AiCoachChatStoreError(
                "[AI_COACH_SESSION_NOT_FOUND]",
                "AI 教练会话不存在。",
                404,
            )
        if str(session.user_id) != str(user_id):
            raise AiCoachChatStoreError("[ACCESS_DENIED]", "无权查看该会话。", 403)
        return session

    async def latest_in_progress_session(
        self,
        *,
        user_id: str,
        module_key: str,
    ) -> SalesTrainerAiCoachSession | None:
        result = await self._db.execute(
            select(SalesTrainerAiCoachSession)
            .where(
                SalesTrainerAiCoachSession.user_id == user_id,
                SalesTrainerAiCoachSession.module_key == module_key,
                SalesTrainerAiCoachSession.status == "in_progress",
            )
            .order_by(
                SalesTrainerAiCoachSession.updated_at.desc(),
                SalesTrainerAiCoachSession.created_at.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def event(
        self,
        session_id: str,
        event_id: str,
    ) -> SalesTrainerAiCoachUiEvent:
        result = await self._db.execute(
            select(SalesTrainerAiCoachUiEvent).where(
                SalesTrainerAiCoachUiEvent.session_id == session_id,
                SalesTrainerAiCoachUiEvent.event_id == event_id,
            )
        )
        event = result.scalars().first()
        if event is None:
            raise AiCoachChatStoreError(
                "[AI_COACH_CHAT_EVENT_NOT_FOUND]",
                "互动卡片不存在。",
                404,
            )
        return event

    async def messages(self, session_id: str) -> list[SalesTrainerAiCoachChatMessage]:
        result = await self._db.execute(
            select(SalesTrainerAiCoachChatMessage)
            .where(SalesTrainerAiCoachChatMessage.session_id == session_id)
            .order_by(SalesTrainerAiCoachChatMessage.order_index.asc())
        )
        return list(result.scalars().all())

    async def events(self, session_id: str) -> list[SalesTrainerAiCoachUiEvent]:
        result = await self._db.execute(
            select(SalesTrainerAiCoachUiEvent)
            .where(SalesTrainerAiCoachUiEvent.session_id == session_id)
            .order_by(
                SalesTrainerAiCoachUiEvent.created_at.asc(),
                SalesTrainerAiCoachUiEvent.order_index.asc(),
            )
        )
        return list(result.scalars().all())

    async def next_message_order(self, session_id: str) -> int:
        result = await self._db.scalar(
            select(func.max(SalesTrainerAiCoachChatMessage.order_index)).where(
                SalesTrainerAiCoachChatMessage.session_id == session_id
            )
        )
        return int(result or 0) + 1

    async def next_card_number(self, session_id: str) -> int:
        result = await self._db.scalar(
            select(func.count())
            .select_from(SalesTrainerAiCoachUiEvent)
            .where(
                SalesTrainerAiCoachUiEvent.session_id == session_id,
                SalesTrainerAiCoachUiEvent.event_type == "quiz_card",
            )
        )
        return int(result or 0) + 1
