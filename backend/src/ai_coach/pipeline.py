"""Save/commit/AI/apply processors for structured Coach durable tasks."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_coach.contracts import (
    CoachAnswerEvaluationInput,
    CoachAnswerEvaluationOutput,
    CoachCardGenerationInput,
    CoachCardGenerationOutput,
    CoachContextSnapshot,
    CoachExplanationAIInput,
    CoachExplanationAIOutput,
    CoachProfileSnapshot,
)
from ai_coach.errors import AICoachError
from ai_coach.models import (
    CoachAssistance,
    CoachCardResponse,
    CoachRemediationCycle,
    CoachSession,
    CoachTrainingCard,
    CoachTurn,
)
from ai_platform import (
    AIInvocationResult,
    AIInvocationStatus,
    BudgetScope,
    DataClassification,
    GovernedAIRequest,
    PromptCompilationService,
)
from ai_platform.prompting import PromptPreviewRequest


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class CoachGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    activity_id: str
    cycle_id: str
    card_ids: tuple[str, ...]
    invocation_id: str
    status: str


class CoachGenerationPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_id: str
    task_id: str
    request: GovernedAIRequest


class CoachEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    activity_id: str
    response_id: str
    card_id: str
    score_percent: float
    mastered: bool
    session_status: str
    invocation_id: str | None


class CoachEvaluationPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    response_id: str
    task_id: str
    request: GovernedAIRequest


class CoachAssistanceResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str
    activity_id: str
    assistance_id: str
    status: str
    invocation_id: str | None


class CoachAssistancePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assistance_id: str
    task_id: str
    request: GovernedAIRequest


class CoachCardGenerationProcessor:
    def __init__(
        self,
        session: AsyncSession,
        *,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session = session
        self._prompt_compiler = prompt_compiler

    async def prepare_cycle(
        self,
        *,
        cycle_id: str,
        task_id: str,
    ) -> CoachGenerationPlan | CoachGenerationResult:
        cycle = await self._load_cycle(cycle_id, for_update=True)
        coach_session = await self._load_session(cycle.session_id, for_update=True)
        cards = await self._cards(cycle.cycle_id)
        if cycle.status in {"active", "mastered", "completed", "remediation_needed"}:
            if not cards:
                self._conflict("已完成生成的补练轮次缺少训练卡。")
            return CoachGenerationResult(
                session_id=coach_session.session_id,
                activity_id=coach_session.activity_id,
                cycle_id=cycle.cycle_id,
                card_ids=tuple(item.card_id for item in cards),
                invocation_id=cycle.generation_invocation_id or "",
                status=coach_session.status,
            )
        if cycle.generation_task_id != task_id:
            self._conflict("任务与当前训练卡生成轮次不匹配。")
        if cycle.status not in {"generating", "failed"}:
            self._conflict("当前补练轮次不能生成训练卡。")
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        checkpoint = profile.checkpoints[cycle.checkpoint_index]
        ai_contract = profile.ai.card_generation
        input_model = CoachCardGenerationInput(
            profile_revision_id=coach_session.profile_revision_id,
            session_id=coach_session.session_id,
            checkpoint=checkpoint,
            cycle_no=cycle.cycle_no,
            card_count_min=profile.remediation_policy.cards_per_cycle_min,
            card_count_max=profile.remediation_policy.cards_per_cycle_max,
            allowed_card_types=profile.card_type_whitelist,
            context=context,
            remediation_inputs=tuple(cycle.remediation_inputs_json),
        )
        input_payload = input_model.model_dump(mode="json")
        variables = {
            "profile_json": json.dumps(
                profile.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
            ),
            "checkpoint_json": json.dumps(
                checkpoint.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ),
            "context_json": json.dumps(
                context.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
            ),
            "cycle_no": cycle.cycle_no,
            "remediation_inputs_json": json.dumps(
                cycle.remediation_inputs_json, ensure_ascii=False, sort_keys=True
            ),
        }
        compiled = await self._prompt_compiler.preview(
            PromptPreviewRequest(
                template_id=ai_contract.prompt_template_id,
                revision_id=ai_contract.prompt_revision_id,
                business_purpose=ai_contract.business_purpose,
                input_schema_version=ai_contract.input_schema_version,
                output_schema_version=ai_contract.output_schema_version,
                variables=variables,
                runtime_consumer="ai_coach.card_generation.v1",
                model_routing_revision_id=ai_contract.model_routing_revision_id,
            )
        )
        cycle.status = "generating"
        cycle.updated_at = _now()
        coach_session.status = "preparing"
        coach_session.active_task_id = task_id
        coach_session.failure_stage = None
        coach_session.error_code = None
        coach_session.safe_error_message = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([cycle, coach_session])
        return CoachGenerationPlan(
            cycle_id=cycle.cycle_id,
            task_id=task_id,
            request=GovernedAIRequest(
                business_purpose=ai_contract.business_purpose,
                task_id=task_id,
                organization_id=coach_session.organization_id,
                actor_id=coach_session.learner_id,
                object_type="coach_remediation_cycle",
                object_id=cycle.cycle_id,
                prompt_template_id=ai_contract.prompt_template_id,
                prompt_revision_id=ai_contract.prompt_revision_id,
                prompt_contract_hash=compiled.contract_hash,
                model_routing_profile_id=ai_contract.model_routing_profile_id,
                model_routing_revision_id=ai_contract.model_routing_revision_id,
                input_schema_version=ai_contract.input_schema_version,
                output_schema_version=ai_contract.output_schema_version,
                input_payload=input_payload,
                prompt_variables=variables,
                idempotency_key=f"coach-card-generation:{cycle.cycle_id}:{task_id}",
                data_classification=DataClassification.CONFIDENTIAL,
                trace_id=task_id,
                correlation_id=coach_session.session_id,
                causation_id=cycle.cycle_id,
                runtime_consumer="ai_coach.card_generation.v1",
                timeout_policy_ref=ai_contract.timeout_policy_ref,
                retry_policy_ref=ai_contract.retry_policy_ref,
                budget_scope=BudgetScope.ORGANIZATION,
                formal_scoring=False,
                allow_fallback=ai_contract.allow_fallback,
            ),
        )

    async def apply_result(
        self,
        *,
        plan: CoachGenerationPlan,
        result: AIInvocationResult,
    ) -> CoachGenerationResult:
        cycle = await self._load_cycle(plan.cycle_id, for_update=True)
        coach_session = await self._load_session(cycle.session_id, for_update=True)
        cards = await self._cards(cycle.cycle_id)
        if cycle.status == "active" and cards:
            return CoachGenerationResult(
                session_id=coach_session.session_id,
                activity_id=coach_session.activity_id,
                cycle_id=cycle.cycle_id,
                card_ids=tuple(item.card_id for item in cards),
                invocation_id=cycle.generation_invocation_id or result.invocation_id,
                status=coach_session.status,
            )
        if cycle.generation_task_id != plan.task_id:
            self._conflict("任务与当前训练卡生成轮次不匹配。")
        if (
            result.status
            not in {
                AIInvocationStatus.SUCCEEDED,
                AIInvocationStatus.PARTIAL,
            }
            or result.validated_output is None
        ):
            await self._fail_generation(cycle, coach_session, result)
        try:
            output = CoachCardGenerationOutput.model_validate(result.validated_output)
        except ValidationError:
            await self._fail_invalid_generation(
                cycle,
                coach_session,
                "训练卡输出不符合结构化契约。",
            )
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        card_count = len(output.cards)
        policy = profile.remediation_policy
        if not policy.cards_per_cycle_min <= card_count <= policy.cards_per_cycle_max:
            await self._fail_invalid_generation(
                cycle,
                coach_session,
                "生成的训练卡数量不符合当前训练策略。",
            )
        known_refs = {item.ref_id for item in context.references}
        prepared_cards: list[tuple[dict[str, Any], dict[str, Any], str, list[str]]] = []
        for generated_card in output.cards:
            if generated_card.card_type not in profile.card_type_whitelist:
                await self._fail_invalid_generation(
                    cycle,
                    coach_session,
                    "模型返回了未启用的训练卡类型。",
                )
            if not set(generated_card.source_ref_ids).issubset(known_refs):
                await self._fail_invalid_generation(
                    cycle,
                    coach_session,
                    "训练卡引用了本轮上下文之外的内容。",
                )
            try:
                prepared_cards.append(_split_card(generated_card))
            except AICoachError as exc:
                await self._fail_invalid_generation(
                    cycle,
                    coach_session,
                    exc.message,
                )
        sequence_start = int(
            await self._session.scalar(
                select(func.coalesce(func.max(CoachTurn.sequence), 0)).where(
                    CoachTurn.session_id == coach_session.session_id
                )
            )
            or 0
        )
        created_cards: list[CoachTrainingCard] = []
        for position, prepared in enumerate(prepared_cards, start=1):
            public_payload, evaluation_spec, evaluation_mode, source_refs = prepared
            turn = CoachTurn(
                turn_id=_id(),
                session_id=coach_session.session_id,
                cycle_id=cycle.cycle_id,
                organization_id=coach_session.organization_id,
                checkpoint_index=cycle.checkpoint_index,
                cycle_no=cycle.cycle_no,
                sequence=sequence_start + position,
                cycle_position=position,
                status="current" if position == 1 else "pending",
                created_at=_now(),
                updated_at=_now(),
            )
            card_row = CoachTrainingCard(
                card_id=_id(),
                session_id=coach_session.session_id,
                cycle_id=cycle.cycle_id,
                turn_id=turn.turn_id,
                organization_id=coach_session.organization_id,
                card_type=str(public_payload["card_type"]),
                evaluation_mode=evaluation_mode,
                public_payload_json=public_payload,
                evaluation_spec_json=evaluation_spec,
                source_ref_ids_json=source_refs,
                generation_invocation_id=result.invocation_id,
                status="current" if position == 1 else "pending",
                created_at=_now(),
                updated_at=_now(),
            )
            self._session.add_all([turn, card_row])
            created_cards.append(card_row)
        cycle.status = "active"
        cycle.generation_strategy = output.generation_strategy
        cycle.generation_invocation_id = result.invocation_id
        cycle.updated_at = _now()
        coach_session.status = "awaiting_answer"
        coach_session.active_task_id = None
        coach_session.failure_stage = None
        coach_session.error_code = None
        coach_session.safe_error_message = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([cycle, coach_session, *created_cards])
        return CoachGenerationResult(
            session_id=coach_session.session_id,
            activity_id=coach_session.activity_id,
            cycle_id=cycle.cycle_id,
            card_ids=tuple(item.card_id for item in created_cards),
            invocation_id=result.invocation_id,
            status=coach_session.status,
        )

    async def _fail_generation(
        self,
        cycle: CoachRemediationCycle,
        coach_session: CoachSession,
        result: AIInvocationResult,
    ) -> None:
        failure = result.failure
        cycle.status = "failed"
        cycle.generation_invocation_id = result.invocation_id
        cycle.updated_at = _now()
        coach_session.status = "failed_recoverable"
        coach_session.failure_stage = "card_generation"
        coach_session.error_code = (
            failure.code if failure else "coach_generation_failed"
        )
        coach_session.safe_error_message = (
            "训练卡准备失败，已保留当前进度，可稍后重试。"
        )
        coach_session.active_task_id = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([cycle, coach_session])
        raise AICoachError(
            "[COACH_CARD_GENERATION_FAILED]",
            coach_session.safe_error_message,
            503,
            details={"retryable": bool(failure and failure.retryable)},
        )

    async def _fail_invalid_generation(
        self,
        cycle: CoachRemediationCycle,
        coach_session: CoachSession,
        message: str,
    ) -> None:
        cycle.status = "failed"
        cycle.updated_at = _now()
        coach_session.status = "failed_recoverable"
        coach_session.failure_stage = "card_generation"
        coach_session.error_code = "coach_generation_output_invalid"
        coach_session.safe_error_message = message
        coach_session.active_task_id = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([cycle, coach_session])
        raise AICoachError(
            "[COACH_CARD_GENERATION_OUTPUT_INVALID]",
            message,
            422,
        )

    async def _load_cycle(
        self, cycle_id: str, *, for_update: bool
    ) -> CoachRemediationCycle:
        query = select(CoachRemediationCycle).where(
            CoachRemediationCycle.cycle_id == cycle_id
        )
        if for_update:
            query = query.with_for_update()
        cycle = await self._session.scalar(query.limit(1))
        if cycle is None:
            raise AICoachError("[COACH_CYCLE_NOT_FOUND]", "训练轮次不存在。", 404)
        return cycle

    async def _load_session(self, session_id: str, *, for_update: bool) -> CoachSession:
        query = select(CoachSession).where(CoachSession.session_id == session_id)
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None:
            raise AICoachError("[COACH_SESSION_NOT_FOUND]", "训练会话不存在。", 404)
        return row

    async def _cards(self, cycle_id: str) -> list[CoachTrainingCard]:
        rows = (
            await self._session.execute(
                select(CoachTrainingCard)
                .join(CoachTurn, CoachTurn.turn_id == CoachTrainingCard.turn_id)
                .where(CoachTrainingCard.cycle_id == cycle_id)
                .order_by(CoachTurn.cycle_position)
            )
        ).scalars()
        return list(rows)

    @staticmethod
    def _conflict(message: str) -> None:
        raise AICoachError("[COACH_TASK_STATE_CONFLICT]", message, 409)


class CoachAnswerEvaluationProcessor:
    def __init__(
        self,
        session: AsyncSession,
        *,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session = session
        self._prompt_compiler = prompt_compiler

    async def prepare_response(
        self,
        *,
        response_id: str,
        task_id: str,
    ) -> CoachEvaluationPlan | CoachEvaluationResult:
        response = await self._load_response(response_id, for_update=True)
        card = await self._load_card(response.card_id)
        coach_session = await self._load_session(response.session_id, for_update=True)
        if response.status == "evaluated":
            return _evaluation_result(response, coach_session)
        if response.evaluation_task_id != task_id:
            self._conflict("任务与当前答案评估不匹配。")
        if response.status not in {"saved", "evaluating", "failed_recoverable"}:
            self._conflict("当前答案不能进行评估。")
        if card.evaluation_mode != "ai":
            self._conflict("确定性训练卡不能调用模型评分。")
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        context_by_id = {item.ref_id: item for item in context.references}
        sources = tuple(
            context_by_id[ref_id]
            for ref_id in card.source_ref_ids_json
            if ref_id in context_by_id
        )
        if len(sources) != len(card.source_ref_ids_json):
            self._conflict("训练卡来源已经不可用，不能继续评分。")
        ai_contract = profile.ai.answer_evaluation
        input_model = CoachAnswerEvaluationInput(
            session_id=coach_session.session_id,
            card_id=card.card_id,
            card_type=card.card_type,
            prompt=str(card.public_payload_json["prompt"]),
            public_card=dict(card.public_payload_json),
            reference_points=tuple(card.evaluation_spec_json["reference_points"]),
            learner_answer=response.raw_answer_json,
            sources=sources,
        )
        input_payload = input_model.model_dump(mode="json")
        variables = {
            "card_json": json.dumps(
                card.public_payload_json, ensure_ascii=False, sort_keys=True
            ),
            "answer_json": json.dumps(
                response.raw_answer_json, ensure_ascii=False, sort_keys=True
            ),
            "reference_points_json": json.dumps(
                card.evaluation_spec_json["reference_points"],
                ensure_ascii=False,
                sort_keys=True,
            ),
            "sources_json": json.dumps(
                [item.model_dump(mode="json") for item in sources],
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
        compiled = await self._prompt_compiler.preview(
            PromptPreviewRequest(
                template_id=ai_contract.prompt_template_id,
                revision_id=ai_contract.prompt_revision_id,
                business_purpose=ai_contract.business_purpose,
                input_schema_version=ai_contract.input_schema_version,
                output_schema_version=ai_contract.output_schema_version,
                variables=variables,
                runtime_consumer="ai_coach.answer_evaluation.v1",
                model_routing_revision_id=ai_contract.model_routing_revision_id,
            )
        )
        response.status = "evaluating"
        response.error_code = None
        response.safe_error_message = None
        coach_session.status = "evaluating"
        coach_session.active_task_id = task_id
        coach_session.failure_stage = None
        coach_session.error_code = None
        coach_session.safe_error_message = None
        coach_session.version += 1
        coach_session.updated_at = _now()
        await self._session.flush([response, coach_session])
        return CoachEvaluationPlan(
            response_id=response.response_id,
            task_id=task_id,
            request=GovernedAIRequest(
                business_purpose=ai_contract.business_purpose,
                task_id=task_id,
                organization_id=coach_session.organization_id,
                actor_id=coach_session.learner_id,
                object_type="coach_card_response",
                object_id=response.response_id,
                prompt_template_id=ai_contract.prompt_template_id,
                prompt_revision_id=ai_contract.prompt_revision_id,
                prompt_contract_hash=compiled.contract_hash,
                model_routing_profile_id=ai_contract.model_routing_profile_id,
                model_routing_revision_id=ai_contract.model_routing_revision_id,
                input_schema_version=ai_contract.input_schema_version,
                output_schema_version=ai_contract.output_schema_version,
                input_payload=input_payload,
                prompt_variables=variables,
                idempotency_key=f"coach-evaluation:{response.response_id}:{task_id}",
                data_classification=DataClassification.CONFIDENTIAL,
                trace_id=task_id,
                correlation_id=coach_session.session_id,
                causation_id=response.response_id,
                runtime_consumer="ai_coach.answer_evaluation.v1",
                timeout_policy_ref=ai_contract.timeout_policy_ref,
                retry_policy_ref=ai_contract.retry_policy_ref,
                budget_scope=BudgetScope.ACTOR,
                formal_scoring=True,
                allow_fallback=ai_contract.allow_fallback,
            ),
        )

    async def apply_result(
        self,
        *,
        plan: CoachEvaluationPlan,
        result: AIInvocationResult,
    ) -> CoachEvaluationResult:
        response = await self._load_response(plan.response_id, for_update=True)
        coach_session = await self._load_session(response.session_id, for_update=True)
        if response.status == "evaluated":
            return _evaluation_result(response, coach_session)
        if response.evaluation_task_id != plan.task_id:
            self._conflict("任务与当前答案评估不匹配。")
        if (
            result.status
            not in {
                AIInvocationStatus.SUCCEEDED,
                AIInvocationStatus.PARTIAL,
            }
            or result.validated_output is None
        ):
            failure = result.failure
            response.status = "failed_recoverable"
            response.invocation_id = result.invocation_id
            response.error_code = failure.code if failure else "coach_evaluation_failed"
            response.safe_error_message = "答案已经保存，但反馈生成失败，可稍后重试。"
            coach_session.status = "failed_recoverable"
            coach_session.active_task_id = None
            coach_session.failure_stage = "answer_evaluation"
            coach_session.error_code = response.error_code
            coach_session.safe_error_message = response.safe_error_message
            coach_session.version += 1
            coach_session.updated_at = _now()
            await self._session.flush([response, coach_session])
            raise AICoachError(
                "[COACH_ANSWER_EVALUATION_FAILED]",
                response.safe_error_message,
                503,
                details={"retryable": bool(failure and failure.retryable)},
            )
        try:
            output = CoachAnswerEvaluationOutput.model_validate(
                result.validated_output
            )
        except ValidationError:
            response.status = "failed_recoverable"
            response.error_code = "coach_evaluation_output_invalid"
            response.safe_error_message = "答案已经保存，但反馈格式无效，可稍后重试。"
            coach_session.status = "failed_recoverable"
            coach_session.active_task_id = None
            coach_session.failure_stage = "answer_evaluation"
            coach_session.error_code = response.error_code
            coach_session.safe_error_message = response.safe_error_message
            coach_session.version += 1
            coach_session.updated_at = _now()
            await self._session.flush([response, coach_session])
            raise AICoachError(
                "[COACH_ANSWER_EVALUATION_OUTPUT_INVALID]",
                response.safe_error_message,
                422,
            ) from None
        card = await self._load_card(response.card_id)
        if not set(output.source_ref_ids).issubset(set(card.source_ref_ids_json)):
            response.status = "failed_recoverable"
            response.error_code = "coach_evaluation_source_invalid"
            response.safe_error_message = "反馈依据超出本轮学习内容，已停止采用该结果。"
            coach_session.status = "failed_recoverable"
            coach_session.active_task_id = None
            coach_session.failure_stage = "answer_evaluation"
            coach_session.error_code = response.error_code
            coach_session.safe_error_message = response.safe_error_message
            coach_session.version += 1
            coach_session.updated_at = _now()
            await self._session.flush([response, coach_session])
            raise AICoachError(
                "[COACH_EVALUATION_SOURCE_INVALID]",
                response.safe_error_message,
                422,
            )
        evaluation = output.model_dump(mode="json")
        evaluation["reported_mastered"] = evaluation.pop("mastered")
        evaluation["result_source"] = "ai_inference"
        response.invocation_id = result.invocation_id
        response.prompt_template_id = result.prompt_template_id
        response.prompt_revision_id = result.prompt_revision_id
        response.prompt_contract_hash = result.prompt_contract_hash
        response.model_routing_profile_id = result.model_routing_profile_id
        response.model_routing_revision_id = result.model_routing_revision_id
        return await finalize_response(
            self._session,
            response=response,
            coach_session=coach_session,
            score_percent=output.score_percent,
            uncertainty=output.uncertainty,
            source_ref_ids=list(output.source_ref_ids),
            evaluation=evaluation,
            evaluation_kind="ai",
        )

    async def _load_response(
        self, response_id: str, *, for_update: bool
    ) -> CoachCardResponse:
        query = select(CoachCardResponse).where(
            CoachCardResponse.response_id == response_id
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None:
            raise AICoachError("[COACH_RESPONSE_NOT_FOUND]", "训练回答不存在。", 404)
        return row

    async def _load_session(self, session_id: str, *, for_update: bool) -> CoachSession:
        query = select(CoachSession).where(CoachSession.session_id == session_id)
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None:
            raise AICoachError("[COACH_SESSION_NOT_FOUND]", "训练会话不存在。", 404)
        return row

    async def _load_card(self, card_id: str) -> CoachTrainingCard:
        row = await self._session.get(CoachTrainingCard, card_id)
        if row is None:
            raise AICoachError("[COACH_CARD_NOT_FOUND]", "训练卡不存在。", 404)
        return row

    @staticmethod
    def _conflict(message: str) -> None:
        raise AICoachError("[COACH_TASK_STATE_CONFLICT]", message, 409)


class CoachAssistanceProcessor:
    def __init__(
        self,
        session: AsyncSession,
        *,
        prompt_compiler: PromptCompilationService,
    ) -> None:
        self._session = session
        self._prompt_compiler = prompt_compiler

    async def prepare_assistance(
        self,
        *,
        assistance_id: str,
        task_id: str,
    ) -> CoachAssistancePlan | CoachAssistanceResult:
        assistance = await self._load(assistance_id, for_update=True)
        coach_session = await self._session.get(CoachSession, assistance.session_id)
        card = await self._session.get(CoachTrainingCard, assistance.card_id)
        if coach_session is None or card is None:
            raise AICoachError(
                "[COACH_ASSISTANCE_CONTEXT_NOT_FOUND]",
                "当前讲解所需的训练内容不存在。",
                404,
            )
        if assistance.status == "completed":
            return CoachAssistanceResult(
                session_id=coach_session.session_id,
                activity_id=coach_session.activity_id,
                assistance_id=assistance.assistance_id,
                status=assistance.status,
                invocation_id=assistance.invocation_id,
            )
        if assistance.task_id != task_id:
            raise AICoachError(
                "[COACH_TASK_STATE_CONFLICT]", "任务与当前讲解请求不匹配。", 409
            )
        profile = CoachProfileSnapshot.model_validate(
            coach_session.profile_snapshot_json
        )
        context = CoachContextSnapshot.model_validate(
            coach_session.context_snapshot_json
        )
        context_by_id = {item.ref_id: item for item in context.references}
        sources = tuple(
            context_by_id[ref_id]
            for ref_id in card.source_ref_ids_json
            if ref_id in context_by_id
        )
        response = await self._session.scalar(
            select(CoachCardResponse)
            .where(CoachCardResponse.card_id == card.card_id)
            .limit(1)
        )
        ai_contract = profile.ai.feedback_explanation
        input_model = CoachExplanationAIInput(
            session_id=coach_session.session_id,
            assistance_type=assistance.assistance_type,
            card=dict(card.public_payload_json),
            feedback=(
                dict(response.evaluation_json)
                if response is not None and response.evaluation_json is not None
                else None
            ),
            sources=sources,
        )
        input_payload = input_model.model_dump(mode="json")
        variables = {
            "assistance_type": assistance.assistance_type,
            "card_json": json.dumps(
                card.public_payload_json, ensure_ascii=False, sort_keys=True
            ),
            "feedback_json": json.dumps(
                input_payload.get("feedback"), ensure_ascii=False, sort_keys=True
            ),
            "sources_json": json.dumps(
                [item.model_dump(mode="json") for item in sources],
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
        compiled = await self._prompt_compiler.preview(
            PromptPreviewRequest(
                template_id=ai_contract.prompt_template_id,
                revision_id=ai_contract.prompt_revision_id,
                business_purpose=ai_contract.business_purpose,
                input_schema_version=ai_contract.input_schema_version,
                output_schema_version=ai_contract.output_schema_version,
                variables=variables,
                runtime_consumer="ai_coach.feedback_explanation.v1",
                model_routing_revision_id=ai_contract.model_routing_revision_id,
            )
        )
        assistance.status = "queued"
        await self._session.flush([assistance])
        return CoachAssistancePlan(
            assistance_id=assistance.assistance_id,
            task_id=task_id,
            request=GovernedAIRequest(
                business_purpose=ai_contract.business_purpose,
                task_id=task_id,
                organization_id=coach_session.organization_id,
                actor_id=coach_session.learner_id,
                object_type="coach_assistance",
                object_id=assistance.assistance_id,
                prompt_template_id=ai_contract.prompt_template_id,
                prompt_revision_id=ai_contract.prompt_revision_id,
                prompt_contract_hash=compiled.contract_hash,
                model_routing_profile_id=ai_contract.model_routing_profile_id,
                model_routing_revision_id=ai_contract.model_routing_revision_id,
                input_schema_version=ai_contract.input_schema_version,
                output_schema_version=ai_contract.output_schema_version,
                input_payload=input_payload,
                prompt_variables=variables,
                idempotency_key=(
                    f"coach-assistance:{assistance.assistance_id}:{task_id}"
                ),
                data_classification=DataClassification.CONFIDENTIAL,
                trace_id=task_id,
                correlation_id=coach_session.session_id,
                causation_id=assistance.assistance_id,
                runtime_consumer="ai_coach.feedback_explanation.v1",
                timeout_policy_ref=ai_contract.timeout_policy_ref,
                retry_policy_ref=ai_contract.retry_policy_ref,
                budget_scope=BudgetScope.ACTOR,
                formal_scoring=False,
                allow_fallback=ai_contract.allow_fallback,
            ),
        )

    async def apply_result(
        self,
        *,
        plan: CoachAssistancePlan,
        result: AIInvocationResult,
    ) -> CoachAssistanceResult:
        assistance = await self._load(plan.assistance_id, for_update=True)
        coach_session = await self._session.get(CoachSession, assistance.session_id)
        if coach_session is None:
            raise AICoachError(
                "[COACH_ASSISTANCE_CONTEXT_NOT_FOUND]",
                "当前讲解所需的训练会话不存在。",
                404,
            )
        if assistance.status == "completed":
            return CoachAssistanceResult(
                session_id=assistance.session_id,
                activity_id=coach_session.activity_id,
                assistance_id=assistance.assistance_id,
                status=assistance.status,
                invocation_id=assistance.invocation_id,
            )
        if (
            result.status
            not in {
                AIInvocationStatus.SUCCEEDED,
                AIInvocationStatus.PARTIAL,
            }
            or result.validated_output is None
        ):
            assistance.status = "failed_recoverable"
            assistance.error_code = (
                result.failure.code
                if result.failure is not None
                else "coach_assistance_failed"
            )
            assistance.invocation_id = result.invocation_id
            await self._session.flush([assistance])
            raise AICoachError(
                "[COACH_ASSISTANCE_FAILED]",
                "讲解生成失败，训练进度未受影响，可稍后重试。",
                503,
                details={
                    "retryable": bool(result.failure and result.failure.retryable)
                },
            )
        try:
            output = CoachExplanationAIOutput.model_validate(result.validated_output)
        except ValidationError:
            assistance.status = "failed_recoverable"
            assistance.error_code = "coach_assistance_output_invalid"
            assistance.invocation_id = result.invocation_id
            await self._session.flush([assistance])
            raise AICoachError(
                "[COACH_ASSISTANCE_OUTPUT_INVALID]",
                "讲解格式无效，训练进度未受影响，可稍后重试。",
                422,
            ) from None
        card = await self._session.get(CoachTrainingCard, assistance.card_id)
        if card is None or not set(output.source_ref_ids).issubset(
            set(card.source_ref_ids_json)
        ):
            assistance.status = "failed_recoverable"
            assistance.error_code = "coach_assistance_source_invalid"
            await self._session.flush([assistance])
            raise AICoachError(
                "[COACH_ASSISTANCE_SOURCE_INVALID]",
                "讲解依据超出本轮学习内容，已停止采用该结果。",
                422,
            )
        assistance.status = "completed"
        assistance.result_json = output.model_dump(mode="json")
        assistance.source_ref_ids_json = list(output.source_ref_ids)
        assistance.invocation_id = result.invocation_id
        assistance.prompt_revision_id = result.prompt_revision_id
        assistance.model_routing_revision_id = result.model_routing_revision_id
        assistance.error_code = None
        assistance.completed_at = _now()
        await self._session.flush([assistance])
        return CoachAssistanceResult(
            session_id=assistance.session_id,
            activity_id=coach_session.activity_id,
            assistance_id=assistance.assistance_id,
            status=assistance.status,
            invocation_id=assistance.invocation_id,
        )

    async def _load(self, assistance_id: str, *, for_update: bool) -> CoachAssistance:
        query = select(CoachAssistance).where(
            CoachAssistance.assistance_id == assistance_id
        )
        if for_update:
            query = query.with_for_update()
        row = await self._session.scalar(query.limit(1))
        if row is None:
            raise AICoachError("[COACH_ASSISTANCE_NOT_FOUND]", "讲解请求不存在。", 404)
        return row


async def finalize_response(
    session: AsyncSession,
    *,
    response: CoachCardResponse,
    coach_session: CoachSession,
    score_percent: float,
    uncertainty: float,
    source_ref_ids: list[str],
    evaluation: dict[str, Any],
    evaluation_kind: str,
) -> CoachEvaluationResult:
    card = await session.get(CoachTrainingCard, response.card_id)
    turn = await session.get(CoachTurn, response.turn_id)
    cycle = await session.get(CoachRemediationCycle, card.cycle_id if card else "")
    if card is None or turn is None or cycle is None:
        raise AICoachError(
            "[COACH_RESPONSE_CONTEXT_NOT_FOUND]",
            "训练回答关联的卡片或轮次不存在。",
            409,
        )
    profile = CoachProfileSnapshot.model_validate(coach_session.profile_snapshot_json)
    mastered = (
        score_percent >= profile.mastery_rule.threshold_percent
        and uncertainty <= profile.mastery_rule.maximum_uncertainty
    )
    response.status = "evaluated"
    response.score_percent = score_percent
    response.mastered = mastered
    response.evaluation_json = evaluation
    response.uncertainty = uncertainty
    response.source_ref_ids_json = source_ref_ids
    response.evaluation_kind = evaluation_kind
    response.error_code = None
    response.safe_error_message = None
    response.evaluated_at = _now()
    card.status = "scored"
    card.updated_at = _now()
    turn.status = "scored"
    turn.updated_at = _now()
    pending_count = int(
        await session.scalar(
            select(func.count(CoachTrainingCard.card_id))
            .where(CoachTrainingCard.cycle_id == cycle.cycle_id)
            .where(CoachTrainingCard.status == "pending")
        )
        or 0
    )
    if pending_count:
        coach_session.status = "feedback_ready"
    else:
        responses = (
            (
                await session.execute(
                    select(CoachCardResponse)
                    .join(
                        CoachTrainingCard,
                        CoachTrainingCard.card_id == CoachCardResponse.card_id,
                    )
                    .where(CoachTrainingCard.cycle_id == cycle.cycle_id)
                    .where(CoachCardResponse.status == "evaluated")
                )
            )
            .scalars()
            .all()
        )
        if len(responses) < profile.mastery_rule.minimum_scored_cards:
            raise AICoachError(
                "[COACH_CYCLE_INCOMPLETE]",
                "当前训练轮次的有效评分不足，不能完成掌握判断。",
                409,
            )
        average = sum(float(item.score_percent or 0) for item in responses) / len(
            responses
        )
        maximum_uncertainty = max(float(item.uncertainty or 0) for item in responses)
        cycle.score_percent = average
        cycle.maximum_uncertainty = maximum_uncertainty
        cycle.result_summary_json = {
            "card_count": len(responses),
            "mastered_card_count": sum(item.mastered is True for item in responses),
            "missing_points": list(
                dict.fromkeys(
                    str(point)
                    for item in responses
                    for point in (item.evaluation_json or {}).get("missing_points", [])
                )
            ),
        }
        cycle.completed_at = _now()
        if maximum_uncertainty > profile.mastery_rule.maximum_uncertainty:
            cycle.status = "needs_human_help"
            coach_session.status = "needs_human_help"
            coach_session.human_help_status = "open"
            coach_session.human_help_next_action_json = None
        elif average >= profile.mastery_rule.threshold_percent:
            cycle.status = "mastered"
            coach_session.status = "checkpoint_mastered"
        elif cycle.cycle_no < profile.remediation_policy.maximum_automatic_cycles:
            cycle.status = "remediation_needed"
            coach_session.status = "remediation_required"
        else:
            cycle.status = "needs_human_help"
            coach_session.status = "needs_human_help"
            coach_session.human_help_status = "open"
            coach_session.human_help_next_action_json = None
        cycle.updated_at = _now()
    coach_session.active_task_id = None
    coach_session.failure_stage = None
    coach_session.error_code = None
    coach_session.safe_error_message = None
    coach_session.version += 1
    coach_session.updated_at = _now()
    await session.flush([response, card, turn, cycle, coach_session])
    return _evaluation_result(response, coach_session)


def deterministic_evaluation(
    *,
    card: CoachTrainingCard,
    answer: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    if card.evaluation_mode != "deterministic":
        raise AICoachError(
            "[COACH_CARD_EVALUATION_MODE_INVALID]",
            "当前训练卡不能使用规则评分。",
            409,
        )
    expected: list[str]
    actual: list[str]
    if card.card_type in {"single_choice", "multiple_choice", "scenario_choice"}:
        if answer.get("answer_type") != "choice":
            raise AICoachError(
                "[COACH_ANSWER_TYPE_INVALID]", "请选择当前训练卡要求的答案。", 422
            )
        expected = [
            str(item) for item in card.evaluation_spec_json["correct_option_ids"]
        ]
        actual = [str(item) for item in answer.get("selected_option_ids", [])]
        matched = set(actual) == set(expected)
    elif card.card_type == "ordering":
        if answer.get("answer_type") != "ordering":
            raise AICoachError(
                "[COACH_ANSWER_TYPE_INVALID]", "请按要求排列全部步骤。", 422
            )
        expected = [
            str(item) for item in card.evaluation_spec_json["correct_order_ids"]
        ]
        actual = [str(item) for item in answer.get("ordered_item_ids", [])]
        matched = actual == expected
    else:
        raise AICoachError(
            "[COACH_CARD_EVALUATION_MODE_INVALID]",
            "当前训练卡需要结构化语言评估。",
            409,
        )
    score = 100.0 if matched else 0.0
    return score, {
        "result_source": "rule",
        "score_percent": score,
        "evidence_from_answer": actual,
        "missing_points": [] if matched else ["答案与当前学习依据不一致"],
        "misconception": None,
        "feedback": "回答符合要求。" if matched else "请重新对照学习依据辨析关键点。",
        "improvement_action": "继续下一张训练卡。"
        if matched
        else "复习当前依据后再进行补练。",
        "next_suggestion": "继续训练" if matched else "完成针对性补练",
        "uncertainty": 0.0,
        "source_ref_ids": list(card.source_ref_ids_json),
    }


def _split_card(card: Any) -> tuple[dict[str, Any], dict[str, Any], str, list[str]]:
    raw = card.model_dump(mode="json")
    _assert_safe_card_content(raw)
    source_refs = [str(item) for item in raw["source_ref_ids"]]
    if card.card_type in {"single_choice", "multiple_choice", "scenario_choice"}:
        correct = [str(item) for item in raw.pop("correct_option_ids")]
        option_ids = [str(item["option_id"]) for item in raw["options"]]
        if len(option_ids) != len(set(option_ids)) or not set(correct).issubset(
            set(option_ids)
        ):
            raise AICoachError(
                "[COACH_CARD_SCHEMA_INVALID]",
                "选择训练卡的选项或答案配置无效。",
                422,
            )
        evaluation = {"correct_option_ids": correct}
        mode = "deterministic"
    elif card.card_type == "ordering":
        correct_order = [str(item) for item in raw.pop("correct_order_ids")]
        item_ids = [str(item["item_id"]) for item in raw["items"]]
        if len(item_ids) != len(set(item_ids)) or set(correct_order) != set(item_ids):
            raise AICoachError(
                "[COACH_CARD_SCHEMA_INVALID]",
                "排序训练卡的步骤配置无效。",
                422,
            )
        evaluation = {"correct_order_ids": correct_order}
        mode = "deterministic"
    else:
        reference_points = [str(item) for item in raw.pop("reference_points")]
        evaluation = {"reference_points": reference_points}
        mode = "ai"
    return raw, evaluation, mode, source_refs


_HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_EXTERNAL_INSTRUCTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "忽略以上指令",
    "忽略之前的指令",
    "系统提示词",
    "javascript:",
    "data:text/html",
)


def _assert_safe_card_content(payload: Any) -> None:
    values: list[str] = []
    if isinstance(payload, str):
        values.append(payload)
    elif isinstance(payload, dict):
        for value in payload.values():
            _assert_safe_card_content(value)
        return
    elif isinstance(payload, list):
        for value in payload:
            _assert_safe_card_content(value)
        return
    for value in values:
        lowered = value.casefold()
        if _HTML_TAG.search(value) or any(
            marker in lowered for marker in _EXTERNAL_INSTRUCTION_MARKERS
        ):
            raise AICoachError(
                "[COACH_CARD_CONTENT_UNSAFE]",
                "训练卡包含不允许的标记或外部指令。",
                422,
            )


def _evaluation_result(
    response: CoachCardResponse,
    coach_session: CoachSession,
) -> CoachEvaluationResult:
    return CoachEvaluationResult(
        session_id=coach_session.session_id,
        activity_id=coach_session.activity_id,
        response_id=response.response_id,
        card_id=response.card_id,
        score_percent=float(response.score_percent or 0),
        mastered=response.mastered is True,
        session_status=coach_session.status,
        invocation_id=response.invocation_id,
    )


__all__ = [
    "CoachAnswerEvaluationProcessor",
    "CoachAssistancePlan",
    "CoachAssistanceProcessor",
    "CoachAssistanceResult",
    "CoachCardGenerationProcessor",
    "CoachEvaluationPlan",
    "CoachEvaluationResult",
    "CoachGenerationPlan",
    "CoachGenerationResult",
    "deterministic_evaluation",
    "finalize_response",
]
