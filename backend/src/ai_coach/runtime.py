"""Command-driven learner runtime for the structured Coach activity."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Never

from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import (
    CoachContextSnapshot,
    CoachProfileSnapshot,
    RequestCoachAssistanceInput,
    SubmitCoachAnswerInput,
)
from ai_coach.errors import AICoachError
from ai_coach.models import (
    CoachAssistance,
    CoachCardResponse,
    CoachCommandAudit,
    CoachOutcome,
    CoachProfileRevision,
    CoachRemediationCycle,
    CoachSession,
    CoachTrainingCard,
    CoachTurn,
)
from ai_coach.pipeline import deterministic_evaluation, finalize_response
from ai_coach.ports import (
    CoachActivityOutcomePayload,
    CoachActivityOutcomeWriterPort,
    CoachContextBuilderPort,
)
from ai_coach.task_types import (
    COACH_ANSWER_EVALUATION_TASK_TYPE,
    COACH_ASSISTANCE_TASK_TYPE,
    COACH_CARD_GENERATION_TASK_TYPE,
)
from task_runtime.contracts import ActorContext, TaskCommand, TaskRuntimePort


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class CoachStartContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    organization_id: str
    learner_id: str
    enrollment_id: str
    path_revision_id: str
    activity_id: str
    attempt_id: str
    profile_revision_id: str
    competency_keys: tuple[str, ...]
    trace_id: str | None = None


class CoachRuntimeProjection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str | None
    status: str
    version: int
    task_id: str | None
    runner: dict[str, Any]
    available_commands: tuple[str, ...]


class StructuredCoachRuntime:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tasks: TaskRuntimePort,
        context_builder: CoachContextBuilderPort,
        outcomes: CoachActivityOutcomeWriterPort,
    ) -> None:
        self._session = session
        self._tasks = tasks
        self._context_builder = context_builder
        self._outcomes = outcomes

    async def workspace(
        self,
        *,
        organization_id: str,
        learner_id: str,
        profile_revision_id: str,
        attempt_id: str | None,
    ) -> CoachRuntimeProjection:
        if attempt_id is None:
            profile_row = await self._published_profile(
                organization_id=organization_id,
                revision_id=profile_revision_id,
            )
            profile = CoachProfileSnapshot.model_validate(profile_row.snapshot_json)
            return CoachRuntimeProjection(
                session_id=None,
                status="not_started",
                version=0,
                task_id=None,
                runner={
                    "kind": "ai_coach",
                    "profile_title": profile.title,
                    "checkpoint": {
                        "current": 0,
                        "total": len(profile.checkpoints),
                        "title": "尚未开始",
                    },
                    "progress": {"completed_cards": 0, "total_cards": 0},
                    "source_context": [],
                    "weaknesses": [],
                    "current_card": None,
                    "last_feedback": None,
                    "assistance": None,
                    "mastery": {
                        "threshold_percent": profile.mastery_rule.threshold_percent,
                        "cycle": 0,
                        "maximum_automatic_cycles": (
                            profile.remediation_policy.maximum_automatic_cycles
                        ),
                    },
                    "failure": None,
                    "human_help": None,
                },
                available_commands=("start",),
            )
        coach_session = await self._session.scalar(
            select(CoachSession)
            .where(CoachSession.organization_id == organization_id)
            .where(CoachSession.learner_id == learner_id)
            .where(CoachSession.attempt_id == attempt_id)
            .limit(1)
        )
        if coach_session is None:
            raise AICoachError(
                "[COACH_SESSION_NOT_FOUND]",
                "当前训练会话不存在，请重新进入活动。",
                404,
            )
        if coach_session.profile_revision_id != profile_revision_id:
            raise AICoachError(
                "[COACH_PROFILE_MISMATCH]",
                "当前训练记录与路径冻结的教练配置不一致。",
                409,
            )
        return await self._projection(coach_session)

    async def start_or_resume(
        self,
        *,
        context: CoachStartContext,
        idempotency_key: str,
    ) -> CoachRuntimeProjection:
        request = context.model_dump(mode="json")
        fingerprint = _canonical_hash(request)
        existing = await self._session.scalar(
            select(CoachSession)
            .where(CoachSession.attempt_id == context.attempt_id)
            .limit(1)
        )
        if existing is not None:
            if (
                existing.organization_id != context.organization_id
                or existing.learner_id != context.learner_id
            ):
                self._not_found()
            if (
                existing.idempotency_key_hash != _secret_hash(idempotency_key)
                or existing.command_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            return await self._projection(existing)
        profile_row = await self._published_profile(
            organization_id=context.organization_id,
            revision_id=context.profile_revision_id,
        )
        profile = CoachProfileSnapshot.model_validate(profile_row.snapshot_json)
        if not set(context.competency_keys).issubset(
            set(profile.applicable_competency_keys)
        ):
            raise AICoachError(
                "[COACH_PROFILE_COMPETENCY_MISMATCH]",
                "当前活动能力范围与已发布教练配置不一致。",
                422,
            )
        snapshot = await self._context_builder.build(
            organization_id=context.organization_id,
            learner_id=context.learner_id,
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity_id,
            profile_revision_id=context.profile_revision_id,
            profile=profile,
        )
        if not snapshot.references:
            raise AICoachError(
                "[COACH_CONTEXT_UNAVAILABLE]",
                "当前训练缺少可验证的学习依据，请联系培训负责人。",
                409,
            )
        coach_session = CoachSession(
            session_id=_id(),
            organization_id=context.organization_id,
            learner_id=context.learner_id,
            enrollment_id=context.enrollment_id,
            path_revision_id=context.path_revision_id,
            activity_id=context.activity_id,
            attempt_id=context.attempt_id,
            profile_revision_id=context.profile_revision_id,
            profile_snapshot_json=profile.model_dump(mode="json"),
            context_snapshot_json=snapshot.model_dump(mode="json"),
            competency_keys_json=list(context.competency_keys),
            status="created",
            checkpoint_index=0,
            cycle_no=0,
            active_cycle_id=None,
            active_task_id=None,
            failure_stage=None,
            error_code=None,
            safe_error_message=None,
            human_help_status=None,
            human_help_next_action_json=None,
            idempotency_key_hash=_secret_hash(idempotency_key),
            command_fingerprint=fingerprint,
            version=1,
            created_at=_now(),
            updated_at=_now(),
        )
        self._session.add(coach_session)
        await self._session.flush([coach_session])
        await self._create_generation_cycle(
            coach_session,
            reason="开始第一个训练检查点",
            remediation_inputs=(),
            idempotency_key=f"{idempotency_key}:checkpoint:0:cycle:0",
            trace_id=context.trace_id,
        )
        return await self._projection(coach_session)

    async def submit_answer(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        payload: SubmitCoachAnswerInput,
        expected_version: int,
        idempotency_key: str,
        trace_id: str | None,
    ) -> CoachRuntimeProjection:
        coach_session = await self._load_session(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        answer_payload = payload.answer.model_dump(mode="json")
        answer_hash = _canonical_hash(
            {"card_id": payload.card_id, "answer": answer_payload}
        )
        token_hash = _secret_hash(payload.client_token)
        replay = await self._session.scalar(
            select(CoachCardResponse)
            .where(CoachCardResponse.session_id == coach_session.session_id)
            .where(CoachCardResponse.client_token_hash == token_hash)
            .limit(1)
        )
        if replay is not None:
            if replay.answer_hash != answer_hash:
                self._idempotency_conflict()
            return await self._projection(coach_session)
        self._require_version(coach_session, expected_version)
        if coach_session.status != "awaiting_answer":
            raise AICoachError(
                "[COACH_SESSION_STATE_CONFLICT]",
                "当前训练卡尚不能提交答案，请刷新后重试。",
                409,
            )
        card = await self._session.scalar(
            select(CoachTrainingCard)
            .where(CoachTrainingCard.card_id == payload.card_id)
            .where(CoachTrainingCard.session_id == coach_session.session_id)
            .with_for_update()
            .limit(1)
        )
        if card is None or card.status != "current":
            raise AICoachError(
                "[COACH_CARD_NOT_CURRENT]",
                "该训练卡已不是当前任务，请刷新后继续。",
                409,
            )
        self._validate_answer(card, answer_payload)
        turn = await self._session.get(CoachTurn, card.turn_id)
        if turn is None or turn.status != "current":
            raise AICoachError(
                "[COACH_TURN_STATE_CONFLICT]",
                "当前训练轮次状态已更新，请刷新后继续。",
                409,
            )
        response = CoachCardResponse(
            response_id=_id(),
            session_id=coach_session.session_id,
            card_id=card.card_id,
            turn_id=turn.turn_id,
            organization_id=organization_id,
            learner_id=learner_id,
            raw_answer_json=answer_payload,
            client_token_hash=token_hash,
            answer_hash=answer_hash,
            status="saved",
            evaluation_task_id=None,
            source_ref_ids_json=[],
            submitted_at=_now(),
        )
        card.status = "answered"
        card.updated_at = _now()
        turn.status = "answered"
        turn.updated_at = _now()
        self._session.add(response)
        # This flush is the save-before-AI boundary. The task row is created only
        # after the immutable raw response is accepted by the database transaction.
        await self._session.flush([response, card, turn])
        if card.evaluation_mode == "deterministic":
            score, evaluation = deterministic_evaluation(
                card=card,
                answer=answer_payload,
            )
            await finalize_response(
                self._session,
                response=response,
                coach_session=coach_session,
                score_percent=score,
                uncertainty=0,
                source_ref_ids=list(card.source_ref_ids_json),
                evaluation=evaluation,
                evaluation_kind="deterministic",
            )
        else:
            task = await self._tasks.enqueue(
                TaskCommand(
                    task_type=COACH_ANSWER_EVALUATION_TASK_TYPE,
                    schema_version=1,
                    organization_id=organization_id,
                    actor_id=learner_id,
                    resource_type="coach_card_response",
                    resource_id=response.response_id,
                    idempotency_key=f"{idempotency_key}:evaluate",
                    input_payload={"response_id": response.response_id},
                    correlation_id=coach_session.session_id,
                    causation_id=card.card_id,
                    trace_id=trace_id,
                    data_classification="confidential",
                )
            )
            response.status = "evaluating"
            response.evaluation_task_id = task.task_id
            coach_session.status = "evaluating"
            coach_session.active_task_id = task.task_id
            coach_session.version += 1
            coach_session.updated_at = _now()
            await self._session.flush([response, coach_session])
        return await self._projection(coach_session)

    async def continue_training(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        idempotency_key: str,
        trace_id: str | None,
    ) -> CoachRuntimeProjection:
        coach_session = await self._load_session(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if await self._replayed_command(
            coach_session, "continue_coach", idempotency_key
        ):
            return await self._projection(coach_session)
        self._require_version(coach_session, expected_version)
        before_version = coach_session.version
        if coach_session.status == "feedback_ready":
            card = await self._session.scalar(
                select(CoachTrainingCard)
                .join(CoachTurn, CoachTurn.turn_id == CoachTrainingCard.turn_id)
                .where(CoachTrainingCard.cycle_id == coach_session.active_cycle_id)
                .where(CoachTrainingCard.status == "pending")
                .order_by(CoachTurn.cycle_position)
                .with_for_update()
                .limit(1)
            )
            if card is None:
                raise AICoachError(
                    "[COACH_NEXT_CARD_NOT_FOUND]",
                    "下一张训练卡不存在，请刷新后重试。",
                    409,
                )
            turn = await self._session.get(CoachTurn, card.turn_id)
            assert turn is not None
            card.status = "current"
            card.updated_at = _now()
            turn.status = "current"
            turn.updated_at = _now()
            coach_session.status = "awaiting_answer"
            coach_session.version += 1
            coach_session.updated_at = _now()
            await self._session.flush([card, turn, coach_session])
        elif coach_session.status == "checkpoint_mastered":
            if coach_session.checkpoint_index == 2:
                await self._complete_session(coach_session, trace_id=trace_id)
            else:
                coach_session.checkpoint_index += 1
                coach_session.cycle_no = 0
                await self._create_generation_cycle(
                    coach_session,
                    reason="进入下一个训练检查点",
                    remediation_inputs=(),
                    idempotency_key=(
                        f"{idempotency_key}:checkpoint:"
                        f"{coach_session.checkpoint_index}:cycle:0"
                    ),
                    trace_id=trace_id,
                )
        elif coach_session.status == "remediation_required":
            profile = CoachProfileSnapshot.model_validate(
                coach_session.profile_snapshot_json
            )
            next_cycle = coach_session.cycle_no + 1
            if next_cycle > profile.remediation_policy.maximum_automatic_cycles:
                coach_session.status = "needs_human_help"
                coach_session.human_help_status = "open"
                coach_session.human_help_next_action_json = None
                coach_session.active_task_id = None
                coach_session.version += 1
                coach_session.updated_at = _now()
                await self._session.flush([coach_session])
            else:
                current_cycle = await self._session.get(
                    CoachRemediationCycle, coach_session.active_cycle_id
                )
                missing_points = tuple(
                    str(item)
                    for item in (
                        (current_cycle.result_summary_json or {}).get(
                            "missing_points", []
                        )
                        if current_cycle is not None
                        else []
                    )
                )
                coach_session.cycle_no = next_cycle
                await self._create_generation_cycle(
                    coach_session,
                    reason="根据本轮缺失点开始针对性补练",
                    remediation_inputs=missing_points,
                    idempotency_key=(
                        f"{idempotency_key}:checkpoint:"
                        f"{coach_session.checkpoint_index}:cycle:{next_cycle}"
                    ),
                    trace_id=trace_id,
                )
        else:
            raise AICoachError(
                "[COACH_SESSION_STATE_CONFLICT]",
                "当前训练状态没有可继续的下一步。",
                409,
            )
        await self._record_command(
            coach_session,
            command="continue_coach",
            idempotency_key=idempotency_key,
            before_version=before_version,
            trace_id=trace_id,
        )
        return await self._projection(coach_session)

    async def retry_failed(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        idempotency_key: str,
        trace_id: str | None,
    ) -> CoachRuntimeProjection:
        coach_session = await self._load_session(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if await self._replayed_command(coach_session, "retry_coach", idempotency_key):
            return await self._projection(coach_session)
        self._require_version(coach_session, expected_version)
        if coach_session.status != "failed_recoverable":
            raise AICoachError(
                "[COACH_SESSION_STATE_CONFLICT]",
                "当前训练没有可重试的失败任务。",
                409,
            )
        before_version = coach_session.version
        if coach_session.failure_stage == "card_generation":
            cycle = await self._session.get(
                CoachRemediationCycle, coach_session.active_cycle_id
            )
            if cycle is None or cycle.status != "failed":
                raise AICoachError(
                    "[COACH_CYCLE_NOT_FOUND]", "可重试的训练轮次不存在。", 409
                )
            task = await self._tasks.enqueue(
                TaskCommand(
                    task_type=COACH_CARD_GENERATION_TASK_TYPE,
                    schema_version=1,
                    organization_id=organization_id,
                    actor_id=learner_id,
                    resource_type="coach_remediation_cycle",
                    resource_id=cycle.cycle_id,
                    idempotency_key=f"{idempotency_key}:generation",
                    input_payload={"cycle_id": cycle.cycle_id},
                    correlation_id=coach_session.session_id,
                    causation_id=cycle.cycle_id,
                    trace_id=trace_id,
                    data_classification="confidential",
                )
            )
            cycle.status = "generating"
            cycle.generation_task_id = task.task_id
            cycle.updated_at = _now()
            coach_session.status = "preparing"
            coach_session.active_task_id = task.task_id
            await self._session.flush([cycle])
        elif coach_session.failure_stage == "answer_evaluation":
            response = await self._session.scalar(
                select(CoachCardResponse)
                .where(CoachCardResponse.session_id == coach_session.session_id)
                .where(CoachCardResponse.status == "failed_recoverable")
                .order_by(desc(CoachCardResponse.submitted_at))
                .with_for_update()
                .limit(1)
            )
            if response is None:
                raise AICoachError(
                    "[COACH_RESPONSE_NOT_FOUND]", "可重试的训练回答不存在。", 409
                )
            task = await self._tasks.enqueue(
                TaskCommand(
                    task_type=COACH_ANSWER_EVALUATION_TASK_TYPE,
                    schema_version=1,
                    organization_id=organization_id,
                    actor_id=learner_id,
                    resource_type="coach_card_response",
                    resource_id=response.response_id,
                    idempotency_key=f"{idempotency_key}:evaluation",
                    input_payload={"response_id": response.response_id},
                    correlation_id=coach_session.session_id,
                    causation_id=response.card_id,
                    trace_id=trace_id,
                    data_classification="confidential",
                )
            )
            response.status = "evaluating"
            response.evaluation_task_id = task.task_id
            response.error_code = None
            response.safe_error_message = None
            coach_session.status = "evaluating"
            coach_session.active_task_id = task.task_id
            await self._session.flush([response])
        else:
            raise AICoachError(
                "[COACH_RETRY_STAGE_UNSUPPORTED]",
                "当前失败阶段不能自动重试，请联系培训负责人。",
                409,
            )
        coach_session.failure_stage = None
        coach_session.error_code = None
        coach_session.safe_error_message = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([coach_session])
        await self._record_command(
            coach_session,
            command="retry_coach",
            idempotency_key=idempotency_key,
            before_version=before_version,
            trace_id=trace_id,
        )
        return await self._projection(coach_session)

    async def request_assistance(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        payload: RequestCoachAssistanceInput,
        expected_version: int,
        idempotency_key: str,
        trace_id: str | None,
    ) -> CoachRuntimeProjection:
        coach_session = await self._load_session(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        self._require_version(coach_session, expected_version)
        if coach_session.status not in {
            "awaiting_answer",
            "feedback_ready",
            "checkpoint_mastered",
            "remediation_required",
        }:
            raise AICoachError(
                "[COACH_ASSISTANCE_STATE_CONFLICT]",
                "当前训练状态不能请求讲解。",
                409,
            )
        fingerprint = _canonical_hash(payload.model_dump(mode="json"))
        key_hash = _secret_hash(idempotency_key)
        replay = await self._session.scalar(
            select(CoachAssistance)
            .where(CoachAssistance.session_id == coach_session.session_id)
            .where(CoachAssistance.idempotency_key_hash == key_hash)
            .limit(1)
        )
        if replay is not None:
            if replay.request_fingerprint != fingerprint:
                self._idempotency_conflict()
            return await self._projection(coach_session)
        card = await self._session.scalar(
            select(CoachTrainingCard)
            .where(CoachTrainingCard.card_id == payload.card_id)
            .where(CoachTrainingCard.session_id == coach_session.session_id)
            .limit(1)
        )
        if card is None:
            self._not_found()
        assistance = CoachAssistance(
            assistance_id=_id(),
            session_id=coach_session.session_id,
            card_id=card.card_id,
            organization_id=organization_id,
            learner_id=learner_id,
            assistance_type=payload.assistance_type,
            status="queued",
            task_id=None,
            result_json=None,
            source_ref_ids_json=[],
            idempotency_key_hash=key_hash,
            request_fingerprint=fingerprint,
            created_at=_now(),
        )
        self._session.add(assistance)
        await self._session.flush([assistance])
        task = await self._tasks.enqueue(
            TaskCommand(
                task_type=COACH_ASSISTANCE_TASK_TYPE,
                schema_version=1,
                organization_id=organization_id,
                actor_id=learner_id,
                resource_type="coach_assistance",
                resource_id=assistance.assistance_id,
                idempotency_key=f"{idempotency_key}:assistance",
                input_payload={"assistance_id": assistance.assistance_id},
                correlation_id=coach_session.session_id,
                causation_id=card.card_id,
                trace_id=trace_id,
                data_classification="confidential",
            )
        )
        assistance.task_id = task.task_id
        await self._session.flush([assistance])
        return await self._projection(coach_session)

    async def cancel(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        expected_version: int,
        idempotency_key: str,
        trace_id: str | None,
    ) -> CoachRuntimeProjection:
        coach_session = await self._load_session(
            organization_id=organization_id,
            learner_id=learner_id,
            attempt_id=attempt_id,
            for_update=True,
        )
        if await self._replayed_command(coach_session, "cancel", idempotency_key):
            return await self._projection(coach_session)
        self._require_version(coach_session, expected_version)
        if coach_session.status == "completed":
            raise AICoachError(
                "[COACH_SESSION_STATE_CONFLICT]", "已完成的训练不能取消。", 409
            )
        before_version = coach_session.version
        if coach_session.active_task_id is not None:
            await self._tasks.request_cancel(
                coach_session.active_task_id,
                ActorContext(
                    organization_id=organization_id,
                    actor_id=learner_id,
                ),
                idempotency_key=f"{idempotency_key}:task",
            )
        coach_session.status = "cancelled"
        coach_session.active_task_id = None
        coach_session.failure_stage = None
        coach_session.cancelled_at = _now()
        coach_session.version += 1
        coach_session.updated_at = _now()
        cycles = (
            (
                await self._session.execute(
                    select(CoachRemediationCycle).where(
                        CoachRemediationCycle.session_id == coach_session.session_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for cycle in cycles:
            if cycle.status not in {"mastered", "completed"}:
                cycle.status = "cancelled"
                cycle.updated_at = _now()
        cards = (
            (
                await self._session.execute(
                    select(CoachTrainingCard).where(
                        CoachTrainingCard.session_id == coach_session.session_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for card in cards:
            if card.status not in {"scored"}:
                card.status = "cancelled"
                card.updated_at = _now()
        turns = (
            (
                await self._session.execute(
                    select(CoachTurn).where(
                        CoachTurn.session_id == coach_session.session_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for turn in turns:
            if turn.status not in {"scored"}:
                turn.status = "cancelled"
                turn.updated_at = _now()
        await self._session.flush([coach_session, *cycles, *cards, *turns])
        await self._outcomes.record(
            CoachActivityOutcomePayload(
                organization_id=organization_id,
                actor_id=learner_id,
                attempt_id=attempt_id,
                lifecycle_result="cancelled",
                assessment_result="not_applicable",
                result_type="coach_session",
                result_id=coach_session.session_id,
                score=None,
                max_score=None,
                passed=None,
                lineage={
                    "profile_revision_id": coach_session.profile_revision_id,
                    "session_id": coach_session.session_id,
                    "reason": "learner_cancelled",
                },
                next_action={"type": "restart_activity"},
                idempotency_key=f"coach-cancel:{coach_session.session_id}",
                trace_id=trace_id,
            )
        )
        await self._record_command(
            coach_session,
            command="cancel",
            idempotency_key=idempotency_key,
            before_version=before_version,
            trace_id=trace_id,
        )
        return await self._projection(coach_session)

    async def _create_generation_cycle(
        self,
        coach_session: CoachSession,
        *,
        reason: str,
        remediation_inputs: tuple[str, ...],
        idempotency_key: str,
        trace_id: str | None,
    ) -> CoachRemediationCycle:
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        checkpoint = profile.checkpoints[coach_session.checkpoint_index]
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        cycle = CoachRemediationCycle(
            cycle_id=_id(),
            session_id=coach_session.session_id,
            organization_id=coach_session.organization_id,
            checkpoint_index=coach_session.checkpoint_index,
            checkpoint_key=checkpoint.checkpoint_key,
            cycle_no=coach_session.cycle_no,
            status="generating",
            reason=reason,
            input_evidence_json=[
                {
                    "competency_key": item.competency_key,
                    "source_ref_ids": list(item.source_ref_ids),
                    "summary": item.summary,
                }
                for item in context.weaknesses
                if item.competency_key in checkpoint.competency_keys
            ],
            remediation_inputs_json=list(remediation_inputs),
            generation_strategy=None,
            generation_task_id=None,
            generation_invocation_id=None,
            result_summary_json=None,
            created_at=_now(),
            updated_at=_now(),
        )
        self._session.add(cycle)
        await self._session.flush([cycle])
        task = await self._tasks.enqueue(
            TaskCommand(
                task_type=COACH_CARD_GENERATION_TASK_TYPE,
                schema_version=1,
                organization_id=coach_session.organization_id,
                actor_id=coach_session.learner_id,
                resource_type="coach_remediation_cycle",
                resource_id=cycle.cycle_id,
                idempotency_key=idempotency_key,
                input_payload={"cycle_id": cycle.cycle_id},
                correlation_id=coach_session.session_id,
                causation_id=checkpoint.checkpoint_key,
                trace_id=trace_id,
                data_classification="confidential",
            )
        )
        cycle.generation_task_id = task.task_id
        coach_session.status = "preparing"
        coach_session.active_cycle_id = cycle.cycle_id
        coach_session.active_task_id = task.task_id
        coach_session.failure_stage = None
        coach_session.error_code = None
        coach_session.safe_error_message = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([cycle, coach_session])
        return cycle

    async def _complete_session(
        self,
        coach_session: CoachSession,
        *,
        trace_id: str | None,
    ) -> None:
        existing = await self._session.scalar(
            select(CoachOutcome)
            .where(CoachOutcome.session_id == coach_session.session_id)
            .limit(1)
        )
        if existing is not None:
            coach_session.status = "completed"
            coach_session.completed_at = coach_session.completed_at or _now()
            coach_session.version += 1
            coach_session.updated_at = _now()
            await self._session.flush([coach_session])
            return
        cycles = list(
            (
                await self._session.execute(
                    select(CoachRemediationCycle)
                    .where(CoachRemediationCycle.session_id == coach_session.session_id)
                    .order_by(
                        CoachRemediationCycle.checkpoint_index,
                        CoachRemediationCycle.cycle_no,
                    )
                )
            ).scalars()
        )
        mastered_by_checkpoint = {
            item.checkpoint_index: item for item in cycles if item.status == "mastered"
        }
        if set(mastered_by_checkpoint) != {0, 1, 2}:
            raise AICoachError(
                "[COACH_SESSION_INCOMPLETE]",
                "三个训练检查点尚未全部达标。",
                409,
            )
        responses = list(
            (
                await self._session.execute(
                    select(CoachCardResponse)
                    .where(CoachCardResponse.session_id == coach_session.session_id)
                    .where(CoachCardResponse.status == "evaluated")
                    .order_by(CoachCardResponse.submitted_at)
                )
            ).scalars()
        )
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        mastery_score = (
            sum(
                float(mastered_by_checkpoint[index].score_percent or 0)
                for index in range(3)
            )
            / 3
        )
        checkpoint_results = [
            {
                "checkpoint_key": profile.checkpoints[index].checkpoint_key,
                "title": profile.checkpoints[index].title,
                "mastery_score_percent": float(
                    mastered_by_checkpoint[index].score_percent or 0
                ),
                "final_cycle_no": mastered_by_checkpoint[index].cycle_no,
            }
            for index in range(3)
        ]
        cycle_history = [
            {
                "cycle_id": item.cycle_id,
                "checkpoint_key": item.checkpoint_key,
                "cycle_no": item.cycle_no,
                "status": item.status,
                "score_percent": (
                    float(item.score_percent)
                    if item.score_percent is not None
                    else None
                ),
                "maximum_uncertainty": (
                    float(item.maximum_uncertainty)
                    if item.maximum_uncertainty is not None
                    else None
                ),
                "generation_invocation_id": item.generation_invocation_id,
            }
            for item in cycles
        ]
        lineage = {
            "profile_revision_id": coach_session.profile_revision_id,
            "session_id": coach_session.session_id,
            "path_revision_id": coach_session.path_revision_id,
            "activity_id": coach_session.activity_id,
            "competency_keys": list(coach_session.competency_keys_json),
            "responses": [
                {
                    "response_id": item.response_id,
                    "card_id": item.card_id,
                    "evaluation_kind": item.evaluation_kind,
                    "source_ref_ids": list(item.source_ref_ids_json),
                    "invocation_id": item.invocation_id,
                    "prompt_revision_id": item.prompt_revision_id,
                    "prompt_contract_hash": item.prompt_contract_hash,
                    "model_routing_revision_id": item.model_routing_revision_id,
                }
                for item in responses
            ],
        }
        outcome = CoachOutcome(
            outcome_id=_id(),
            session_id=coach_session.session_id,
            organization_id=coach_session.organization_id,
            learner_id=coach_session.learner_id,
            attempt_id=coach_session.attempt_id,
            profile_revision_id=coach_session.profile_revision_id,
            mastery_score_percent=mastery_score,
            checkpoint_results_json=checkpoint_results,
            cycle_history_json=cycle_history,
            source_refs_json=[
                {
                    "resource_type": item.resource_type,
                    "resource_id": item.resource_id,
                    "revision_id": item.revision_id,
                }
                for item in context.references
            ],
            lineage_json=lineage,
            generic_activity_outcome_id=None,
            idempotency_key_hash=_secret_hash(
                f"coach-outcome:{coach_session.session_id}"
            ),
            created_at=_now(),
        )
        self._session.add(outcome)
        await self._session.flush([outcome])
        generic_outcome_id = await self._outcomes.record(
            CoachActivityOutcomePayload(
                organization_id=coach_session.organization_id,
                actor_id=coach_session.learner_id,
                attempt_id=coach_session.attempt_id,
                lifecycle_result="completed",
                assessment_result="passed",
                result_type="coach_outcome",
                result_id=outcome.outcome_id,
                score=mastery_score,
                max_score=100,
                passed=True,
                source_refs=tuple(
                    {
                        "resource_type": item.resource_type,
                        "resource_id": item.resource_id,
                    }
                    for item in context.references
                ),
                lineage=lineage,
                confidence=(
                    1
                    - max(
                        (float(item.uncertainty or 0) for item in responses),
                        default=0,
                    )
                ),
                degradations=context.degradations,
                next_action={"type": "continue_training_path"},
                idempotency_key=f"coach-outcome:{coach_session.session_id}",
                trace_id=trace_id,
            )
        )
        outcome.generic_activity_outcome_id = generic_outcome_id
        coach_session.status = "completed"
        coach_session.active_task_id = None
        coach_session.completed_at = _now()
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([outcome, coach_session])

    async def _projection(self, coach_session: CoachSession) -> CoachRuntimeProjection:
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        cards = list(
            (
                await self._session.execute(
                    select(CoachTrainingCard)
                    .join(CoachTurn, CoachTurn.turn_id == CoachTrainingCard.turn_id)
                    .where(CoachTrainingCard.session_id == coach_session.session_id)
                    .order_by(CoachTurn.sequence)
                )
            ).scalars()
        )
        current_card = next((item for item in cards if item.status == "current"), None)
        latest_response = await self._session.scalar(
            select(CoachCardResponse)
            .where(CoachCardResponse.session_id == coach_session.session_id)
            .where(CoachCardResponse.status == "evaluated")
            .order_by(desc(CoachCardResponse.evaluated_at))
            .limit(1)
        )
        latest_assistance = await self._session.scalar(
            select(CoachAssistance)
            .where(CoachAssistance.session_id == coach_session.session_id)
            .where(
                CoachAssistance.status.in_(
                    ("queued", "completed", "failed_recoverable")
                )
            )
            .order_by(desc(CoachAssistance.created_at))
            .limit(1)
        )
        active_cycle_cards = [
            item for item in cards if item.cycle_id == coach_session.active_cycle_id
        ]
        completed_cards = sum(item.status == "scored" for item in active_cycle_cards)
        checkpoint = profile.checkpoints[coach_session.checkpoint_index]
        source_labels = {item.ref_id: item.label for item in context.references}
        current_card_payload: dict[str, Any] | None = None
        if current_card is not None:
            current_card_payload = dict(current_card.public_payload_json)
            current_card_payload.pop("source_ref_ids", None)
            current_card_payload["sources"] = [
                source_labels[ref_id]
                for ref_id in current_card.source_ref_ids_json
                if ref_id in source_labels
            ]
        commands = {
            "preparing": (),
            "awaiting_answer": (
                "submit_coach_answer",
                "request_coach_assistance",
                "cancel",
            ),
            "evaluating": ("cancel",),
            "feedback_ready": (
                "continue_coach",
                "request_coach_assistance",
                "cancel",
            ),
            "checkpoint_mastered": ("continue_coach", "cancel"),
            "remediation_required": ("continue_coach", "cancel"),
            "failed_recoverable": ("retry_coach", "cancel"),
            "needs_human_help": ("cancel",),
            "completed": ("review",),
            "cancelled": (),
        }.get(coach_session.status, ())
        return CoachRuntimeProjection(
            session_id=coach_session.session_id,
            status=coach_session.status,
            version=coach_session.version,
            task_id=coach_session.active_task_id,
            runner={
                "kind": "ai_coach",
                "profile_title": profile.title,
                "checkpoint": {
                    "current": coach_session.checkpoint_index + 1,
                    "total": len(profile.checkpoints),
                    "title": checkpoint.title,
                    "objective": checkpoint.objective,
                },
                "progress": {
                    "completed_cards": completed_cards,
                    "total_cards": len(active_cycle_cards),
                },
                "source_context": [
                    {
                        "label": item.label,
                        "resource_type": item.resource_type,
                    }
                    for item in context.references
                ],
                "weaknesses": [
                    {
                        "competency_key": item.competency_key,
                        "summary": item.summary,
                        "confidence": item.confidence,
                    }
                    for item in context.weaknesses
                ],
                "current_card": (
                    None
                    if current_card is None
                    else {
                        "card_id": current_card.card_id,
                        **(current_card_payload or {}),
                    }
                ),
                "last_feedback": (
                    None
                    if latest_response is None
                    else {
                        "card_id": latest_response.card_id,
                        "mastered": latest_response.mastered,
                        "evaluation_kind": latest_response.evaluation_kind,
                        **dict(latest_response.evaluation_json or {}),
                    }
                ),
                "assistance": (
                    None
                    if latest_assistance is None
                    else {
                        "status": latest_assistance.status,
                        "assistance_type": latest_assistance.assistance_type,
                        "result": latest_assistance.result_json,
                    }
                ),
                "mastery": {
                    "threshold_percent": profile.mastery_rule.threshold_percent,
                    "cycle": coach_session.cycle_no,
                    "maximum_automatic_cycles": (
                        profile.remediation_policy.maximum_automatic_cycles
                    ),
                },
                "failure": (
                    None
                    if coach_session.status != "failed_recoverable"
                    else {
                        "stage": coach_session.failure_stage,
                        "message": coach_session.safe_error_message,
                        "answer_preserved": coach_session.failure_stage
                        == "answer_evaluation",
                    }
                ),
                "human_help": (
                    None
                    if coach_session.status != "needs_human_help"
                    else {
                        "title": "需要培训负责人协助",
                        "message": "自动补练已到边界或当前证据不足，培训负责人将给出下一步。",
                        "status": coach_session.human_help_status or "open",
                        "next_action": coach_session.human_help_next_action_json,
                    }
                ),
            },
            available_commands=commands,
        )

    async def _published_profile(
        self,
        *,
        organization_id: str,
        revision_id: str,
    ) -> CoachProfileRevision:
        row = await self._session.get(CoachProfileRevision, revision_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.status not in {"published", "archived"}
        ):
            raise AICoachError(
                "[COACH_PROFILE_NOT_PUBLISHED]",
                "当前训练引用的教练配置尚未发布或不可访问。",
                422,
            )
        return row

    async def _load_session(
        self,
        *,
        organization_id: str,
        learner_id: str,
        attempt_id: str,
        for_update: bool,
    ) -> CoachSession:
        query = select(CoachSession).where(CoachSession.attempt_id == attempt_id)
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if (
            row is None
            or row.organization_id != organization_id
            or row.learner_id != learner_id
        ):
            self._not_found()
        return row

    async def _replayed_command(
        self,
        coach_session: CoachSession,
        command: str,
        idempotency_key: str,
    ) -> bool:
        row = await self._session.scalar(
            select(CoachCommandAudit.audit_id)
            .where(CoachCommandAudit.object_type == "coach_session")
            .where(CoachCommandAudit.object_id == coach_session.session_id)
            .where(CoachCommandAudit.command == command)
            .where(
                CoachCommandAudit.idempotency_key_hash == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        return row is not None

    async def _record_command(
        self,
        coach_session: CoachSession,
        *,
        command: str,
        idempotency_key: str,
        before_version: int,
        trace_id: str | None,
    ) -> None:
        self._session.add(
            CoachCommandAudit(
                audit_id=_id(),
                organization_id=coach_session.organization_id,
                actor_id=coach_session.learner_id,
                capability="newcomer.activity.execute",
                object_type="coach_session",
                object_id=coach_session.session_id,
                command=command,
                before_version=before_version,
                after_version=coach_session.version,
                idempotency_key_hash=_secret_hash(idempotency_key),
                reason=None,
                trace_id=trace_id,
                result="succeeded",
                details_json={},
                occurred_at=_now(),
            )
        )
        await self._session.flush()

    @staticmethod
    def _validate_answer(
        card: CoachTrainingCard,
        answer: dict[str, Any],
    ) -> None:
        answer_type = answer.get("answer_type")
        if card.card_type in {"single_choice", "multiple_choice", "scenario_choice"}:
            if answer_type != "choice":
                raise AICoachError(
                    "[COACH_ANSWER_TYPE_INVALID]", "请选择当前训练卡要求的答案。", 422
                )
            selected = [str(item) for item in answer.get("selected_option_ids", [])]
            option_ids = {
                str(item["option_id"])
                for item in card.public_payload_json.get("options", [])
            }
            if (
                len(selected) != len(set(selected))
                or not set(selected).issubset(option_ids)
                or (card.card_type != "multiple_choice" and len(selected) != 1)
            ):
                raise AICoachError(
                    "[COACH_ANSWER_INVALID]", "选择答案不属于当前训练卡。", 422
                )
            return
        if card.card_type == "ordering":
            if answer_type != "ordering":
                raise AICoachError(
                    "[COACH_ANSWER_TYPE_INVALID]", "请按要求排列全部步骤。", 422
                )
            actual = [str(item) for item in answer.get("ordered_item_ids", [])]
            expected = {
                str(item["item_id"])
                for item in card.public_payload_json.get("items", [])
            }
            if len(actual) != len(set(actual)) or set(actual) != expected:
                raise AICoachError(
                    "[COACH_ANSWER_INVALID]", "请完整排列当前训练卡的全部步骤。", 422
                )
            return
        if answer_type != "text" or not str(answer.get("text", "")).strip():
            raise AICoachError(
                "[COACH_ANSWER_TYPE_INVALID]", "请填写当前训练卡要求的回答。", 422
            )

    @staticmethod
    def _require_version(coach_session: CoachSession, expected: int) -> None:
        if coach_session.version != expected:
            raise AICoachError(
                "[COACH_VERSION_CONFLICT]",
                "训练进度已更新，请刷新后继续。",
                412,
                details={
                    "expected_version": expected,
                    "actual_version": coach_session.version,
                },
            )

    @staticmethod
    def _not_found() -> Never:
        raise AICoachError(
            "[COACH_SESSION_NOT_FOUND]", "训练会话不存在或不可访问。", 404
        )

    @staticmethod
    def _idempotency_conflict() -> Never:
        raise AICoachError(
            "[COACH_IDEMPOTENCY_CONFLICT]",
            "同一提交标识已用于不同内容，请刷新后重试。",
            409,
        )


__all__ = [
    "CoachRuntimeProjection",
    "CoachStartContext",
    "StructuredCoachRuntime",
]
