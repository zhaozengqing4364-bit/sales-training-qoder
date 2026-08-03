"""Governed AI candidate generation with deterministic, human-visible gates."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_platform import (
    AIInvocationPort,
    AIInvocationResult,
    AIInvocationStatus,
    BudgetScope,
    DataClassification,
    GovernedAIRequest,
)
from learning.contracts import QuestionCandidateContent, QuestionGenerationOutput
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestionCandidate,
    LearningQuestionGenerationBatch,
    LearningQuestionRevision,
    LearningSourceAnchor,
    LearningUnitRevision,
)


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def question_fingerprint(question: QuestionCandidateContent) -> str:
    normalized = {
        "question_type": question.question_type,
        "stem": " ".join(question.stem.casefold().split()),
        "options": sorted(
            " ".join(item.text.casefold().split()) for item in question.options
        ),
    }
    return _canonical_hash(normalized)


def contains_sensitive_text(question: QuestionCandidateContent) -> bool:
    text = " ".join(
        [question.stem, question.explanation]
        + [option.text for option in question.options]
    ).casefold()
    return any(term in text for term in ("password", "api token", "密钥"))


def build_question_generation_context(
    *,
    source_revision_id: str,
    learning_unit_revision_id: str,
    requested_count: int,
    learning_unit_snapshot: dict[str, object],
    anchors: list[LearningSourceAnchor],
) -> tuple[dict[str, object], dict[str, object]]:
    """Build the exact governed-AI input shared by preview and worker execution."""

    anchor_context = [
        {
            "anchor_id": item.anchor_id,
            "label": item.label,
            "locator_type": item.locator_type,
        }
        for item in sorted(anchors, key=lambda item: item.anchor_id)
    ]
    input_payload: dict[str, object] = {
        "source_revision_id": source_revision_id,
        "learning_unit_revision_id": learning_unit_revision_id,
        "requested_count": requested_count,
        "learning_unit": dict(learning_unit_snapshot),
        "source_anchors": anchor_context,
    }
    prompt_variables: dict[str, object] = {
        "source_revision_id": source_revision_id,
        "learning_unit_revision_id": learning_unit_revision_id,
        "requested_count": requested_count,
        "learning_unit_json": json.dumps(
            learning_unit_snapshot,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "source_anchors_json": json.dumps(
            anchor_context,
            ensure_ascii=False,
            sort_keys=True,
        ),
    }
    return input_payload, prompt_variables


class QuestionGenerationProcessResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    invocation_id: str
    created_count: int
    passed_count: int
    failed_count: int
    candidate_ids: tuple[str, ...]


class QuestionGenerationPlan(BaseModel):
    """Frozen invocation request created and committed before Provider I/O."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    task_id: str
    request: GovernedAIRequest


class QuestionGenerationProcessor:
    def __init__(self, session: AsyncSession, *, ai: AIInvocationPort) -> None:
        self._session = session
        self._ai = ai

    async def process_batch(
        self, *, batch_id: str, task_id: str
    ) -> QuestionGenerationProcessResult:
        prepared = await self.prepare_batch(batch_id=batch_id, task_id=task_id)
        if isinstance(prepared, QuestionGenerationProcessResult):
            return prepared
        result = await self._ai.invoke(prepared.request)
        return await self.apply_result(plan=prepared, result=result)

    async def prepare_batch(
        self, *, batch_id: str, task_id: str
    ) -> QuestionGenerationPlan | QuestionGenerationProcessResult:
        batch = await self._session.scalar(
            select(LearningQuestionGenerationBatch)
            .where(LearningQuestionGenerationBatch.batch_id == batch_id)
            .with_for_update()
            .limit(1)
        )
        if batch is None:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_BATCH_NOT_FOUND]", "题目生成批次不存在。", 404
            )
        if batch.task_id != task_id:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_TASK_MISMATCH]", "任务与题目生成批次不匹配。", 409
            )
        if batch.status == "completed":
            rows = (
                await self._session.execute(
                    select(LearningQuestionCandidate).where(
                        LearningQuestionCandidate.batch_id == batch_id
                    )
                )
            ).scalars().all()
            return QuestionGenerationProcessResult(
                batch_id=batch_id,
                invocation_id=batch.invocation_id or "",
                created_count=len(rows),
                passed_count=sum(item.gate_status == "passed" for item in rows),
                failed_count=sum(item.gate_status == "failed" for item in rows),
                candidate_ids=tuple(item.candidate_id for item in rows),
            )
        if batch.status not in {"queued", "running", "failed"}:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_BATCH_STATE_CONFLICT]", "当前批次不能执行。", 409
            )
        batch.status = "running"
        batch.version += 1
        await self._session.flush([batch])
        unit = await self._session.get(
            LearningUnitRevision,
            batch.learning_unit_revision_id,
        )
        if (
            unit is None
            or unit.organization_id != batch.organization_id
            or unit.status not in {"published", "archived"}
        ):
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_SOURCE_UNAVAILABLE]",
                "题目生成引用的学习内容版本不可用。",
                409,
            )
        anchor_ids = tuple(unit.source_anchor_ids_json)
        anchors = (
            await self._session.execute(
                select(LearningSourceAnchor)
                .where(
                    LearningSourceAnchor.organization_id == batch.organization_id
                )
                .where(
                    LearningSourceAnchor.source_revision_id
                    == batch.source_revision_id
                )
                .where(LearningSourceAnchor.anchor_id.in_(anchor_ids))
            )
        ).scalars().all()
        if {item.anchor_id for item in anchors} != set(anchor_ids):
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_SOURCE_UNAVAILABLE]",
                "题目生成引用的来源锚点不可用。",
                409,
            )
        input_payload, prompt_variables = build_question_generation_context(
            source_revision_id=batch.source_revision_id,
            learning_unit_revision_id=batch.learning_unit_revision_id,
            requested_count=batch.requested_count,
            learning_unit_snapshot=dict(unit.snapshot_json),
            anchors=list(anchors),
        )
        return QuestionGenerationPlan(
            batch_id=batch.batch_id,
            task_id=task_id,
            request=GovernedAIRequest(
                business_purpose="newcomer_question_generation",
                task_id=task_id,
                organization_id=batch.organization_id,
                actor_id=batch.requested_by,
                object_type="question_generation_batch",
                object_id=batch.batch_id,
                prompt_template_id=batch.prompt_template_id,
                prompt_revision_id=batch.prompt_revision_id,
                prompt_contract_hash=batch.prompt_contract_hash,
                model_routing_profile_id=batch.model_routing_profile_id,
                model_routing_revision_id=batch.model_routing_revision_id,
                input_schema_version=batch.input_schema_version,
                output_schema_version=batch.output_schema_version,
                input_payload=input_payload,
                prompt_variables=prompt_variables,
                idempotency_key=f"question-generation:{batch.batch_id}",
                data_classification=DataClassification.INTERNAL,
                trace_id=task_id,
                correlation_id=batch.batch_id,
                causation_id=batch.learning_unit_revision_id,
                runtime_consumer="learning.question_generation.v1",
                timeout_policy_ref="question-generation-default",
                retry_policy_ref="question-generation-default",
                budget_scope=BudgetScope.ORGANIZATION,
                formal_scoring=False,
                allow_fallback=True,
            ),
        )

    async def apply_result(
        self,
        *,
        plan: QuestionGenerationPlan,
        result: AIInvocationResult,
    ) -> QuestionGenerationProcessResult:
        batch = await self._session.scalar(
            select(LearningQuestionGenerationBatch)
            .where(LearningQuestionGenerationBatch.batch_id == plan.batch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
            .limit(1)
        )
        if batch is None:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_BATCH_NOT_FOUND]", "题目生成批次不存在。", 404
            )
        if batch.task_id != plan.task_id:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_TASK_MISMATCH]", "任务与题目生成批次不匹配。", 409
            )
        if batch.status == "completed":
            return await self._completed_result(batch)
        if batch.status not in {"running", "failed"}:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_BATCH_STATE_CONFLICT]", "当前批次不能保存生成结果。", 409
            )
        if result.status not in {
            AIInvocationStatus.SUCCEEDED,
            AIInvocationStatus.PARTIAL,
        } or result.validated_output is None:
            batch.status = "failed"
            batch.error_code = (
                result.failure.code if result.failure is not None else "ai_generation_failed"
            )
            batch.invocation_id = result.invocation_id
            batch.version += 1
            await self._session.flush([batch])
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_AI_FAILED]", "候选题生成失败，可从任务中心重试。", 503,
                details={"retryable": bool(result.failure and result.failure.retryable)},
            )
        output = QuestionGenerationOutput.model_validate(result.validated_output)
        if len(output.questions) > batch.requested_count:
            raise LearningGovernanceError(
                "[QUESTION_GENERATION_OUTPUT_LIMIT]", "生成结果超过请求数量。", 422
            )
        existing_fingerprints = set(
            (
                await self._session.execute(
                    select(LearningQuestionRevision.deterministic_fingerprint).where(
                        LearningQuestionRevision.organization_id == batch.organization_id
                    )
                )
            ).scalars()
        )
        existing_fingerprints.update(
            (
                await self._session.execute(
                    select(LearningQuestionCandidate.deterministic_fingerprint).where(
                        LearningQuestionCandidate.organization_id == batch.organization_id
                    )
                )
            ).scalars()
        )
        created: list[LearningQuestionCandidate] = []
        seen = set(existing_fingerprints)
        base_time = _now()
        for index, question in enumerate(output.questions):
            fingerprint = question_fingerprint(question)
            anchor_rows = (
                await self._session.execute(
                    select(LearningSourceAnchor)
                    .where(LearningSourceAnchor.organization_id == batch.organization_id)
                    .where(LearningSourceAnchor.anchor_id.in_(question.source_anchor_ids))
                )
            ).scalars().all()
            anchor_ids = {item.anchor_id for item in anchor_rows}
            sources_valid = (
                anchor_ids == set(question.source_anchor_ids)
                and all(
                    item.source_revision_id == batch.source_revision_id
                    for item in anchor_rows
                )
            )
            duplicate_passed = fingerprint not in seen
            sensitive_passed = not contains_sensitive_text(question)
            quality_passed = (
                len(question.stem.strip()) >= 12
                and len(question.explanation.strip()) >= 8
                and bool(question.competency_keys)
            )
            gates: dict[str, dict[str, object]] = {
                "schema": {"passed": True},
                "answer": {"passed": True},
                "source": {"passed": sources_valid},
                "duplicate": {
                    "passed": duplicate_passed,
                    "fingerprint": fingerprint,
                },
                "sensitive": {"passed": sensitive_passed},
                "quality": {"passed": quality_passed},
            }
            gate_status = (
                "passed"
                if all(bool(item["passed"]) for item in gates.values())
                else "failed"
            )
            row = LearningQuestionCandidate(
                candidate_id=_id(),
                batch_id=batch.batch_id,
                organization_id=batch.organization_id,
                status="generated",
                version=1,
                question_type=question.question_type,
                content_json=question.model_dump(mode="json"),
                source_anchor_ids_json=list(question.source_anchor_ids),
                competency_keys_json=list(question.competency_keys),
                deterministic_fingerprint=fingerprint,
                gate_status=gate_status,
                gate_results_json=gates,
                prompt_revision_id=batch.prompt_revision_id,
                model_routing_revision_id=batch.model_routing_revision_id,
                generation_input_hash=batch.generation_input_hash,
                invocation_id=result.invocation_id,
                created_at=base_time + timedelta(microseconds=index),
                updated_at=base_time + timedelta(microseconds=index),
            )
            self._session.add(row)
            created.append(row)
            seen.add(fingerprint)
        batch.status = "completed"
        batch.invocation_id = result.invocation_id
        batch.candidate_count = len(created)
        batch.error_code = None
        batch.version += 1
        batch.completed_at = _now()
        await self._session.flush([batch, *created])
        return QuestionGenerationProcessResult(
            batch_id=batch.batch_id,
            invocation_id=result.invocation_id,
            created_count=len(created),
            passed_count=sum(item.gate_status == "passed" for item in created),
            failed_count=sum(item.gate_status == "failed" for item in created),
            candidate_ids=tuple(item.candidate_id for item in created),
        )

    async def _completed_result(
        self, batch: LearningQuestionGenerationBatch
    ) -> QuestionGenerationProcessResult:
        rows = (
            await self._session.execute(
                select(LearningQuestionCandidate).where(
                    LearningQuestionCandidate.batch_id == batch.batch_id
                )
            )
        ).scalars().all()
        return QuestionGenerationProcessResult(
            batch_id=batch.batch_id,
            invocation_id=batch.invocation_id or "",
            created_count=len(rows),
            passed_count=sum(item.gate_status == "passed" for item in rows),
            failed_count=sum(item.gate_status == "failed" for item in rows),
            candidate_ids=tuple(item.candidate_id for item in rows),
        )

    @staticmethod
    def question_fingerprint(question: QuestionCandidateContent) -> str:
        return question_fingerprint(question)

    @staticmethod
    def _contains_sensitive_text(question: QuestionCandidateContent) -> bool:
        return contains_sensitive_text(question)


__all__ = [
    "QuestionGenerationProcessResult",
    "QuestionGenerationProcessor",
    "contains_sensitive_text",
    "question_fingerprint",
]
