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
    AiCoachFollowupPromptPayloadV1,
    AiCoachUiEventPublicPayloadV1,
)
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import AiCoachAnswerPayloadV1, AiCoachScoreResultV1
from sales_trainer.services.ai_coach_chat_auto_advance import AiCoachChatAutoAdvance
from sales_trainer.services.ai_coach_chat_errors import (
    AiCoachChatGenerationError,
    AiCoachChatServiceError,
    service_error_from_exception,
)
from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
from sales_trainer.services.ai_coach_chat_generation_streaming import (
    AiCoachGenerationDeltaHandler,
)
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
from sales_trainer.services.business_etiquette_ai_coach_progress_service import (
    BusinessEtiquetteAiCoachProgressService,
    BusinessEtiquetteAiCoachProgressServiceError,
)
from sales_trainer.services.business_etiquette_learning_service import (
    BUSINESS_SKILLS_MODULE_KEY,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


class AiCoachChatService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        logs: OperationLogService | None = None,
        scoring: AiCoachChatScorer | None = None,
        runtime: AiCoachChatRuntime | None = None,
        projection: AiCoachChatProjection | None = None,
        store: AiCoachChatStore | None = None,
        events: AiCoachChatEventWriter | None = None,
        auto_advance: AiCoachChatAutoAdvance | None = None,
        session_creator: AiCoachChatSessionCreator | None = None,
    ) -> None:
        self._db = db
        self._logs = logs or OperationLogService(db)
        self._scoring = scoring or AiCoachChatScorer(db)
        self._runtime = runtime or AiCoachChatRuntime(db)
        self._projection = projection or AiCoachChatProjection()
        self._store = store or AiCoachChatStore(db)
        self._events = events or AiCoachChatEventWriter(
            db,
            self._projection,
            self._store,
        )
        self._auto_advance = auto_advance or AiCoachChatAutoAdvance(
            db,
            self._store,
            self._events,
            self._logs,
        )
        self._session_creator = session_creator or AiCoachChatSessionCreator(
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
        resume_strategy: str | None = None,
        actor: User | None = None,
    ) -> AiCoachChatSessionPublicV1:
        resume_strategy = await self._resolve_resume_strategy(
            module_key=module_key,
            resume_strategy=resume_strategy,
        )
        if resume_strategy == "latest_in_progress":
            existing = await self._store.latest_in_progress_session(
                user_id=user_id,
                module_key=module_key,
            )
            if existing is not None:
                return await self.public_session(str(existing.session_id), user_id)
        if resume_strategy == "latest_active_or_new":
            active_session = await self._latest_active_session(
                user_id=user_id,
                module_key=module_key,
            )
            if active_session is not None:
                return active_session
        session_id = await self._session_creator.create_session_id(
            actor=actor,
            user_id=user_id,
            module_key=module_key,
        )
        return await self.public_session(session_id, user_id)

    async def create_session_shell(
        self,
        *,
        user_id: str,
        module_key: str,
        resume_strategy: str | None = None,
        actor: User | None = None,
    ) -> AiCoachChatSessionPublicV1:
        resume_strategy = await self._resolve_resume_strategy(
            module_key=module_key,
            resume_strategy=resume_strategy,
        )
        if resume_strategy == "latest_in_progress":
            existing = await self._store.latest_in_progress_session(
                user_id=user_id,
                module_key=module_key,
            )
            if existing is not None:
                return await self.public_session(str(existing.session_id), user_id)
        if resume_strategy == "latest_active_or_new":
            active_session = await self._latest_active_session(
                user_id=user_id,
                module_key=module_key,
            )
            if active_session is not None:
                return active_session
        session_id = await self._session_creator.create_session_id(
            actor=actor,
            user_id=user_id,
            module_key=module_key,
            start_auto_advance=False,
        )
        return await self.public_session(session_id, user_id)

    async def start_session_auto_advance(
        self,
        *,
        session_id: str,
        user_id: str,
        actor: User | None = None,
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> AiCoachChatSessionPublicV1:
        session = await self._require_owned_session(session_id, user_id)
        try:
            await self._auto_advance.start_session_if_configured(
                session=session,
                config=self._runtime.config_from_session(session),
                actor=actor,
                on_generation_delta=on_generation_delta,
            )
        except AiCoachChatGenerationError as exc:
            raise service_error_from_exception(exc) from exc
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
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
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
                    on_generation_delta=on_generation_delta,
                )
            except AiCoachChatGenerationError as exc:
                raise service_error_from_exception(exc) from exc
            return await self.public_session(session_id, user_id)
        history = await self._store.messages(session_id)
        config = self._runtime.config_from_session(session)
        try:
            response = await self._runtime.generate_chat_response(
                session=session,
                config=config,
                user_message=message,
                history=history,
                on_generation_delta=on_generation_delta,
            )
        except AiCoachChatRuntimeError as exc:
            raise service_error_from_exception(exc) from exc
        if not response.ui_events:
            response.ui_events.append(
                AiCoachChatUiEventInternalV1(
                    type="followup_prompt",
                    payload=AiCoachFollowupPromptPayloadV1(
                        prompts=list(config.empty_response_recovery_prompts),
                    ),
                )
            )
            response.assistant_text = (
                response.assistant_text.strip()
                or config.empty_response_recovery_message
            )
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
                "llm_runtime": dict(response.runtime_audit or {}),
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
        event_payload, score_result = await self.score_and_persist_event_answer(
            session_id=session_id,
            event_id=event_id,
            user_id=user_id,
            answer_payload=answer_payload,
            actor=actor,
        )
        await self.advance_after_scored_event(
            session_id=session_id,
            event_id=event_id,
            user_id=user_id,
            event_payload=event_payload,
            score_result=score_result,
            answer_payload=answer_payload,
            actor=actor,
        )
        return await self.public_session(session_id, user_id)

    async def score_and_persist_event_answer(
        self,
        *,
        session_id: str,
        event_id: str,
        user_id: str,
        answer_payload: AiCoachAnswerPayloadV1,
        actor: User | None = None,
    ) -> tuple[dict[str, object], AiCoachScoreResultV1]:
        session = await self._require_owned_session(session_id, user_id)
        event = await self._event(session_id, event_id)
        scoring_runtime_metadata: dict[str, object] = {}
        score_result = await self.score_quiz_event(
            event,
            answer_payload=answer_payload,
            runtime_metadata_out=scoring_runtime_metadata,
        )
        score_result = self._with_mastery_context(
            score_result,
            threshold=self._runtime.config_from_session(session).mastery_threshold,
        )
        event_payload = dict(event.payload_json or {})
        setattr(event, "answer_payload", answer_payload.model_dump(mode="json"))
        score_result_payload = score_result.model_dump(mode="json")
        if scoring_runtime_metadata:
            score_result_payload["runtime_audit"] = {
                "scoring": dict(scoring_runtime_metadata)
            }
        setattr(event, "score_result", score_result_payload)
        setattr(event, "status", "scored")
        await self._logs.record(
            actor=actor,
            action="ai_coach_chat_card_submitted_v1",
            target_type="sales_trainer_ai_coach_ui_event",
            target_id=event_id,
            metadata={"session_id": session_id, "score": score_result.score},
        )
        await self._db.flush()
        if str(session.module_key) == BUSINESS_SKILLS_MODULE_KEY:
            try:
                await BusinessEtiquetteAiCoachProgressService(
                    self._db,
                    store=self._store,
                    logs=self._logs,
                ).update_session_progress_snapshot(session, actor=actor)
            except BusinessEtiquetteAiCoachProgressServiceError as exc:
                raise AiCoachChatServiceError(
                    exc.code,
                    exc.message,
                    exc.status_code,
                ) from exc
        await self._db.commit()
        return event_payload, score_result

    async def advance_after_scored_event(
        self,
        *,
        session_id: str,
        event_id: str,
        user_id: str,
        event_payload: dict[str, object],
        score_result: AiCoachScoreResultV1,
        answer_payload: AiCoachAnswerPayloadV1,
        actor: User | None = None,
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> None:
        session = await self._require_owned_session(session_id, user_id)
        try:
            await self._auto_advance.advance_after_answer(
                session=session,
                config=self._runtime.config_from_session(session),
                event_payload=event_payload,
                event_id=event_id,
                score_result=score_result,
                answer_payload=answer_payload,
                actor=actor,
                on_generation_delta=on_generation_delta,
            )
        except AiCoachChatGenerationError as exc:
            raise service_error_from_exception(exc) from exc

    async def rollback_cancelled_generation(self) -> None:
        await self._db.rollback()

    async def record_advance_timeout_after_scored_event(
        self,
        *,
        session_id: str,
        event_id: str,
        user_id: str,
        score_result: AiCoachScoreResultV1,
        actor: User | None = None,
    ) -> None:
        session = await self._require_owned_session(session_id, user_id)
        await self._auto_advance.record_timeout_after_answer(
            session=session,
            config=self._runtime.config_from_session(session),
            event_id=event_id,
            score_result=score_result,
            actor=actor,
        )

    async def score_quiz_event(
        self,
        event: SalesTrainerAiCoachUiEvent,
        *,
        answer_payload: AiCoachAnswerPayloadV1 | dict[str, object],
        runtime_metadata_out: dict[str, object] | None = None,
    ) -> AiCoachScoreResultV1:
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
                runtime_metadata_out=runtime_metadata_out,
            )
        except AiCoachChatScoringError as exc:
            raise service_error_from_exception(exc) from exc

    @staticmethod
    def _with_mastery_context(
        score_result: AiCoachScoreResultV1,
        *,
        threshold: float,
    ) -> AiCoachScoreResultV1:
        return score_result.model_copy(
            update={
                "mastery_threshold": threshold,
                "mastered": score_result.score >= threshold,
            }
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
            return self._events.build_stored_event_payload(
                event_id=event_id,
                session=session,
                event=event,
                card_number=card_number,
            )
        except AiCoachChatServiceError:
            raise

    def public_payload_for_event(
        self,
        event_type: str,
        stored_payload: dict[str, Any],
    ) -> AiCoachUiEventPublicPayloadV1:
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

    async def _latest_active_session(
        self,
        *,
        user_id: str,
        module_key: str,
    ) -> AiCoachChatSessionPublicV1 | None:
        existing = await self._store.latest_in_progress_session(
            user_id=user_id,
            module_key=module_key,
        )
        if existing is None:
            return None
        public = await self.public_session(str(existing.session_id), user_id)
        if (
            public.coach_state is not None
            and public.coach_state.session_phase == "answering"
            and public.coach_state.active_event_id
        ):
            return public
        return None

    async def _resolve_resume_strategy(
        self,
        *,
        module_key: str,
        resume_strategy: str | None,
    ) -> str:
        if resume_strategy is not None:
            return resume_strategy
        path_response = await SalesTrainerPathConfigService(self._db).get_config()
        try:
            _, config = self._runtime.module_ai_coach_config(
                path_response.get("path"),
                module_key,
            )
            self._runtime.validate_chat_config(config)
        except AiCoachChatRuntimeError as exc:
            raise service_error_from_exception(exc) from exc
        return config.entry_resume_policy

    async def _event(
        self,
        session_id: str,
        event_id: str,
    ) -> SalesTrainerAiCoachUiEvent:
        try:
            return await self._store.event(session_id, event_id)
        except AiCoachChatStoreError as exc:
            raise service_error_from_exception(exc) from exc
