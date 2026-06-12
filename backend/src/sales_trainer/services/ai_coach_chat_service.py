from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.ai_coach_chat_models import (
    SalesTrainerAiCoachChatMessage,
    SalesTrainerAiCoachUiEvent,
)
from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatMessageCreate,
    AiCoachChatSessionPublicV1,
    AiCoachChatUiEventInternalV1,
)
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import AiCoachAnswerPayloadV1
from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
from sales_trainer.services.ai_coach_chat_errors import (
    AiCoachChatGenerationError,
    AiCoachChatServiceError,
    service_error_from_exception,
)
from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
from sales_trainer.services.ai_coach_chat_projection import (
    AiCoachChatProjection,
)
from sales_trainer.services.ai_coach_chat_runtime import (
    AiCoachChatRuntime,
    AiCoachChatRuntimeError,
)
from sales_trainer.services.ai_coach_chat_scoring import (
    AiCoachChatScorer,
    AiCoachChatScoringError,
)
from sales_trainer.services.ai_coach_chat_session_creator import (
    AiCoachChatSessionCreator,
)
from sales_trainer.services.ai_coach_chat_store import (
    AiCoachChatStore,
    AiCoachChatStoreError,
)
from sales_trainer.services.operation_log_service import OperationLogService


class AiCoachChatService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._logs = OperationLogService(db)
        self._scoring = AiCoachChatScorer(db)
        self._runtime = AiCoachChatRuntime(db)
        self._projection = AiCoachChatProjection()
        self._store = AiCoachChatStore(db)
        self._events = AiCoachChatEventWriter(db, self._projection, self._store)
        self._auto_advance = AiCoachChatAutoAdvance(
            db,
            self._store,
            self._events,
            self._logs,
        )
        self._session_creator = AiCoachChatSessionCreator(
            db,
            self._runtime,
            self._logs,
            self._store,
            self._events,
        )

    async def create_session(
        self,
        *,
        user_id: str,
        module_key: str,
        resume_strategy: str = "new",
        actor: User | None = None,
    ) -> AiCoachChatSessionPublicV1:
        if resume_strategy == "latest_in_progress":
            existing = await self._store.latest_in_progress_session(
                user_id=user_id,
                module_key=module_key,
            )
            if existing is not None:
                return await self.public_session(str(existing.session_id), user_id)
        session_id = await self._session_creator.create_session_id(
            actor=actor,
            user_id=user_id,
            module_key=module_key,
        )
        return await self.public_session(session_id, user_id)

    async def public_session(
        self,
        session_id: str,
        user_id: str,
    ) -> AiCoachChatSessionPublicV1:
        session = await self._require_owned_session(session_id, user_id)
        messages = await self._store.messages(session_id)
        events = await self._store.events(session_id)
        return self._projection.project_session(session, messages, events)

    async def send_message(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: AiCoachChatMessageCreate,
        actor: User | None = None,
    ) -> AiCoachChatSessionPublicV1:
        session = await self._require_owned_session(session_id, user_id)
        if session.status != "in_progress":
            raise AiCoachChatServiceError(
                "[AI_COACH_SESSION_NOT_IN_PROGRESS]",
                "AI 教练会话已结束，无法继续对话。",
                409,
            )
        if payload.event_id is not None:
            await self._event(session_id, payload.event_id)
        message = (
            self._command_display_text(payload.command)
            if payload.command is not None
            else (payload.content or "").strip()
        )
        user_order = await self._store.next_message_order(session_id)
        self._db.add(
            SalesTrainerAiCoachChatMessage(
                session_id=session_id,
                role="user",
                content=message,
                order_index=user_order,
            )
        )
        await self._db.flush()
        if payload.command is not None:
            try:
                await self._auto_advance.advance_for_command(
                    session=session,
                    config=self._runtime.config_from_session(session),
                    command=payload.command,
                    event_id=payload.event_id,
                    actor=actor,
                )
            except AiCoachChatGenerationError as exc:
                raise service_error_from_exception(exc) from exc
            return await self.public_session(session_id, user_id)
        history = await self._store.messages(session_id)
        try:
            response = await self._runtime.generate_chat_response(
                session=session,
                config=self._runtime.config_from_session(session),
                user_message=message,
                history=history,
            )
        except AiCoachChatRuntimeError as exc:
            raise service_error_from_exception(exc) from exc
        assistant = SalesTrainerAiCoachChatMessage(
            session_id=session_id,
            role="assistant",
            content=response.assistant_text,
            order_index=user_order + 1,
        )
        self._db.add(assistant)
        await self._db.flush()
        await self._events.persist_ui_events(session, assistant, response.ui_events)
        await self._logs.record(
            actor=actor,
            action="ai_coach_chat_message_sent_v1",
            target_type="sales_trainer_ai_coach_session",
            target_id=session_id,
            metadata={
                "ui_event_count": len(response.ui_events),
                "schema_version": response.schema_version,
            },
        )
        await self._db.commit()
        return await self.public_session(session_id, user_id)

    @staticmethod
    def _command_display_text(command: str | None) -> str:
        labels = {
            "continue": "继续下一题",
            "explain": "讲解一下",
            "switch_scenario": "换个场景",
            "summarize": "总结本轮",
            "end": "结束训练",
            "retry": "重试当前步骤",
        }
        return labels.get(command or "", "继续训练")

    async def submit_event_answer(
        self,
        *,
        session_id: str,
        event_id: str,
        user_id: str,
        answer_payload: AiCoachAnswerPayloadV1,
        actor: User | None = None,
    ) -> AiCoachChatSessionPublicV1:
        session = await self._require_owned_session(session_id, user_id)
        event = await self._event(session_id, event_id)
        score_result = await self.score_quiz_event(event, answer_payload=answer_payload)
        event.answer_payload = answer_payload.model_dump(mode="json")
        event.score_result = score_result.model_dump(mode="json")
        event.status = "scored"
        await self._logs.record(
            actor=actor,
            action="ai_coach_chat_card_submitted_v1",
            target_type="sales_trainer_ai_coach_ui_event",
            target_id=event_id,
            metadata={"session_id": session_id, "score": score_result.score},
        )
        await self._db.flush()
        await self._db.commit()
        try:
            await self._auto_advance.advance_after_answer(
                session=session,
                config=self._runtime.config_from_session(session),
                event_payload=event.payload_json,
                event_id=event_id,
                score_result=score_result,
                answer_payload=answer_payload,
                actor=actor,
            )
        except AiCoachChatGenerationError as exc:
            raise service_error_from_exception(exc) from exc
        return await self.public_session(session_id, user_id)

    async def score_quiz_event(
        self,
        event: SalesTrainerAiCoachUiEvent,
        *,
        answer_payload: AiCoachAnswerPayloadV1 | dict[str, object],
    ):
        if event.status != "pending" or event.answer_payload:
            raise AiCoachChatServiceError(
                "[AI_COACH_CHAT_EVENT_ALREADY_SUBMITTED]",
                "该互动卡片已经提交过。",
                409,
            )
        if event.event_type != "quiz_card":
            raise AiCoachChatServiceError(
                "[AI_COACH_CHAT_EVENT_NOT_ANSWERABLE]",
                "该 UI 事件不支持提交答案。",
                409,
            )
        try:
            return await self._scoring.score_quiz_event(
                event,
                answer_payload=answer_payload,
            )
        except AiCoachChatScoringError as exc:
            raise service_error_from_exception(exc) from exc

    def build_stored_event_payload(
        self,
        *,
        event_id: str,
        session: SalesTrainerAiCoachSession,
        event: AiCoachChatUiEventInternalV1,
        card_number: int,
    ) -> dict[str, Any]:
        try:
            return self._events.build_stored_event_payload(
                event_id=event_id,
                session=session,
                event=event,
                card_number=card_number,
            )
        except AiCoachChatServiceError:
            raise

    def public_payload_for_event(self, event_type: str, stored_payload: dict[str, Any]):
        return self._projection.public_payload_for_event(event_type, stored_payload)

    async def _require_owned_session(
        self,
        session_id: str,
        user_id: str,
    ) -> SalesTrainerAiCoachSession:
        try:
            return await self._store.require_owned_session(session_id, user_id)
        except AiCoachChatStoreError as exc:
            raise service_error_from_exception(exc) from exc

    async def _event(
        self,
        session_id: str,
        event_id: str,
    ) -> SalesTrainerAiCoachUiEvent:
        try:
            return await self._store.event(session_id, event_id)
        except AiCoachChatStoreError as exc:
            raise service_error_from_exception(exc) from exc
