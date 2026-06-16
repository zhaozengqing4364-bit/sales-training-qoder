from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatEventAnswerSubmit,
    AiCoachChatMessageCreate,
    AiCoachChatSessionCreate,
    AiCoachChatStreamErrorEventV1,
    AiCoachChatStreamEventV1,
    AiCoachChatStreamSessionSnapshotEventV1,
    AiCoachChatStreamStatusEventV1,
    AiCoachChatStreamUiEventDeltaEventV1,
    AiCoachQuizCardDraftPayloadPublicV1,
)
from sales_trainer.services.ai_coach_chat_errors import (
    AI_COACH_STREAM_TIMEOUT_CODE,
    AI_COACH_STREAM_TIMEOUT_MESSAGE,
    AiCoachChatServiceError,
)
from sales_trainer.services.ai_coach_chat_service import AiCoachChatService


class AiCoachChatStreamService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        service: AiCoachChatService | None = None,
    ) -> None:
        self._service = service or AiCoachChatService(db)

    async def stream_create_session(
        self,
        *,
        payload: AiCoachChatSessionCreate,
        actor: User,
    ) -> AsyncIterator[str]:
        user_id = str(actor.user_id)
        async for chunk in self._guarded(
            self._stream_create_session(payload=payload, user_id=user_id, actor=actor)
        ):
            yield chunk

    async def stream_send_message(
        self,
        *,
        session_id: str,
        payload: AiCoachChatMessageCreate,
        actor: User,
    ) -> AsyncIterator[str]:
        user_id = str(actor.user_id)
        async for chunk in self._guarded(
            self._stream_send_message(
                session_id=session_id,
                payload=payload,
                user_id=user_id,
                actor=actor,
            )
        ):
            yield chunk

    async def stream_submit_answer(
        self,
        *,
        session_id: str,
        event_id: str,
        payload: AiCoachChatEventAnswerSubmit,
        actor: User,
    ) -> AsyncIterator[str]:
        user_id = str(actor.user_id)
        async for chunk in self._guarded(
            self._stream_submit_answer(
                session_id=session_id,
                event_id=event_id,
                payload=payload,
                user_id=user_id,
                actor=actor,
            )
        ):
            yield chunk

    async def _stream_create_session(
        self,
        *,
        payload: AiCoachChatSessionCreate,
        user_id: str,
        actor: User,
    ) -> AsyncIterator[AiCoachChatStreamEventV1]:
        yield self._status("resolving_session", "正在检查是否有可继续的训练局。")
        session = await self._service.create_session_shell(
            user_id=user_id,
            module_key=payload.module_key,
            resume_strategy=payload.resume_strategy,
            actor=actor,
        )
        yield self._snapshot(session, phase="session_ready")
        if session.messages and len(session.messages) > 1:
            yield self._status(
                "completed",
                "已恢复当前可继续训练局。",
                session_id=session.session_id,
            )
            return
        config = self._service._runtime.config_from_session(  # noqa: SLF001
            await self._service._require_owned_session(session.session_id, user_id)  # noqa: SLF001
        )
        if not config.streaming_enabled:
            yield self._error(
                "[AI_COACH_STREAMING_DISABLED]",
                "该模块未启用流式训练体验，请使用普通训练入口。",
            )
            return
        yield self._status(
            "generating_first_card",
            "正在生成本轮训练计划和第一张题卡。",
            session_id=session.session_id,
        )
        queue, on_delta = self._delta_queue(
            session_id=session.session_id,
            phase="generating_first_card",
        )
        task = asyncio.create_task(
            asyncio.wait_for(
                self._service.start_session_auto_advance(
                    session_id=session.session_id,
                    user_id=user_id,
                    actor=actor,
                    on_generation_delta=on_delta,
                ),
                timeout=float(config.generation_timeout_seconds),
            )
        )
        while not task.done() or not queue.empty():
            delta = await self._poll_delta(task, queue)
            if delta is not None:
                yield delta
        session = await task
        yield self._snapshot(session, phase="completed")

    async def _stream_send_message(
        self,
        *,
        session_id: str,
        payload: AiCoachChatMessageCreate,
        user_id: str,
        actor: User,
    ) -> AsyncIterator[AiCoachChatStreamEventV1]:
        config = self._service._runtime.config_from_session(  # noqa: SLF001
            await self._service._require_owned_session(session_id, user_id)  # noqa: SLF001
        )
        if not config.streaming_enabled:
            yield self._error(
                "[AI_COACH_STREAMING_DISABLED]",
                "该模块未启用流式训练体验，请使用普通训练入口。",
            )
            return
        yield self._status("saving_user_message", "正在保存你的输入。", session_id=session_id)
        yield self._status(
            "generating_next_card",
            "正在生成教练回复和下一步训练内容。",
            session_id=session_id,
        )
        queue, on_delta = self._delta_queue(
            session_id=session_id,
            phase="generating_next_card",
        )
        task = asyncio.create_task(
            asyncio.wait_for(
                self._service.send_message(
                    session_id=session_id,
                    user_id=user_id,
                    payload=payload,
                    actor=actor,
                    on_generation_delta=on_delta,
                ),
                timeout=float(config.generation_timeout_seconds),
            )
        )
        while not task.done() or not queue.empty():
            delta = await self._poll_delta(task, queue)
            if delta is not None:
                yield delta
        session = await task
        yield self._snapshot(session, phase="completed")

    async def _stream_submit_answer(
        self,
        *,
        session_id: str,
        event_id: str,
        payload: AiCoachChatEventAnswerSubmit,
        user_id: str,
        actor: User,
    ) -> AsyncIterator[AiCoachChatStreamEventV1]:
        config = self._service._runtime.config_from_session(  # noqa: SLF001
            await self._service._require_owned_session(session_id, user_id)  # noqa: SLF001
        )
        if not config.streaming_enabled:
            yield self._error(
                "[AI_COACH_STREAMING_DISABLED]",
                "该模块未启用流式训练体验，请使用普通训练入口。",
            )
            return
        yield self._status("scoring_answer", "正在批改当前题卡。", session_id=session_id)
        event_payload, score_result = await self._service.score_and_persist_event_answer(
            session_id=session_id,
            event_id=event_id,
            user_id=user_id,
            answer_payload=payload.answer_payload,
            actor=actor,
        )
        yield self._snapshot(await self._service.public_session(session_id, user_id), phase="answer_scored")
        should_generate_next = bool(getattr(config, "proactive_coaching_enabled", False)) and bool(
            getattr(config, "auto_advance_enabled", False)
        )
        if not should_generate_next:
            await self._service.advance_after_scored_event(
                session_id=session_id,
                event_id=event_id,
                user_id=user_id,
                event_payload=event_payload,
                score_result=score_result,
                answer_payload=payload.answer_payload,
                actor=actor,
            )
            yield self._snapshot(await self._service.public_session(session_id, user_id), phase="completed")
            return
        yield self._status(
            "deciding_next_action",
            "正在判断下一步训练动作。",
            session_id=session_id,
        )
        yield self._status(
            "generating_next_card",
            "正在生成下一张题卡或阶段复盘。",
            session_id=session_id,
        )
        fallback_actor = self._actor_snapshot(actor)
        queue, on_delta = self._delta_queue(
            session_id=session_id,
            phase="generating_next_card",
        )
        try:
            task = asyncio.create_task(
                asyncio.wait_for(
                    self._service.advance_after_scored_event(
                        session_id=session_id,
                        event_id=event_id,
                        user_id=user_id,
                        event_payload=event_payload,
                        score_result=score_result,
                        answer_payload=payload.answer_payload,
                        actor=actor,
                        on_generation_delta=on_delta,
                    ),
                    timeout=float(config.generation_timeout_seconds),
                )
            )
            while not task.done() or not queue.empty():
                delta = await self._poll_delta(task, queue)
                if delta is not None:
                    yield delta
            await task
        except TimeoutError:
            await self._service.rollback_cancelled_generation()
            await self._service.record_advance_timeout_after_scored_event(
                session_id=session_id,
                event_id=event_id,
                user_id=user_id,
                score_result=score_result,
                actor=fallback_actor,
            )
        yield self._snapshot(await self._service.public_session(session_id, user_id), phase="completed")

    async def _guarded(
        self,
        events: AsyncIterator[AiCoachChatStreamEventV1],
    ) -> AsyncIterator[str]:
        try:
            async for event in events:
                yield self._encode(event)
        except AiCoachChatServiceError as exc:
            yield self._encode(self._error(exc.code, exc.message))
        except TimeoutError:
            yield self._encode(
                self._error(
                    AI_COACH_STREAM_TIMEOUT_CODE,
                    AI_COACH_STREAM_TIMEOUT_MESSAGE,
                )
            )

    @staticmethod
    def _status(
        phase,
        message: str,
        *,
        session_id: str | None = None,
    ) -> AiCoachChatStreamStatusEventV1:
        return AiCoachChatStreamStatusEventV1(
            phase=phase,
            message=message,
            session_id=session_id,
        )

    @staticmethod
    def _snapshot(
        session,
        *,
        phase,
    ) -> AiCoachChatStreamSessionSnapshotEventV1:
        return AiCoachChatStreamSessionSnapshotEventV1(
            phase=phase,
            session=session,
        )

    @staticmethod
    def _delta_queue(
        *,
        session_id: str,
        phase,
    ):
        queue: asyncio.Queue[AiCoachChatStreamUiEventDeltaEventV1] = asyncio.Queue()

        async def on_delta(draft: AiCoachQuizCardDraftPayloadPublicV1) -> None:
            await queue.put(
                AiCoachChatStreamUiEventDeltaEventV1(
                    phase=phase,
                    session_id=session_id,
                    delta_id=f"{session_id}:quiz_card",
                    payload=draft,
                )
            )

        return queue, on_delta

    @staticmethod
    async def _poll_delta(
        task: asyncio.Task,
        queue: asyncio.Queue[AiCoachChatStreamUiEventDeltaEventV1],
    ) -> AiCoachChatStreamUiEventDeltaEventV1 | None:
        if task.done() and queue.empty():
            return None
        try:
            return await asyncio.wait_for(queue.get(), timeout=0.05)
        except TimeoutError:
            return None

    @staticmethod
    def _error(
        error_code: str,
        message: str,
        *,
        recoverable: bool = True,
    ) -> AiCoachChatStreamErrorEventV1:
        return AiCoachChatStreamErrorEventV1(
            error_code=error_code,
            message=message,
            recoverable=recoverable,
        )

    @staticmethod
    def _actor_snapshot(actor: User | None):
        if actor is None:
            return None
        return SimpleNamespace(
            user_id=str(actor.user_id),
            role=str(getattr(actor, "role", "")),
        )

    @staticmethod
    def _encode(event: AiCoachChatStreamEventV1) -> str:
        payload = event.model_dump(mode="json")
        return (
            f"event: {event.type}\n"
            f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"
        )
