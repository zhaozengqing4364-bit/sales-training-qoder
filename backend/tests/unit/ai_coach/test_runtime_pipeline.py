from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_coach.ai_schemas import (
    COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
    COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
    COACH_CARD_GENERATION_INPUT_SCHEMA,
    COACH_CARD_GENERATION_OUTPUT_SCHEMA,
    COACH_EXPLANATION_INPUT_SCHEMA,
    COACH_EXPLANATION_OUTPUT_SCHEMA,
)
from ai_coach.contracts import (
    CoachContextReference,
    CoachContextSnapshot,
    CoachHumanInterventionInput,
    CoachProfileSnapshot,
    CoachWeaknessInput,
    RequestCoachAssistanceInput,
    SubmitCoachAnswerInput,
)
from ai_coach.errors import AICoachError
from ai_coach.governance import CoachGovernanceService, CoachReviewActor
from ai_coach.models import (
    CoachAssistance,
    CoachCardResponse,
    CoachHumanIntervention,
    CoachOutcome,
    CoachProfileRevision,
    CoachRemediationCycle,
    CoachSession,
    CoachTrainingCard,
    CoachTurn,
)
from ai_coach.pipeline import (
    CoachAnswerEvaluationProcessor,
    CoachAssistancePlan,
    CoachAssistanceProcessor,
    CoachCardGenerationProcessor,
    CoachEvaluationPlan,
    CoachGenerationPlan,
)
from ai_coach.runtime import CoachStartContext, StructuredCoachRuntime
from ai_coach.task_definitions import (
    CoachCardGenerationTaskHandler,
    CoachCardGenerationTaskInput,
)
from ai_platform import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationResult,
    AIInvocationStatus,
    PromptCompilationService,
    PublishedPromptRevisionSnapshot,
    StaticPublishedPromptRevisionResolver,
    StrictPromptCompiler,
    compute_prompt_revision_content_hash,
)
from newcomer_foundation_composition import FoundationCoachContextBuilder
from task_runtime.contracts import (
    ActorContext,
    TaskProgressProjection,
    TaskProjection,
    TaskReference,
    TaskState,
)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _contract(
    *,
    purpose: str,
    template_id: str,
    prompt_revision_id: str,
    input_schema: str,
    output_schema: str,
) -> dict[str, object]:
    return {
        "business_purpose": purpose,
        "prompt_template_id": template_id,
        "prompt_revision_id": prompt_revision_id,
        "model_routing_profile_id": f"{purpose}-models",
        "model_routing_revision_id": f"{purpose}-models-v1",
        "input_schema_version": input_schema,
        "output_schema_version": output_schema,
        "timeout_policy_ref": f"{purpose}-timeout-v1",
        "retry_policy_ref": f"{purpose}-retry-v1",
        "allow_fallback": True,
    }


def _profile() -> CoachProfileSnapshot:
    return CoachProfileSnapshot.model_validate(
        {
            "title": "新人销售基础能力结构化教练",
            "training_goal": "依次巩固识别理解、组织表达和销售场景迁移。",
            "applicable_competency_keys": ["identify", "express", "transfer"],
            "allowed_knowledge_scope": ["learning-unit-revision-1"],
            "tone_principles": ["具体", "尊重"],
            "feedback_principles": ["引用回答证据", "给出下一步"],
            "checkpoints": [
                {
                    "checkpoint_key": "identify",
                    "title": "识别与理解",
                    "objective": "识别客户问题与方法边界。",
                    "competency_keys": ["identify"],
                },
                {
                    "checkpoint_key": "express",
                    "title": "组织与表达",
                    "objective": "用客户语言组织清晰表达。",
                    "competency_keys": ["express"],
                },
                {
                    "checkpoint_key": "transfer",
                    "title": "销售场景迁移",
                    "objective": "把方法迁移到销售推进场景。",
                    "competency_keys": ["transfer"],
                },
            ],
            "card_type_whitelist": [
                "single_choice",
                "multiple_choice",
                "ordering",
                "short_answer_rewrite",
                "scenario_choice",
                "key_points_completion",
                "example_comparison",
                "summary",
            ],
            "mastery_rule": {
                "threshold_percent": 80,
                "minimum_scored_cards": 3,
                "maximum_uncertainty": 0.35,
            },
            "remediation_policy": {
                "cards_per_cycle_min": 3,
                "cards_per_cycle_max": 5,
                "maximum_automatic_cycles": 2,
            },
            "ai": {
                "card_generation": _contract(
                    purpose="foundation_coach_card_generation",
                    template_id="coach-card-generation",
                    prompt_revision_id="coach-card-generation-v1",
                    input_schema=COACH_CARD_GENERATION_INPUT_SCHEMA,
                    output_schema=COACH_CARD_GENERATION_OUTPUT_SCHEMA,
                ),
                "answer_evaluation": _contract(
                    purpose="foundation_coach_answer_evaluation",
                    template_id="coach-answer-evaluation",
                    prompt_revision_id="coach-answer-evaluation-v1",
                    input_schema=COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
                    output_schema=COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
                ),
                "feedback_explanation": _contract(
                    purpose="foundation_coach_feedback_explanation",
                    template_id="coach-feedback-explanation",
                    prompt_revision_id="coach-feedback-explanation-v1",
                    input_schema=COACH_EXPLANATION_INPUT_SCHEMA,
                    output_schema=COACH_EXPLANATION_OUTPUT_SCHEMA,
                ),
            },
        }
    )


def _context() -> CoachContextSnapshot:
    return CoachContextSnapshot(
        references=(
            CoachContextReference(
                ref_id="source-1",
                resource_type="learning_unit",
                resource_id="learning-unit-1",
                revision_id="learning-unit-revision-1",
                label="需求澄清方法",
                excerpt="先确认客户目标、业务影响和约束，再给出回应。",
            ),
        ),
        weaknesses=(
            CoachWeaknessInput(
                competency_key="identify",
                source_ref_ids=("source-1",),
                summary="需求澄清仍需巩固",
                confidence=0.9,
            ),
        ),
    )


def _prompt_revision(
    *,
    template_id: str,
    purpose: str,
    revision_id: str,
    variables: tuple[str, ...],
    input_schema: str,
    output_schema: str,
) -> PublishedPromptRevisionSnapshot:
    template = "\n".join(f"{item}={{{{ {item} }}}}" for item in variables)
    return PublishedPromptRevisionSnapshot(
        template_id=template_id,
        business_purpose=purpose,
        revision_id=revision_id,
        revision_no=1,
        status="published",
        template=template,
        variables=variables,
        input_schema_version=input_schema,
        output_schema_version=output_schema,
        content_hash=compute_prompt_revision_content_hash(
            template_id=template_id,
            business_purpose=purpose,
            revision_id=revision_id,
            revision_no=1,
            template=template,
            variables=variables,
            input_schema_version=input_schema,
            output_schema_version=output_schema,
        ),
    )


def _prompt_compiler() -> PromptCompilationService:
    revisions = (
        _prompt_revision(
            template_id="coach-card-generation",
            purpose="foundation_coach_card_generation",
            revision_id="coach-card-generation-v1",
            variables=(
                "checkpoint_json",
                "context_json",
                "cycle_no",
                "profile_json",
                "remediation_inputs_json",
            ),
            input_schema=COACH_CARD_GENERATION_INPUT_SCHEMA,
            output_schema=COACH_CARD_GENERATION_OUTPUT_SCHEMA,
        ),
        _prompt_revision(
            template_id="coach-answer-evaluation",
            purpose="foundation_coach_answer_evaluation",
            revision_id="coach-answer-evaluation-v1",
            variables=(
                "answer_json",
                "card_json",
                "reference_points_json",
                "sources_json",
            ),
            input_schema=COACH_ANSWER_EVALUATION_INPUT_SCHEMA,
            output_schema=COACH_ANSWER_EVALUATION_OUTPUT_SCHEMA,
        ),
        _prompt_revision(
            template_id="coach-feedback-explanation",
            purpose="foundation_coach_feedback_explanation",
            revision_id="coach-feedback-explanation-v1",
            variables=(
                "assistance_type",
                "card_json",
                "feedback_json",
                "sources_json",
            ),
            input_schema=COACH_EXPLANATION_INPUT_SCHEMA,
            output_schema=COACH_EXPLANATION_OUTPUT_SCHEMA,
        ),
    )
    return PromptCompilationService(
        resolver=StaticPublishedPromptRevisionResolver(list(revisions)),
        compiler=StrictPromptCompiler(),
    )


class _ContextBuilder:
    async def build(self, **_: object) -> CoachContextSnapshot:
        return _context()


class _Tasks:
    def __init__(self) -> None:
        self.commands: list[Any] = []
        self.cancelled: list[str] = []

    async def enqueue(self, command: Any) -> TaskReference:
        self.commands.append(command)
        return TaskReference(
            task_id=f"coach-task-{len(self.commands)}",
            state=TaskState.QUEUED,
            organization_id=command.organization_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            created_at=datetime.now(UTC),
        )

    async def request_cancel(
        self,
        task_id: str,
        actor: ActorContext,
        *,
        idempotency_key: str | None = None,
    ) -> TaskProjection:
        del idempotency_key
        self.cancelled.append(task_id)
        return self._projection(
            task_id=task_id,
            state=TaskState.CANCEL_REQUESTED,
            actor=actor,
        )

    async def get(self, task_id: str, viewer: ActorContext) -> TaskProjection:
        return self._projection(task_id=task_id, state=TaskState.QUEUED, actor=viewer)

    @staticmethod
    def _projection(
        *,
        task_id: str,
        state: TaskState,
        actor: ActorContext,
    ) -> TaskProjection:
        now = datetime.now(UTC)
        return TaskProjection(
            task_id=task_id,
            task_type="ai_coach.test",
            schema_version=1,
            organization_id=actor.organization_id,
            actor_id=actor.actor_id,
            resource_type="coach_session",
            resource_id="session-1",
            state=state,
            priority=50,
            attempt_count=0,
            max_attempts=3,
            next_run_at=None,
            deadline_at=None,
            progress=TaskProgressProjection(stage="test"),
            result_kind=None,
            result_location=None,
            error=None,
            version=1,
            created_at=now,
            updated_at=now,
        )


class _Outcomes:
    def __init__(self) -> None:
        self.payloads: list[Any] = []

    async def record(self, payload: Any) -> str:
        self.payloads.append(payload)
        return f"generic-coach-outcome-{len(self.payloads)}"


class _FencedHandlerSession:
    async def assert_current(self) -> None:
        return None


class _TaskHandlerContext:
    def __init__(self, task_id: str) -> None:
        self.claim = SimpleNamespace(task_id=task_id)

    async def checkpoint(self) -> None:
        return None

    def fenced(self, _: AsyncSession) -> _FencedHandlerSession:
        return _FencedHandlerSession()


class _GenerationAI:
    async def invoke(self, request: Any) -> AIInvocationResult:
        return AIInvocationResult(
            invocation_id="handler-generation-invocation",
            status=AIInvocationStatus.SUCCEEDED,
            validated_output={
                "cards": _generated_cards(first_type="single_choice"),
                "generation_strategy": "处理器结果位置验证",
            },
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
        )


async def _seed_profile(test_db: Any) -> CoachProfileRevision:
    profile = _profile()
    row = CoachProfileRevision(
        revision_id="coach-profile-revision-1",
        organization_id="org-1",
        stable_key="foundation-coach",
        revision_no=1,
        revision_label="2026.07",
        status="published",
        snapshot_json=profile.model_dump(mode="json"),
        content_hash=_hash(profile.model_dump(mode="json")),
        created_by="admin-1",
        published_by="admin-1",
        created_at=datetime.now(UTC),
        published_at=datetime.now(UTC),
    )
    test_db.add(row)
    await test_db.flush([row])
    return row


async def _start(
    test_db: Any,
    *,
    learner_id: str,
) -> tuple[StructuredCoachRuntime, _Tasks, _Outcomes, CoachSession]:
    profile = await _seed_profile(test_db)
    tasks = _Tasks()
    outcomes = _Outcomes()
    runtime = StructuredCoachRuntime(
        test_db,
        tasks=tasks,
        context_builder=_ContextBuilder(),
        outcomes=outcomes,
    )
    projection = await runtime.start_or_resume(
        context=CoachStartContext(
            organization_id="org-1",
            learner_id=learner_id,
            enrollment_id="enrollment-1",
            path_revision_id="path-revision-1",
            activity_id="coach-foundation-remediation",
            attempt_id="coach-attempt-1",
            profile_revision_id=profile.revision_id,
            competency_keys=("identify", "express", "transfer"),
            trace_id="trace-1",
        ),
        idempotency_key="start-coach-1",
    )
    assert projection.status == "preparing"
    row = await test_db.scalar(
        select(CoachSession).where(CoachSession.attempt_id == "coach-attempt-1")
    )
    assert row is not None
    return runtime, tasks, outcomes, row


def _generated_cards(*, first_type: str) -> list[dict[str, Any]]:
    text_card: dict[str, Any] = {
        "card_type": "short_answer_rewrite",
        "prompt": "请把回应改写为客户语言。",
        "source_ref_ids": ["source-1"],
        "instruction": "说明目标、影响和下一步。",
        "reference_points": ["客户目标", "业务影响", "下一步"],
    }
    choice_card: dict[str, Any] = {
        "card_type": "single_choice",
        "prompt": "面对模糊需求时，第一步怎么做？",
        "source_ref_ids": ["source-1"],
        "options": [
            {"option_id": "confirm", "text": "澄清目标和影响"},
            {"option_id": "promise", "text": "立即承诺"},
        ],
        "correct_option_ids": ["confirm"],
    }
    ordering_card: dict[str, Any] = {
        "card_type": "ordering",
        "prompt": "排列需求沟通步骤。",
        "source_ref_ids": ["source-1"],
        "items": [
            {"item_id": "clarify", "text": "澄清"},
            {"item_id": "respond", "text": "回应"},
        ],
        "correct_order_ids": ["clarify", "respond"],
    }
    if first_type == "short_answer_rewrite":
        return [text_card, choice_card, ordering_card]
    return [choice_card, ordering_card, choice_card]


def _succeeded_result(plan: Any, output: dict[str, object]) -> AIInvocationResult:
    return AIInvocationResult(
        invocation_id=f"invocation-{plan.task_id}",
        status=AIInvocationStatus.SUCCEEDED,
        validated_output=output,
        prompt_template_id=plan.request.prompt_template_id,
        prompt_revision_id=plan.request.prompt_revision_id,
        prompt_contract_hash=plan.request.prompt_contract_hash,
        model_routing_profile_id=plan.request.model_routing_profile_id,
        model_routing_revision_id=plan.request.model_routing_revision_id,
    )


async def _apply_generation(
    test_db: Any,
    coach_session: CoachSession,
    *,
    first_type: str,
) -> None:
    plan = await CoachCardGenerationProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    ).prepare_cycle(
        cycle_id=str(coach_session.active_cycle_id),
        task_id=str(coach_session.active_task_id),
    )
    assert isinstance(plan, CoachGenerationPlan)
    assert set(plan.request.prompt_variables) == {
        "profile_json",
        "checkpoint_json",
        "context_json",
        "cycle_no",
        "remediation_inputs_json",
    }
    await CoachCardGenerationProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    ).apply_result(
        plan=plan,
        result=_succeeded_result(
            plan,
            {
                "cards": _generated_cards(first_type=first_type),
                "generation_strategy": "根据当前检查点和弱项生成三张训练卡。",
            },
        ),
    )


@pytest.mark.asyncio
async def test_generation_task_completion_returns_activity_result_location(
    test_db: Any,
    test_engine: Any,
    test_user: Any,
) -> None:
    _, _, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await test_db.commit()
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    handler = CoachCardGenerationTaskHandler(
        session_factory,
        ai_factory=_GenerationAI,
        prompt_compiler=_prompt_compiler(),
    )

    completion = await handler.execute(
        _TaskHandlerContext(str(coach_session.active_task_id)),
        CoachCardGenerationTaskInput(cycle_id=str(coach_session.active_cycle_id)),
    )

    assert completion.location == (
        "/api/v1/newcomer-training/activities/coach-foundation-remediation"
    )
    assert completion.structured_payload["activity_id"] == (
        "coach-foundation-remediation"
    )


@pytest.mark.asyncio
async def test_session_resumes_without_duplicate_task_and_can_cancel_in_flight(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, tasks, outcomes, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    start_context = CoachStartContext(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="coach-foundation-remediation",
        attempt_id="coach-attempt-1",
        profile_revision_id=coach_session.profile_revision_id,
        competency_keys=("identify", "express", "transfer"),
        trace_id="trace-1",
    )

    resumed = await runtime.start_or_resume(
        context=start_context,
        idempotency_key="start-coach-1",
    )

    assert resumed.status == "preparing"
    assert len(tasks.commands) == 1
    cancelled = await runtime.cancel(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        expected_version=resumed.version,
        idempotency_key="cancel-coach-1",
        trace_id="trace-cancel-1",
    )
    assert cancelled.status == "cancelled"
    assert tasks.cancelled == ["coach-task-1"]
    assert outcomes.payloads[0].lifecycle_result == "cancelled"


@pytest.mark.asyncio
async def test_start_fails_closed_without_authorized_published_context(
    test_db: Any,
    test_user: Any,
) -> None:
    profile = await _seed_profile(test_db)
    tasks = _Tasks()
    runtime = StructuredCoachRuntime(
        test_db,
        tasks=tasks,
        context_builder=FoundationCoachContextBuilder(test_db),
        outcomes=_Outcomes(),
    )

    with pytest.raises(AICoachError) as missing_context:
        await runtime.start_or_resume(
            context=CoachStartContext(
                organization_id="org-1",
                learner_id=str(test_user.user_id),
                enrollment_id="enrollment-1",
                path_revision_id="path-revision-1",
                activity_id="coach-foundation-remediation",
                attempt_id="coach-attempt-without-context",
                profile_revision_id=profile.revision_id,
                competency_keys=("identify", "express", "transfer"),
                trace_id="trace-no-context",
            ),
            idempotency_key="start-coach-without-context",
        )

    assert missing_context.value.code == "[COACH_CONTEXT_UNAVAILABLE]"
    assert tasks.commands == []


@pytest.mark.asyncio
async def test_answer_is_saved_before_ai_and_replayed_without_duplicate_task(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, tasks, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _apply_generation(
        test_db,
        coach_session,
        first_type="short_answer_rewrite",
    )
    workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    card_id = workspace.runner["current_card"]["card_id"]
    expected_version = workspace.version
    payload = SubmitCoachAnswerInput.model_validate(
        {
            "card_id": card_id,
            "client_token": "answer-token-001",
            "answer": {
                "answer_type": "text",
                "text": "我会先确认客户目标和影响，再约定下一步。",
            },
        }
    )

    submitted = await runtime.submit_answer(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=payload,
        expected_version=expected_version,
        idempotency_key="submit-answer-1",
        trace_id="trace-answer-1",
    )

    response = await test_db.scalar(
        select(CoachCardResponse).where(CoachCardResponse.card_id == card_id)
    )
    assert response is not None
    assert response.raw_answer_json["text"].startswith("我会先确认")
    assert response.status == "evaluating"
    assert submitted.status == "evaluating"
    assert len(tasks.commands) == 2
    assert tasks.commands[-1].resource_id == response.response_id
    assert tasks.commands[-1].data_classification == "confidential"

    replayed = await runtime.submit_answer(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=payload,
        expected_version=expected_version,
        idempotency_key="submit-answer-replayed-at-http-layer",
        trace_id="trace-answer-2",
    )
    assert replayed.status == "evaluating"
    assert len(tasks.commands) == 2


@pytest.mark.asyncio
async def test_provider_failure_preserves_answer_and_supports_bounded_retry(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, tasks, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _apply_generation(
        test_db,
        coach_session,
        first_type="short_answer_rewrite",
    )
    workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    payload = SubmitCoachAnswerInput.model_validate(
        {
            "card_id": workspace.runner["current_card"]["card_id"],
            "client_token": "answer-token-002",
            "answer": {"answer_type": "text", "text": "先澄清，再回应。"},
        }
    )
    await runtime.submit_answer(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=payload,
        expected_version=workspace.version,
        idempotency_key="submit-answer-2",
        trace_id="trace-answer-2",
    )
    response = await test_db.scalar(
        select(CoachCardResponse).where(CoachCardResponse.card_id == payload.card_id)
    )
    assert response is not None
    processor = CoachAnswerEvaluationProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    )
    plan = await processor.prepare_response(
        response_id=response.response_id,
        task_id=str(response.evaluation_task_id),
    )
    assert isinstance(plan, CoachEvaluationPlan)
    assert set(plan.request.prompt_variables) == {
        "card_json",
        "answer_json",
        "reference_points_json",
        "sources_json",
    }
    with pytest.raises(AICoachError) as failed:
        await processor.apply_result(
            plan=plan,
            result=AIInvocationResult(
                invocation_id="coach-provider-timeout-1",
                status=AIInvocationStatus.FAILED,
                failure=AIInvocationFailure(
                    code="provider_timeout",
                    classification=AIErrorClassification.TIMEOUT,
                    retryable=True,
                    message="provider timeout",
                ),
                model_routing_profile_id=plan.request.model_routing_profile_id,
                model_routing_revision_id=plan.request.model_routing_revision_id,
            ),
        )
    assert failed.value.code == "[COACH_ANSWER_EVALUATION_FAILED]"
    assert response.status == "failed_recoverable"
    assert response.raw_answer_json == payload.answer.model_dump(mode="json")
    assert coach_session.status == "failed_recoverable"

    retried = await runtime.retry_failed(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        expected_version=coach_session.version,
        idempotency_key="retry-evaluation-1",
        trace_id="trace-retry-1",
    )
    assert retried.status == "evaluating"
    assert response.status == "evaluating"
    assert len(tasks.commands) == 3


@pytest.mark.asyncio
async def test_invalid_evaluation_output_preserves_answer_and_fails_recoverably(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, _, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _apply_generation(
        test_db,
        coach_session,
        first_type="short_answer_rewrite",
    )
    workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    payload = SubmitCoachAnswerInput.model_validate(
        {
            "card_id": workspace.runner["current_card"]["card_id"],
            "client_token": "answer-token-invalid-output",
            "answer": {"answer_type": "text", "text": "先澄清，再回应。"},
        }
    )
    await runtime.submit_answer(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=payload,
        expected_version=workspace.version,
        idempotency_key="submit-invalid-evaluation-output",
        trace_id="trace-invalid-evaluation-output",
    )
    response = await test_db.scalar(
        select(CoachCardResponse).where(CoachCardResponse.card_id == payload.card_id)
    )
    assert response is not None
    processor = CoachAnswerEvaluationProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    )
    plan = await processor.prepare_response(
        response_id=response.response_id,
        task_id=str(response.evaluation_task_id),
    )
    assert isinstance(plan, CoachEvaluationPlan)

    with pytest.raises(AICoachError) as invalid:
        await processor.apply_result(
            plan=plan,
            result=_succeeded_result(plan, {}),
        )

    assert invalid.value.code == "[COACH_ANSWER_EVALUATION_OUTPUT_INVALID]"
    assert response.status == "failed_recoverable"
    assert response.raw_answer_json == payload.answer.model_dump(mode="json")
    assert coach_session.status == "failed_recoverable"


@pytest.mark.asyncio
async def test_deterministic_card_is_scored_without_ai_evaluation_task(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, tasks, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _apply_generation(test_db, coach_session, first_type="single_choice")
    workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    result = await runtime.submit_answer(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=SubmitCoachAnswerInput.model_validate(
            {
                "card_id": workspace.runner["current_card"]["card_id"],
                "client_token": "choice-answer-token",
                "answer": {
                    "answer_type": "choice",
                    "selected_option_ids": ["confirm"],
                },
            }
        ),
        expected_version=workspace.version,
        idempotency_key="choice-answer-command",
        trace_id="trace-choice",
    )

    assert result.status == "feedback_ready"
    assert result.runner["last_feedback"]["evaluation_kind"] == "deterministic"
    assert result.runner["last_feedback"]["score_percent"] == 100
    assert len(tasks.commands) == 1


@pytest.mark.asyncio
async def test_assistance_is_persisted_without_changing_formal_session_state(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, tasks, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _apply_generation(test_db, coach_session, first_type="single_choice")
    workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    card_id = workspace.runner["current_card"]["card_id"]
    requested = await runtime.request_assistance(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=RequestCoachAssistanceInput(
            assistance_type="explain",
            card_id=card_id,
        ),
        expected_version=workspace.version,
        idempotency_key="coach-assistance-1",
        trace_id="trace-assistance-1",
    )
    assistance = await test_db.scalar(
        select(CoachAssistance).where(CoachAssistance.card_id == card_id)
    )
    assert assistance is not None
    assert requested.status == "awaiting_answer"
    assert requested.runner["assistance"]["status"] == "queued"
    assert len(tasks.commands) == 2

    processor = CoachAssistanceProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    )
    plan = await processor.prepare_assistance(
        assistance_id=assistance.assistance_id,
        task_id=str(assistance.task_id),
    )
    assert isinstance(plan, CoachAssistancePlan)
    result = await processor.apply_result(
        plan=plan,
        result=_succeeded_result(
            plan,
            {
                "explanation": "先确认目标和影响，再结合约束给出回应。",
                "source_ref_ids": ["source-1"],
                "uncertainty": 0.1,
            },
        ),
    )
    restored = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    assert result.status == "completed"
    assert restored.status == "awaiting_answer"
    assert restored.runner["assistance"]["result"]["explanation"].startswith(
        "先确认"
    )


@pytest.mark.asyncio
async def test_high_ai_uncertainty_routes_completed_cycle_to_human_help(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, _, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _apply_generation(
        test_db,
        coach_session,
        first_type="short_answer_rewrite",
    )
    workspace = await runtime.workspace(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        profile_revision_id=coach_session.profile_revision_id,
        attempt_id=coach_session.attempt_id,
    )
    text_card_id = workspace.runner["current_card"]["card_id"]
    await runtime.submit_answer(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        payload=SubmitCoachAnswerInput.model_validate(
            {
                "card_id": text_card_id,
                "client_token": "high-uncertainty-text",
                "answer": {
                    "answer_type": "text",
                    "text": "先确认客户目标和影响，再约定下一步。",
                },
            }
        ),
        expected_version=workspace.version,
        idempotency_key="submit-high-uncertainty-text",
        trace_id="trace-high-uncertainty-text",
    )
    response = await test_db.scalar(
        select(CoachCardResponse).where(CoachCardResponse.card_id == text_card_id)
    )
    assert response is not None
    processor = CoachAnswerEvaluationProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    )
    plan = await processor.prepare_response(
        response_id=response.response_id,
        task_id=str(response.evaluation_task_id),
    )
    assert isinstance(plan, CoachEvaluationPlan)
    evaluated = await processor.apply_result(
        plan=plan,
        result=_succeeded_result(
            plan,
            {
                "score_percent": 100,
                "mastered": True,
                "evidence_from_answer": ["确认目标和影响"],
                "missing_points": [],
                "misconception": None,
                "feedback": "表达覆盖关键点。",
                "improvement_action": "继续下一张训练卡。",
                "next_suggestion": "继续训练",
                "uncertainty": 0.9,
                "source_ref_ids": ["source-1"],
            },
        ),
    )
    assert evaluated.mastered is False
    assert response.evaluation_json["result_source"] == "ai_inference"

    for index, answer in enumerate(
        (
            {"answer_type": "choice", "selected_option_ids": ["confirm"]},
            {
                "answer_type": "ordering",
                "ordered_item_ids": ["clarify", "respond"],
            },
        ),
        start=1,
    ):
        current = await runtime.workspace(
            organization_id="org-1",
            learner_id=str(test_user.user_id),
            profile_revision_id=coach_session.profile_revision_id,
            attempt_id=coach_session.attempt_id,
        )
        next_card = await runtime.continue_training(
            organization_id="org-1",
            learner_id=str(test_user.user_id),
            attempt_id=coach_session.attempt_id,
            expected_version=current.version,
            idempotency_key=f"continue-high-uncertainty-{index}",
            trace_id=f"trace-continue-high-uncertainty-{index}",
        )
        current_card_id = next_card.runner["current_card"]["card_id"]
        completed = await runtime.submit_answer(
            organization_id="org-1",
            learner_id=str(test_user.user_id),
            attempt_id=coach_session.attempt_id,
            payload=SubmitCoachAnswerInput.model_validate(
                {
                    "card_id": current_card_id,
                    "client_token": f"high-uncertainty-rule-{index}",
                    "answer": answer,
                }
            ),
            expected_version=next_card.version,
            idempotency_key=f"submit-high-uncertainty-rule-{index}",
            trace_id=f"trace-submit-high-uncertainty-rule-{index}",
        )

    assert completed.status == "needs_human_help"
    assert completed.runner["human_help"]["status"] == "open"
    cycle = await test_db.get(CoachRemediationCycle, coach_session.active_cycle_id)
    assert cycle is not None
    assert cycle.status == "needs_human_help"
    assert float(cycle.maximum_uncertainty or 0) == pytest.approx(0.9)


@pytest.mark.parametrize(
    "invalid_kind",
    ["empty_output", "unknown_source", "unsafe_markup"],
)
@pytest.mark.asyncio
async def test_invalid_generated_card_is_rejected_and_becomes_recoverable(
    test_db: Any,
    test_user: Any,
    invalid_kind: str,
) -> None:
    _, _, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    processor = CoachCardGenerationProcessor(
        test_db,
        prompt_compiler=_prompt_compiler(),
    )
    plan = await processor.prepare_cycle(
        cycle_id=str(coach_session.active_cycle_id),
        task_id=str(coach_session.active_task_id),
    )
    assert isinstance(plan, CoachGenerationPlan)
    cards = _generated_cards(first_type="single_choice")
    output: dict[str, object]
    if invalid_kind == "empty_output":
        output = {}
    else:
        if invalid_kind == "unknown_source":
            cards[0]["source_ref_ids"] = ["outside-context"]
        else:
            cards[0]["prompt"] = "<script>alert('unsafe')</script>"
        output = {
            "cards": cards,
            "generation_strategy": "边界验证",
        }

    with pytest.raises(AICoachError) as invalid:
        await processor.apply_result(
            plan=plan,
            result=_succeeded_result(plan, output),
        )

    assert invalid.value.code == "[COACH_CARD_GENERATION_OUTPUT_INVALID]"
    assert coach_session.status == "failed_recoverable"
    assert coach_session.failure_stage == "card_generation"
    assert not list(
        (
            await test_db.execute(
                select(CoachTrainingCard).where(
                    CoachTrainingCard.session_id == coach_session.session_id
                )
            )
        ).scalars()
    )


@pytest.mark.asyncio
async def test_automatic_remediation_stops_after_two_cycles_and_enters_help_queue(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, tasks, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )

    for cycle_no in (0, 1):
        current_cycle = await test_db.get(
            CoachRemediationCycle,
            coach_session.active_cycle_id,
        )
        assert current_cycle is not None
        current_cycle.status = "remediation_needed"
        current_cycle.result_summary_json = {"missing_points": ["客户影响"]}
        coach_session.status = "remediation_required"
        coach_session.active_task_id = None
        await test_db.flush([current_cycle, coach_session])
        projection = await runtime.continue_training(
            organization_id="org-1",
            learner_id=str(test_user.user_id),
            attempt_id=coach_session.attempt_id,
            expected_version=coach_session.version,
            idempotency_key=f"remediation-cycle-{cycle_no + 1}",
            trace_id=f"trace-cycle-{cycle_no + 1}",
        )
        assert projection.status == "preparing"
        assert coach_session.cycle_no == cycle_no + 1

    final_cycle = await test_db.get(
        CoachRemediationCycle,
        coach_session.active_cycle_id,
    )
    assert final_cycle is not None
    final_cycle.status = "remediation_needed"
    final_cycle.result_summary_json = {"missing_points": ["客户影响"]}
    coach_session.status = "remediation_required"
    coach_session.active_task_id = None
    await test_db.flush([final_cycle, coach_session])
    result = await runtime.continue_training(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        expected_version=coach_session.version,
        idempotency_key="remediation-human-help",
        trace_id="trace-human-help",
    )

    assert result.status == "needs_human_help"
    assert result.runner["human_help"]["status"] == "open"
    assert coach_session.cycle_no == 2
    assert len(tasks.commands) == 3


async def _seed_mastered_evidence(
    test_db: Any,
    coach_session: CoachSession,
) -> None:
    first_cycle = await test_db.get(
        CoachRemediationCycle,
        coach_session.active_cycle_id,
    )
    assert first_cycle is not None
    cycles = [first_cycle]
    for checkpoint_index in (1, 2):
        cycles.append(
            CoachRemediationCycle(
                cycle_id=f"mastered-cycle-{checkpoint_index}",
                session_id=coach_session.session_id,
                organization_id=coach_session.organization_id,
                checkpoint_index=checkpoint_index,
                checkpoint_key=("express" if checkpoint_index == 1 else "transfer"),
                cycle_no=0,
                status="mastered",
                reason="检查点达标",
                input_evidence_json=[],
                remediation_inputs_json=[],
                generation_strategy="基于检查点生成",
                generation_invocation_id=f"generation-{checkpoint_index}",
                score_percent=90,
                maximum_uncertainty=0.1,
                result_summary_json={"missing_points": []},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )
    first_cycle.status = "mastered"
    first_cycle.score_percent = 90
    first_cycle.maximum_uncertainty = 0.1
    first_cycle.completed_at = datetime.now(UTC)
    test_db.add_all(cycles[1:])
    for checkpoint_index, cycle in enumerate(cycles):
        turn = CoachTurn(
            turn_id=f"evidence-turn-{checkpoint_index}",
            session_id=coach_session.session_id,
            cycle_id=cycle.cycle_id,
            organization_id=coach_session.organization_id,
            checkpoint_index=checkpoint_index,
            cycle_no=0,
            sequence=checkpoint_index + 1,
            cycle_position=1,
            status="scored",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        card = CoachTrainingCard(
            card_id=f"evidence-card-{checkpoint_index}",
            session_id=coach_session.session_id,
            cycle_id=cycle.cycle_id,
            turn_id=turn.turn_id,
            organization_id=coach_session.organization_id,
            card_type="summary",
            evaluation_mode="ai",
            public_payload_json={
                "card_type": "summary",
                "prompt": "总结本检查点",
                "scope": "当前检查点",
                "source_ref_ids": ["source-1"],
            },
            evaluation_spec_json={"reference_points": ["客户目标"]},
            source_ref_ids_json=["source-1"],
            generation_invocation_id=f"generation-{checkpoint_index}",
            status="scored",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        response = CoachCardResponse(
            response_id=f"evidence-response-{checkpoint_index}",
            session_id=coach_session.session_id,
            card_id=card.card_id,
            turn_id=turn.turn_id,
            organization_id=coach_session.organization_id,
            learner_id=coach_session.learner_id,
            raw_answer_json={"answer_type": "text", "text": "先澄清再回应"},
            client_token_hash=str(checkpoint_index + 1) * 64,
            answer_hash=str(checkpoint_index + 4) * 64,
            status="evaluated",
            score_percent=90,
            mastered=True,
            evaluation_json={"feedback": "达到要求", "missing_points": []},
            uncertainty=0.1,
            source_ref_ids_json=["source-1"],
            evaluation_kind="ai",
            invocation_id=f"evaluation-{checkpoint_index}",
            prompt_template_id="coach-answer-evaluation",
            prompt_revision_id="coach-answer-evaluation-v1",
            prompt_contract_hash=f"sha256:{'a' * 64}",
            model_routing_profile_id="foundation_coach_answer_evaluation-models",
            model_routing_revision_id=("foundation_coach_answer_evaluation-models-v1"),
            submitted_at=datetime.now(UTC),
            evaluated_at=datetime.now(UTC),
        )
        test_db.add_all([turn, card, response])
    await test_db.flush()
    coach_session.checkpoint_index = 2
    coach_session.cycle_no = 0
    coach_session.active_cycle_id = cycles[2].cycle_id
    coach_session.active_task_id = None
    coach_session.status = "checkpoint_mastered"
    await test_db.flush([coach_session])


@pytest.mark.asyncio
async def test_outcome_is_persisted_only_after_all_three_checkpoints_with_lineage(
    test_db: Any,
    test_user: Any,
) -> None:
    runtime, _, outcomes, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    await _seed_mastered_evidence(test_db, coach_session)

    completed = await runtime.continue_training(
        organization_id="org-1",
        learner_id=str(test_user.user_id),
        attempt_id=coach_session.attempt_id,
        expected_version=coach_session.version,
        idempotency_key="complete-coach-three-checkpoints",
        trace_id="trace-complete",
    )

    outcome = await test_db.scalar(
        select(CoachOutcome).where(CoachOutcome.session_id == coach_session.session_id)
    )
    assert completed.status == "completed"
    assert outcome is not None
    assert len(outcome.checkpoint_results_json) == 3
    assert outcome.generic_activity_outcome_id == "generic-coach-outcome-1"
    assert len(outcome.lineage_json["responses"]) == 3
    assert outcome.lineage_json["responses"][0]["prompt_revision_id"] == (
        "coach-answer-evaluation-v1"
    )
    assert outcomes.payloads[0].assessment_result == "passed"
    assert "foundation_ready" not in outcomes.payloads[0].model_dump_json()


@pytest.mark.asyncio
async def test_human_help_governance_is_org_scoped_append_only_and_audited(
    test_db: Any,
    test_user: Any,
) -> None:
    _, _, _, coach_session = await _start(
        test_db,
        learner_id=str(test_user.user_id),
    )
    coach_session.status = "needs_human_help"
    coach_session.human_help_status = "open"
    coach_session.active_task_id = None
    coach_session.safe_error_message = "自动补练两轮后仍未达标"
    await test_db.flush([coach_session])
    service = CoachGovernanceService(test_db)
    actor = CoachReviewActor(
        organization_id="org-1",
        actor_id="reviewer-1",
        capabilities=frozenset({"newcomer.coach.review"}),
        trace_id="trace-review",
    )

    queue = await service.list_help_queue(actor=actor)
    assert [item.session_id for item in queue] == [coach_session.session_id]
    original_snapshot = json.loads(json.dumps(coach_session.context_snapshot_json))
    detail = await service.intervene(
        actor=actor,
        session_id=coach_session.session_id,
        payload=CoachHumanInterventionInput(
            action="add_guidance",
            reason="请先复习需求澄清方法",
            guidance="用目标、影响、约束三个问题重新组织回答。",
        ),
        expected_version=coach_session.version,
        idempotency_key="coach-guidance-1",
    )
    assert detail.version == coach_session.version
    assert coach_session.human_help_status == "open"
    assert coach_session.context_snapshot_json == original_snapshot

    await service.intervene(
        actor=actor,
        session_id=coach_session.session_id,
        payload=CoachHumanInterventionInput(
            action="assign_learning",
            reason="需要补充学习",
            target_resource_id="learning-unit-revision-1",
        ),
        expected_version=coach_session.version,
        idempotency_key="coach-assign-learning-1",
    )
    interventions = list(
        (
            await test_db.execute(
                select(CoachHumanIntervention)
                .where(CoachHumanIntervention.session_id == coach_session.session_id)
                .order_by(CoachHumanIntervention.created_at)
            )
        ).scalars()
    )
    assert [item.action for item in interventions] == [
        "add_guidance",
        "assign_learning",
    ]
    assert coach_session.human_help_status == "resolved"

    with pytest.raises(AICoachError) as cross_org:
        await service.get_help_detail(
            actor=actor.model_copy(update={"organization_id": "org-2"}),
            session_id=coach_session.session_id,
        )
    assert cross_org.value.status_code == 404
    with pytest.raises(AICoachError) as denied:
        await service.list_help_queue(
            actor=actor.model_copy(update={"capabilities": frozenset()}),
        )
    assert denied.value.status_code == 403
