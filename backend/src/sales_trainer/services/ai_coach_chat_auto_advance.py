from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from common.db.typing import orm_scalar
from sales_trainer.ai_coach_chat_models import SalesTrainerAiCoachChatMessage
from sales_trainer.ai_coach_chat_schemas import (
    AiCoachChatCommandV1,
    AiCoachChatResponseInternalV1,
    AiCoachChatUiEventInternalV1,
    AiCoachFollowupPromptPayloadV1,
    AiCoachQuizCardPayloadInternalV1,
    AiCoachSummaryCardPayloadV1,
)
from sales_trainer.models import SalesTrainerAiCoachSession
from sales_trainer.schemas import (
    AiCoachAnswerPayloadV1,
    AiCoachConfig,
    AiCoachInteractionInternalV1,
    AiCoachNextActionV1,
    AiCoachScoreResultV1,
)
from sales_trainer.services.ai_coach_chat_action_store import AiCoachChatActionStore
from sales_trainer.services.ai_coach_chat_coach_state import (
    AiCoachCoachStateV1,
    coach_state_from_snapshot,
    update_state_after_action,
    update_state_after_score,
)
from sales_trainer.services.ai_coach_chat_errors import (
    AI_COACH_STREAM_TIMEOUT_CODE,
    AiCoachChatGenerationError,
)
from sales_trainer.services.ai_coach_chat_event_writer import AiCoachChatEventWriter
from sales_trainer.services.ai_coach_chat_generation import AiCoachChatGenerator
from sales_trainer.services.ai_coach_chat_generation_streaming import (
    AiCoachGenerationDeltaHandler,
)
from sales_trainer.services.ai_coach_chat_next_action import AiCoachNextActionDecider
from sales_trainer.services.ai_coach_chat_next_action_generation import (
    AiCoachChatNextActionGenerator,
)
from sales_trainer.services.ai_coach_chat_store import AiCoachChatStore
from sales_trainer.services.operation_log_service import OperationLogService


class AiCoachChatAutoAdvance:
    def __init__(
        self,
        db: AsyncSession,
        store: AiCoachChatStore,
        events: AiCoachChatEventWriter,
        logs: OperationLogService,
    ) -> None:
        self._db = db
        self._store = store
        self._events = events
        self._logs = logs
        self._actions = AiCoachChatActionStore()
        self._decider = AiCoachNextActionDecider()

    async def start_session_if_configured(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        actor: User | None,
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> None:
        state = coach_state_from_snapshot(session.coach_state)
        state = state.model_copy(
            update={
                "can_auto_advance": config.proactive_coaching_enabled
                and config.auto_advance_enabled,
            }
        )
        setattr(session, "coach_state", state.model_dump(mode="json"))
        if not config.proactive_coaching_enabled:
            await self._db.commit()
            return
        match config.session_start_behavior:
            case "welcome_only":
                await self._db.commit()
                return
            case "plan_then_wait":
                response = self._plan_then_wait_response()
                action: AiCoachNextActionV1 = "ask_user_choice"
                reason = "session_start_behavior=plan_then_wait"
            case "plan_and_first_card":
                action = "continue_drill"
                reason = "session_start_behavior=plan_and_first_card"
                try:
                    response = await AiCoachChatGenerator(self._db).generate(
                        session=session,
                        config=config,
                        user_message=(
                            "请主动发起一轮教练主导训练局，输出简短训练计划，"
                            "并生成 1 张热身 quiz_card。"
                        ),
                        history=await self._store.messages(
                            orm_scalar(session.session_id, str)
                        ),
                        on_generation_delta=on_generation_delta,
                    )
                    AiCoachChatNextActionGenerator._validate_response_for_action(
                        response,
                        action,
                    )
                except AiCoachChatGenerationError as exc:
                    failed_state = state.model_copy(
                        update={
                            "can_auto_advance": False,
                            "stopped_reason": exc.code,
                        }
                    )
                    await self._append_response(
                        session=session,
                        response=self._fallback_response(
                            exc.code,
                            config,
                            session=session,
                            action=action,
                        ),
                        action=action,
                        reason=reason,
                        trigger_type="session_start",
                        trigger_event_id=None,
                        state_before=state,
                        state_after=failed_state,
                        actor=actor,
                        status="failed",
                        error_code=exc.code,
                    )
                    return
        next_state = update_state_after_action(
            state,
            action=action,
            can_auto_advance=config.auto_advance_enabled,
        )
        await self._append_response(
            session=session,
            response=response,
            action=action,
            reason=reason,
            trigger_type="session_start",
            trigger_event_id=None,
            state_before=state,
            state_after=next_state,
            actor=actor,
        )

    async def advance_after_answer(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        event_payload: dict[str, object],
        event_id: str,
        score_result: AiCoachScoreResultV1,
        answer_payload: AiCoachAnswerPayloadV1,
        actor: User | None,
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> None:
        state_before = coach_state_from_snapshot(session.coach_state)
        scored_state = update_state_after_score(
            state_before,
            score_result=score_result,
            mastery_threshold=config.mastery_threshold,
        )
        decision = self._decider.decide_after_score(
            config=config,
            state=scored_state,
            score_result=score_result,
        )
        if not decision.should_generate:
            setattr(session, "coach_state", scored_state.model_dump(mode="json"))
            self._db.add(
                self._actions.add_action(
                    session,
                    trigger_type="event_answer",
                    trigger_event_id=event_id,
                    action=decision.action,
                    reason=decision.reason,
                    status="skipped",
                    state_before=state_before,
                    state_after=scored_state,
                    error_code=decision.stopped_reason,
                )
            )
            await self._db.commit()
            return
        next_state = update_state_after_action(
            scored_state,
            action=decision.action,
            can_auto_advance=config.auto_advance_enabled,
            stopped_reason=decision.stopped_reason,
        )
        try:
            response = await AiCoachChatNextActionGenerator(self._db).generate(
                session=session,
                config=config,
                decision=decision,
                state=scored_state,
                score_result=score_result,
                answer_payload=answer_payload,
                answered_event_payload=event_payload,
                history=await self._store.messages(orm_scalar(session.session_id, str)),
                on_generation_delta=on_generation_delta,
            )
        except AiCoachChatGenerationError as exc:
            failed_state = scored_state.model_copy(
                update={
                    "can_auto_advance": False,
                    "stopped_reason": exc.code,
                }
            )
            if config.failure_behavior == "abort":
                await self._record_failed_action(
                    session=session,
                    action=decision.action,
                    reason=decision.reason,
                    trigger_event_id=event_id,
                    state_before=state_before,
                    state_after=failed_state,
                    error_code=exc.code,
                    actor=actor,
                )
                raise
            response = self._fallback_response(
                exc.code,
                config,
                session=session,
                action=decision.action,
                answered_event_payload=event_payload,
            )
            await self._append_response(
                session=session,
                response=response,
                action=decision.action,
                reason=decision.reason,
                trigger_type="event_answer",
                trigger_event_id=event_id,
                state_before=state_before,
                state_after=failed_state,
                actor=actor,
                status="failed",
                error_code=exc.code,
            )
            return
        await self._append_response(
            session=session,
            response=response,
            action=decision.action,
            reason=decision.reason,
            trigger_type="event_answer",
            trigger_event_id=event_id,
            state_before=state_before,
            state_after=next_state,
            actor=actor,
        )

    async def advance_for_command(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        command: AiCoachChatCommandV1,
        event_id: str | None,
        actor: User | None,
        on_generation_delta: AiCoachGenerationDeltaHandler | None = None,
    ) -> None:
        state_before = coach_state_from_snapshot(session.coach_state)
        action = self._action_for_command(config, command)
        next_state = update_state_after_action(
            state_before,
            action=action,
            can_auto_advance=config.auto_advance_enabled,
            stopped_reason=None,
        )
        reason = f"学员显式选择训练动作：{command}"
        if action in {"summarize", "end_session"}:
            await self._append_response(
                session=session,
                response=self._summary_response(state_before, action),
                action=action,
                reason=reason,
                trigger_type="user_message",
                trigger_event_id=event_id,
                state_before=state_before,
                state_after=next_state,
                actor=actor,
            )
            return
        try:
            response = await AiCoachChatGenerator(self._db).generate(
                session=session,
                config=config,
                user_message=self._command_instruction(action),
                history=await self._store.messages(orm_scalar(session.session_id, str)),
                on_generation_delta=on_generation_delta,
            )
            AiCoachChatNextActionGenerator._validate_response_for_action(
                response,
                action,
            )
        except AiCoachChatGenerationError as exc:
            failed_state = state_before.model_copy(
                update={
                    "can_auto_advance": False,
                    "stopped_reason": exc.code,
                }
            )
            if config.failure_behavior == "abort":
                await self._record_failed_command(
                    session=session,
                    action=action,
                    reason=reason,
                    trigger_event_id=event_id,
                    state_before=state_before,
                    state_after=failed_state,
                    error_code=exc.code,
                    actor=actor,
                )
                raise
            response = self._fallback_response(
                exc.code,
                config,
                session=session,
                action=action,
            )
            await self._append_response(
                session=session,
                response=response,
                action=action,
                reason=reason,
                trigger_type="user_message",
                trigger_event_id=event_id,
                state_before=state_before,
                state_after=failed_state,
                actor=actor,
                status="failed",
                error_code=exc.code,
            )
            return
        await self._append_response(
            session=session,
            response=response,
            action=action,
            reason=reason,
            trigger_type="user_message",
            trigger_event_id=event_id,
            state_before=state_before,
            state_after=next_state,
            actor=actor,
        )

    async def record_timeout_after_answer(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        config: AiCoachConfig,
        event_id: str,
        score_result: AiCoachScoreResultV1,
        actor: User | None,
    ) -> None:
        state_before = coach_state_from_snapshot(session.coach_state)
        scored_state = update_state_after_score(
            state_before,
            score_result=score_result,
            mastery_threshold=config.mastery_threshold,
        )
        decision = self._decider.decide_after_score(
            config=config,
            state=scored_state,
            score_result=score_result,
        )
        failed_state = scored_state.model_copy(
            update={
                "can_auto_advance": False,
                "stopped_reason": AI_COACH_STREAM_TIMEOUT_CODE,
            }
        )
        await self._append_response(
            session=session,
            response=self._fallback_response(
                AI_COACH_STREAM_TIMEOUT_CODE,
                config,
                session=session,
                action=decision.action,
            ),
            action=decision.action,
            reason=f"{decision.reason}; generation timed out",
            trigger_type="event_answer",
            trigger_event_id=event_id,
            state_before=state_before,
            state_after=failed_state,
            actor=actor,
            status="failed",
            error_code=AI_COACH_STREAM_TIMEOUT_CODE,
        )

    async def _append_response(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        response: AiCoachChatResponseInternalV1,
        action: AiCoachNextActionV1,
        reason: str,
        trigger_type: str,
        trigger_event_id: str | None,
        state_before: AiCoachCoachStateV1,
        state_after: AiCoachCoachStateV1,
        actor: User | None,
        status: str = "generated",
        error_code: str | None = None,
    ) -> None:
        session_id = orm_scalar(session.session_id, str)
        order = await self._store.next_message_order(session_id)
        assistant = SalesTrainerAiCoachChatMessage(
            session_id=session_id,
            role="assistant",
            content=response.assistant_text,
            order_index=order,
        )
        self._db.add(assistant)
        await self._db.flush()
        await self._events.persist_ui_events(session, assistant, response.ui_events)
        setattr(session, "coach_state", state_after.model_dump(mode="json"))
        if action == "end_session":
            setattr(session, "status", "completed")
        self._db.add(
            self._actions.add_action(
                session,
                trigger_type=trigger_type,
                trigger_event_id=trigger_event_id,
                action=action,
                reason=reason,
                status=status,
                state_before=state_before,
                state_after=state_after,
                assistant_message_id=orm_scalar(assistant.message_id, str),
                error_code=error_code,
            )
        )
        await self._logs.record(
            actor=actor,
            action=(
                "ai_coach_chat_next_action_failed_v1"
                if status == "failed"
                else "ai_coach_chat_next_action_generated_v1"
            ),
            target_type="sales_trainer_ai_coach_session",
            target_id=session_id,
            metadata={
                "next_action": action,
                "trigger_type": trigger_type,
                "error_code": error_code,
                "llm_runtime": dict(response.runtime_audit or {}),
            },
        )
        await self._db.commit()

    async def _record_failed_action(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        action: AiCoachNextActionV1,
        reason: str,
        trigger_event_id: str,
        state_before: AiCoachCoachStateV1,
        state_after: AiCoachCoachStateV1,
        error_code: str,
        actor: User | None,
    ) -> None:
        setattr(session, "coach_state", state_after.model_dump(mode="json"))
        self._db.add(
            self._actions.add_action(
                session,
                trigger_type="event_answer",
                trigger_event_id=trigger_event_id,
                action=action,
                reason=reason,
                status="failed",
                state_before=state_before,
                state_after=state_after,
                error_code=error_code,
            )
        )
        await self._logs.record(
            actor=actor,
            action="ai_coach_chat_next_action_failed_v1",
            target_type="sales_trainer_ai_coach_session",
            target_id=orm_scalar(session.session_id, str),
            metadata={
                "next_action": action,
                "trigger_type": "event_answer",
                "error_code": error_code,
            },
        )
        await self._db.commit()

    async def _record_failed_command(
        self,
        *,
        session: SalesTrainerAiCoachSession,
        action: AiCoachNextActionV1,
        reason: str,
        trigger_event_id: str | None,
        state_before: AiCoachCoachStateV1,
        state_after: AiCoachCoachStateV1,
        error_code: str,
        actor: User | None,
    ) -> None:
        setattr(session, "coach_state", state_after.model_dump(mode="json"))
        self._db.add(
            self._actions.add_action(
                session,
                trigger_type="user_message",
                trigger_event_id=trigger_event_id,
                action=action,
                reason=reason,
                status="failed",
                state_before=state_before,
                state_after=state_after,
                error_code=error_code,
            )
        )
        await self._logs.record(
            actor=actor,
            action="ai_coach_chat_next_action_failed_v1",
            target_type="sales_trainer_ai_coach_session",
            target_id=orm_scalar(session.session_id, str),
            metadata={
                "next_action": action,
                "trigger_type": "user_message",
                "error_code": error_code,
            },
        )
        await self._db.commit()

    @staticmethod
    def _action_for_command(
        config: AiCoachConfig,
        command: AiCoachChatCommandV1,
    ) -> AiCoachNextActionV1:
        desired: AiCoachNextActionV1
        match command:
            case "continue" | "retry":
                desired = "continue_drill"
            case "explain":
                desired = "remediate"
            case "switch_scenario":
                desired = "switch_scenario"
            case "summarize":
                desired = "summarize"
            case "end":
                desired = "end_session"
        if desired in config.allowed_next_actions:
            return desired
        for fallback in ("ask_user_choice", "summarize", "end_session"):
            if fallback in config.allowed_next_actions:
                return fallback
        return config.allowed_next_actions[0]

    @staticmethod
    def _command_instruction(action: AiCoachNextActionV1) -> str:
        return (
            "后端已经确定本次教练动作。请不要询问学员要不要开始，"
            f"只执行 next_action={action}，并严格满足该动作的 UI event 数量约束。"
        )

    @staticmethod
    def _plan_then_wait_response() -> AiCoachChatResponseInternalV1:
        return AiCoachChatResponseInternalV1(
            assistant_text="我会带你做一轮商务技巧训练。你可以先选择训练方向，也可以直接说想练什么。",
            ui_events=[
                AiCoachChatUiEventInternalV1(
                    type="followup_prompt",
                    payload=AiCoachFollowupPromptPayloadV1(
                        prompts=["开始客户异议处理", "开始商务礼仪", "先讲知识点"],
                    ),
                )
            ],
        )

    @staticmethod
    def _fallback_response(
        _error_code: str,
        config: AiCoachConfig,
        *,
        session: SalesTrainerAiCoachSession | None = None,
        action: AiCoachNextActionV1 | None = None,
        answered_event_payload: dict[str, object] | None = None,
    ) -> AiCoachChatResponseInternalV1:
        fallback_card = AiCoachChatAutoAdvance._fallback_quiz_card_event(
            config=config,
            session=session,
            action=action,
            answered_event_payload=answered_event_payload,
        )
        if fallback_card is not None:
            return AiCoachChatResponseInternalV1(
                assistant_text=(
                    "训练进度已保存。我先给你一张基础补练卡，完成后继续按当前小单元判断掌握情况。"
                ),
                ui_events=[
                    fallback_card,
                    AiCoachChatUiEventInternalV1(
                        type="followup_prompt",
                        payload=AiCoachFollowupPromptPayloadV1(
                            prompts=["先做这张基础卡", "讲解一下", "总结本轮"],
                        ),
                    ),
                ],
                runtime_audit={"fallback_source": "deterministic_training_card"},
            )
        return AiCoachChatResponseInternalV1(
            assistant_text=config.generation_failure_recovery_message,
            ui_events=[
                AiCoachChatUiEventInternalV1(
                    type="followup_prompt",
                    payload=AiCoachFollowupPromptPayloadV1(
                        prompts=list(config.generation_failure_recovery_prompts),
                    ),
                )
            ],
        )

    @staticmethod
    def _fallback_quiz_card_event(
        *,
        config: AiCoachConfig,
        session: SalesTrainerAiCoachSession | None,
        action: AiCoachNextActionV1 | None,
        answered_event_payload: dict[str, object] | None,
    ) -> AiCoachChatUiEventInternalV1 | None:
        if action not in {
            "continue_drill",
            "increase_difficulty",
            "remediate",
            "switch_scenario",
        }:
            return None
        if "quiz_card" not in config.allowed_ui_event_types:
            return None
        if "scenario_judgment" not in config.allowed_training_card_types:
            return None
        title, capability_keys, chapter_orders = (
            AiCoachChatAutoAdvance._fallback_training_context(
                session=session,
                answered_event_payload=answered_event_payload,
            )
        )
        interaction = AiCoachInteractionInternalV1.model_validate(
            {
                "schema_version": "ai_coach_interaction_v1",
                "training_card_type": "scenario_judgment",
                "interaction_type": "single_choice",
                "stem": (
                    f"{title}：客户第一次到访前，你最应该先做哪一步，"
                    "才能显得专业且尊重对方？"
                ),
                "options": [
                    {
                        "option_id": "A",
                        "text": "先确认对方到访目的、时间、人数和接待安排",
                    },
                    {
                        "option_id": "B",
                        "text": "先完整介绍产品卖点，让对方快速了解公司",
                    },
                ],
                "answer_key": {"option_ids": ["A"], "reference_answer": None},
                "scoring_rubric": {
                    "max_score": 100,
                    "points": [
                        {
                            "key": "visit-preparation",
                            "score": 100,
                            "description": "能先确认接待条件和对方需求。",
                        }
                    ],
                    "partial_credit_policy": "all_or_nothing",
                },
                "feedback_guidance": {
                    "correct": "处理得当。先确认到访目的、时间、人数和接待安排，能降低接待失误。",
                    "incorrect": "这一步容易显得只顾介绍自己。先确认到访安排，再进入产品或方案介绍。",
                },
                "capability_keys": capability_keys,
                "source_chapter_orders": chapter_orders,
                "source_evidence": [
                    {
                        "reason": "AI 生成失败后的确定性基础补练卡。",
                        "confidence": 1.0,
                    }
                ],
            }
        )
        return AiCoachChatUiEventInternalV1(
            type="quiz_card",
            payload=AiCoachQuizCardPayloadInternalV1(
                interaction=interaction,
                explanation="先用一张基础场景题保持训练不中断。",
            ),
        )

    @staticmethod
    def _fallback_training_context(
        *,
        session: SalesTrainerAiCoachSession | None,
        answered_event_payload: dict[str, object] | None,
    ) -> tuple[str, list[str], list[int]]:
        title = "商务礼仪基础练习"
        capability_keys: list[str] = []
        chapter_orders: list[int] = []

        interaction = (
            answered_event_payload.get("interaction_snapshot")
            if answered_event_payload
            else None
        )
        if isinstance(interaction, dict):
            capability_keys = _string_list(interaction.get("capability_keys"))
            chapter_orders = _positive_int_list(
                interaction.get("source_chapter_orders")
            )

        raw_path_config = (
            getattr(session, "path_config_snapshot", None)
            if session is not None
            else None
        )
        path_config = raw_path_config if isinstance(raw_path_config, dict) else {}
        units = path_config.get("learning_units")
        if isinstance(units, list):
            first_enabled = _first_enabled_unit(units)
            if first_enabled:
                title = str(first_enabled.get("title") or title)
                if not capability_keys:
                    capability_keys = _string_list(
                        first_enabled.get("ai_coach_required_capability_keys")
                    ) or _string_list(first_enabled.get("capability_keys"))
                if not chapter_orders:
                    chapter_orders = _positive_int_list(
                        first_enabled.get("ai_coach_remediation_chapter_orders")
                    ) or _positive_int_list(first_enabled.get("source_chapter_orders"))
        return title, capability_keys[:10], chapter_orders[:20]

    @staticmethod
    def _summary_response(
        state: AiCoachCoachStateV1,
        action: AiCoachNextActionV1,
    ) -> AiCoachChatResponseInternalV1:
        answered = state.answered_card_count
        average = round(state.average_score, 1) if state.score_count > 0 else None
        title = "本轮训练总结" if action == "summarize" else "训练已结束"
        items = [
            f"本轮已完成 {answered} 道训练题。",
            (
                f"当前平均得分 {average} 分。"
                if average is not None
                else "当前还没有可计算的答题得分。"
            ),
            "下一次训练可以继续围绕商务技巧情境做短轮练习。",
        ]
        mastered = average is not None and average >= 80
        return AiCoachChatResponseInternalV1(
            assistant_text="这是本轮训练的阶段复盘。",
            ui_events=[
                AiCoachChatUiEventInternalV1(
                    type="summary_card",
                    payload=AiCoachSummaryCardPayloadV1(
                        title=title,
                        items=items,
                        score_percent=average,
                        mastered=mastered if average is not None else None,
                        strengths=["能完成当前训练步骤"] if answered > 0 else [],
                        weaknesses=[],
                        next_steps=["继续完成 2-3 道相邻场景题，巩固商务礼仪判断。"],
                    ),
                )
            ],
        )


def _first_enabled_unit(units: list[object]) -> dict[str, object] | None:
    dict_units = [unit for unit in units if isinstance(unit, dict)]
    for unit in dict_units:
        if unit.get("enabled") is not False:
            return unit
    return dict_units[0] if dict_units else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _positive_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            result.append(parsed)
    return result
