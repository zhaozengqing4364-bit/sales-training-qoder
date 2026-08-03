"""Durable task definitions and executable handlers for structured Coach work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_coach.errors import AICoachError
from ai_coach.pipeline import (
    CoachAnswerEvaluationProcessor,
    CoachAssistancePlan,
    CoachAssistanceProcessor,
    CoachAssistanceResult,
    CoachCardGenerationProcessor,
    CoachEvaluationPlan,
    CoachEvaluationResult,
    CoachGenerationPlan,
    CoachGenerationResult,
)
from ai_coach.task_types import (
    COACH_ANSWER_EVALUATION_TASK_TYPE,
    COACH_ASSISTANCE_TASK_TYPE,
    COACH_CARD_GENERATION_TASK_TYPE,
)
from ai_platform import AIInvocationPort, PromptCompilationService
from task_runtime import TaskDefinition, TaskRegistry
from task_runtime.contracts import TaskCompletion, TaskPolicy, TaskResultKind
from task_runtime.errors import TaskExecutionError, TaskFailureKind

AIInvocationFactory = Callable[[], AIInvocationPort]


class CoachCardGenerationTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_id: str = Field(min_length=1, max_length=160)


class CoachCardGenerationTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    activity_id: str
    cycle_id: str
    card_ids: tuple[str, ...] = Field(min_length=3, max_length=5)
    invocation_id: str
    status: str


class CoachAnswerEvaluationTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    response_id: str = Field(min_length=1, max_length=160)


class CoachAnswerEvaluationTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    activity_id: str
    response_id: str
    card_id: str
    score_percent: float = Field(ge=0, le=100)
    mastered: bool
    session_status: str
    invocation_id: str | None


class CoachAssistanceTaskInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assistance_id: str = Field(min_length=1, max_length=160)


class CoachAssistanceTaskResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    activity_id: str
    assistance_id: str
    status: str
    invocation_id: str | None


class CoachCardGenerationTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ai_factory: AIInvocationFactory,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session_factory = session_factory
        self._ai_factory = ai_factory
        self._prompt_compiler = prompt_compiler

    async def execute(self, context: Any, payload: BaseModel) -> TaskCompletion:
        if not isinstance(payload, CoachCardGenerationTaskInput):
            raise TypeError("coach card generation payload type mismatch")
        await context.checkpoint()
        ai = self._ai_factory()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                prepared = await CoachCardGenerationProcessor(
                    session,
                    prompt_compiler=self._prompt_compiler,
                ).prepare_cycle(
                    cycle_id=payload.cycle_id,
                    task_id=str(context.claim.task_id),
                )
                await session.commit()
            except AICoachError as exc:
                await session.rollback()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise
        if isinstance(prepared, CoachGenerationResult):
            result = prepared
            await context.checkpoint()
        else:
            invocation = await ai.invoke(prepared.request)
            await context.checkpoint()
            result = await self._apply_generation(
                context=context,
                plan=prepared,
                invocation=invocation,
            )
        structured = CoachCardGenerationTaskResult.model_validate(
            result.model_dump(mode="json")
        )
        return TaskCompletion(
            structured_payload=structured.model_dump(mode="json"),
            result_kind=TaskResultKind.COMPLETE,
            resource_type="coach_session",
            resource_id=result.session_id,
            location=(f"/api/v1/newcomer-training/activities/{result.activity_id}"),
        )

    async def _apply_generation(
        self,
        *,
        context: Any,
        plan: CoachGenerationPlan,
        invocation: Any,
    ) -> CoachGenerationResult:
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                result = await CoachCardGenerationProcessor(
                    session,
                    prompt_compiler=self._prompt_compiler,
                ).apply_result(plan=plan, result=invocation)
                await session.commit()
                return result
            except AICoachError as exc:
                await session.commit()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise


class CoachAnswerEvaluationTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ai_factory: AIInvocationFactory,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session_factory = session_factory
        self._ai_factory = ai_factory
        self._prompt_compiler = prompt_compiler

    async def execute(self, context: Any, payload: BaseModel) -> TaskCompletion:
        if not isinstance(payload, CoachAnswerEvaluationTaskInput):
            raise TypeError("coach answer evaluation payload type mismatch")
        await context.checkpoint()
        ai = self._ai_factory()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                prepared = await CoachAnswerEvaluationProcessor(
                    session,
                    prompt_compiler=self._prompt_compiler,
                ).prepare_response(
                    response_id=payload.response_id,
                    task_id=str(context.claim.task_id),
                )
                await session.commit()
            except AICoachError as exc:
                await session.rollback()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise
        if isinstance(prepared, CoachEvaluationResult):
            result = prepared
            await context.checkpoint()
        else:
            invocation = await ai.invoke(prepared.request)
            await context.checkpoint()
            result = await self._apply_evaluation(
                context=context,
                plan=prepared,
                invocation=invocation,
            )
        structured = CoachAnswerEvaluationTaskResult.model_validate(
            result.model_dump(mode="json")
        )
        return TaskCompletion(
            structured_payload=structured.model_dump(mode="json"),
            result_kind=TaskResultKind.COMPLETE,
            resource_type="coach_card_response",
            resource_id=result.response_id,
            location=(f"/api/v1/newcomer-training/activities/{result.activity_id}"),
        )

    async def _apply_evaluation(
        self,
        *,
        context: Any,
        plan: CoachEvaluationPlan,
        invocation: Any,
    ) -> CoachEvaluationResult:
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                result = await CoachAnswerEvaluationProcessor(
                    session,
                    prompt_compiler=self._prompt_compiler,
                ).apply_result(plan=plan, result=invocation)
                await session.commit()
                return result
            except AICoachError as exc:
                await session.commit()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise


class CoachAssistanceTaskHandler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ai_factory: AIInvocationFactory,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session_factory = session_factory
        self._ai_factory = ai_factory
        self._prompt_compiler = prompt_compiler

    async def execute(self, context: Any, payload: BaseModel) -> TaskCompletion:
        if not isinstance(payload, CoachAssistanceTaskInput):
            raise TypeError("coach assistance payload type mismatch")
        await context.checkpoint()
        ai = self._ai_factory()
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                prepared = await CoachAssistanceProcessor(
                    session,
                    prompt_compiler=self._prompt_compiler,
                ).prepare_assistance(
                    assistance_id=payload.assistance_id,
                    task_id=str(context.claim.task_id),
                )
                await session.commit()
            except AICoachError as exc:
                await session.rollback()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise
        if isinstance(prepared, CoachAssistanceResult):
            result = prepared
            await context.checkpoint()
        else:
            invocation = await ai.invoke(prepared.request)
            await context.checkpoint()
            result = await self._apply_assistance(
                context=context,
                plan=prepared,
                invocation=invocation,
            )
        structured = CoachAssistanceTaskResult.model_validate(
            result.model_dump(mode="json")
        )
        return TaskCompletion(
            structured_payload=structured.model_dump(mode="json"),
            result_kind=TaskResultKind.COMPLETE,
            resource_type="coach_assistance",
            resource_id=result.assistance_id,
            location=(f"/api/v1/newcomer-training/activities/{result.activity_id}"),
        )

    async def _apply_assistance(
        self,
        *,
        context: Any,
        plan: CoachAssistancePlan,
        invocation: Any,
    ) -> CoachAssistanceResult:
        async with self._session_factory() as session:
            await context.fenced(session).assert_current()
            try:
                result = await CoachAssistanceProcessor(
                    session,
                    prompt_compiler=self._prompt_compiler,
                ).apply_result(plan=plan, result=invocation)
                await session.commit()
                return result
            except AICoachError as exc:
                await session.commit()
                raise _task_error(exc) from exc
            except Exception:
                await session.rollback()
                raise


def register_coach_task_definitions(
    registry: TaskRegistry,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    ai_factory: AIInvocationFactory | None = None,
    prompt_compiler: PromptCompilationService | None = None,
) -> None:
    dependencies = (session_factory, ai_factory, prompt_compiler)
    if any(item is not None for item in dependencies) and not all(
        item is not None for item in dependencies
    ):
        raise ValueError(
            "Coach Worker 注册必须同时提供 session、AI 和 Prompt 编译依赖。"
        )
    generation_handler = None
    evaluation_handler = None
    assistance_handler = None
    if session_factory is not None and ai_factory is not None:
        assert prompt_compiler is not None
        generation_handler = CoachCardGenerationTaskHandler(
            session_factory,
            ai_factory=ai_factory,
            prompt_compiler=prompt_compiler,
        )
        evaluation_handler = CoachAnswerEvaluationTaskHandler(
            session_factory,
            ai_factory=ai_factory,
            prompt_compiler=prompt_compiler,
        )
        assistance_handler = CoachAssistanceTaskHandler(
            session_factory,
            ai_factory=ai_factory,
            prompt_compiler=prompt_compiler,
        )
    registry.register(
        TaskDefinition(
            task_type=COACH_CARD_GENERATION_TASK_TYPE,
            schema_version=1,
            input_model=CoachCardGenerationTaskInput,
            result_model=CoachCardGenerationTaskResult,
            policy=TaskPolicy(
                timeout_seconds=240,
                max_attempts=3,
                initial_backoff_seconds=15,
                max_backoff_seconds=300,
                lease_seconds=60,
                retryable_error_codes=frozenset({"coach_card_generation_failed"}),
            ),
            handler=generation_handler,
            metric_tags=(("domain", "ai_coach"), ("workload", "generation")),
            allowed_data_classifications=frozenset({"confidential"}),
            max_payload_bytes=1_024,
        )
    )
    registry.register(
        TaskDefinition(
            task_type=COACH_ANSWER_EVALUATION_TASK_TYPE,
            schema_version=1,
            input_model=CoachAnswerEvaluationTaskInput,
            result_model=CoachAnswerEvaluationTaskResult,
            policy=TaskPolicy(
                timeout_seconds=180,
                max_attempts=3,
                initial_backoff_seconds=15,
                max_backoff_seconds=300,
                lease_seconds=60,
                retryable_error_codes=frozenset({"coach_answer_evaluation_failed"}),
            ),
            handler=evaluation_handler,
            metric_tags=(("domain", "ai_coach"), ("workload", "evaluation")),
            allowed_data_classifications=frozenset({"confidential"}),
            max_payload_bytes=1_024,
        )
    )
    registry.register(
        TaskDefinition(
            task_type=COACH_ASSISTANCE_TASK_TYPE,
            schema_version=1,
            input_model=CoachAssistanceTaskInput,
            result_model=CoachAssistanceTaskResult,
            policy=TaskPolicy(
                timeout_seconds=120,
                max_attempts=2,
                initial_backoff_seconds=15,
                max_backoff_seconds=120,
                lease_seconds=60,
                retryable_error_codes=frozenset({"coach_assistance_failed"}),
            ),
            handler=assistance_handler,
            metric_tags=(("domain", "ai_coach"), ("workload", "assistance")),
            allowed_data_classifications=frozenset({"confidential"}),
            max_payload_bytes=1_024,
        )
    )


def _task_error(exc: AICoachError) -> TaskExecutionError:
    retryable = bool(exc.details and exc.details.get("retryable") is True)
    if retryable or exc.status_code == 503:
        kind = TaskFailureKind.PROVIDER_TEMPORARY
    elif exc.status_code == 403:
        kind = TaskFailureKind.PERMISSION_DENIED
    elif exc.status_code in {404, 422}:
        kind = TaskFailureKind.INVALID_INPUT
    else:
        kind = TaskFailureKind.BUSINESS_CONFLICT
    return TaskExecutionError(
        code=exc.code.strip("[]").lower(),
        message=exc.message,
        kind=kind,
    )


__all__ = [
    "COACH_ANSWER_EVALUATION_TASK_TYPE",
    "COACH_ASSISTANCE_TASK_TYPE",
    "COACH_CARD_GENERATION_TASK_TYPE",
    "CoachAnswerEvaluationTaskHandler",
    "CoachAnswerEvaluationTaskInput",
    "CoachAnswerEvaluationTaskResult",
    "CoachAssistanceTaskHandler",
    "CoachAssistanceTaskInput",
    "CoachAssistanceTaskResult",
    "CoachCardGenerationTaskHandler",
    "CoachCardGenerationTaskInput",
    "CoachCardGenerationTaskResult",
    "register_coach_task_definitions",
]
