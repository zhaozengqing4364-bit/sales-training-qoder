from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from ai_platform import (
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    AIWorkloadKind,
    StructuredValidationSummary,
)
from learning.application import (
    LearningGovernanceService,
    QuestionCandidateBulkItem,
)
from learning.contracts import (
    LearningActor,
    LearningUnitRevisionDraft,
    QuestionCandidateContent,
    QuestionGenerationRequest,
    SourceAnchorDraft,
    SourceDocumentRevisionDraft,
)
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestion,
    LearningQuestionCandidate,
    LearningQuestionRevision,
    LearningSourceAnchor,
)
from learning.question_generation import QuestionGenerationProcessor
from task_runtime.contracts import TaskReference, TaskState


class CapturingTaskRuntime:
    def __init__(self) -> None:
        self.commands = []

    async def enqueue(self, command):
        self.commands.append(command)
        return TaskReference(
            task_id="task-question-generation",
            state=TaskState.QUEUED,
            organization_id=command.organization_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            created_at=datetime.now(UTC),
        )

    async def get(self, task_id, viewer):  # pragma: no cover - not used here
        raise AssertionError((task_id, viewer))

    async def request_cancel(self, task_id, actor, *, idempotency_key=None):
        raise AssertionError((task_id, actor, idempotency_key))


class GeneratedQuestionAI:
    def __init__(self, *, source_anchor_id: str) -> None:
        self.requests = []
        self._source_anchor_id = source_anchor_id

    async def invoke(self, request):
        self.requests.append(request)
        return AIInvocationResult(
            invocation_id="invocation-1",
            workload_kind=AIWorkloadKind.LLM,
            status=AIInvocationStatus.SUCCEEDED,
            validated_output={
                "questions": [
                    {
                        "question_type": "single_choice",
                        "stem": "客户最关心交付风险时，首先应该做什么？",
                        "options": [
                            {
                                "option_id": "a",
                                "text": "先确认客户具体担忧和影响",
                                "is_correct": True,
                            },
                            {
                                "option_id": "b",
                                "text": "立即承诺最低价格",
                                "is_correct": False,
                            },
                        ],
                        "reference_answer": None,
                        "rubric": None,
                        "explanation": "先澄清风险才能给出有依据的回应。",
                        "difficulty": "medium",
                        "competency_keys": ["customer_understanding"],
                        "source_anchor_ids": [self._source_anchor_id],
                    },
                    {
                        "question_type": "single_choice",
                        "stem": "客户最关心交付风险时，首先应该做什么？",
                        "options": [
                            {
                                "option_id": "a",
                                "text": "先确认客户具体担忧和影响",
                                "is_correct": True,
                            },
                            {
                                "option_id": "b",
                                "text": "立即承诺最低价格",
                                "is_correct": False,
                            },
                        ],
                        "reference_answer": None,
                        "rubric": None,
                        "explanation": "重复题应被确定性门禁标记。",
                        "difficulty": "medium",
                        "competency_keys": ["customer_understanding"],
                        "source_anchor_ids": [self._source_anchor_id],
                    },
                ]
            },
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
            provider="fake",
            model="fake-question-model",
            usage=AIUsageSummary(
                input_tokens=100,
                output_tokens=200,
                total_tokens=300,
                cost_minor_units=0,
                currency="CNY",
            ),
            validation=StructuredValidationSummary(
                input_valid=True,
                output_valid=True,
                output_validation_attempts=1,
                output_schema_version=request.output_schema_version,
            ),
            created_at=datetime.now(UTC),
        )


def actor() -> LearningActor:
    return LearningActor(
        organization_id="org-1",
        actor_id="content-admin-1",
        capabilities=frozenset(
            {
                "learning.source.manage",
                "learning.content.manage",
                "learning.question.generate",
                "learning.question.manage",
                "learning.question.review",
                "learning.question.publish",
            }
        ),
        trace_id="trace-learning",
    )


async def _published_source_and_unit(test_db):
    service = LearningGovernanceService(test_db)
    user = actor()
    document = await service.create_source_document(
        actor=user,
        stable_key="sales-foundation-handbook",
        title="新人销售基础手册",
        idempotency_key="create-source",
    )
    source_revision = await service.save_source_revision(
        actor=user,
        document_id=document.document_id,
        draft=SourceDocumentRevisionDraft(
            revision_label="2026.07",
            source_type="file",
            source_uri="artifact://learning/source-handbook-v1",
            file_hash="a" * 64,
            parser_version="parser-v1",
            parse_status="ready",
        ),
        expected_document_version=document.version,
        idempotency_key="save-source-v1",
    )
    source_revision = await service.publish_source_revision(
        actor=user,
        revision_id=source_revision.revision_id,
        expected_revision_version=source_revision.version,
        idempotency_key="publish-source-v1",
    )
    anchor = await service.create_source_anchor(
        actor=user,
        source_revision_id=source_revision.revision_id,
        draft=SourceAnchorDraft(
            anchor_key="customer-risk-paragraph",
            label="客户风险澄清方法",
            locator={
                "type": "paragraph",
                "paragraph_id": "p-42",
                "start_offset": 0,
                "end_offset": 86,
            },
            excerpt_hash="b" * 64,
        ),
        idempotency_key="create-anchor",
    )
    unit = await service.create_learning_unit(
        actor=user,
        stable_key="customer-understanding",
        title="理解客户风险",
        idempotency_key="create-unit",
    )
    unit_revision = await service.save_learning_unit_revision(
        actor=user,
        unit_id=unit.unit_id,
        draft=LearningUnitRevisionDraft.model_validate(
            {
                "revision_label": "2026.07",
                "title": "理解客户风险",
                "objectives": ["能够识别并澄清客户的具体风险"],
                "key_concepts": [
                    {
                        "concept_id": "risk-discovery",
                        "title": "风险澄清",
                        "content": "先确认客户担忧、影响和判断标准。",
                        "source_anchor_ids": [anchor.anchor_id],
                    }
                ],
                "examples": [
                    {
                        "example_id": "risk-example",
                        "title": "交付风险",
                        "content": "追问延期会影响哪项业务目标。",
                        "source_anchor_ids": [anchor.anchor_id],
                    }
                ],
                "checkpoints": [
                    {
                        "checkpoint_id": "checkpoint-risk",
                        "prompt": "说出风险澄清的三个信息点",
                        "required": True,
                    }
                ],
                "practice_hints": ["先问影响，再讨论方案"],
            }
        ),
        expected_unit_version=unit.version,
        idempotency_key="save-unit-v1",
    )
    unit_revision = await service.publish_learning_unit_revision(
        actor=user,
        revision_id=unit_revision.revision_id,
        expected_revision_version=unit_revision.version,
        idempotency_key="publish-unit-v1",
    )
    return service, user, document, source_revision, anchor, unit, unit_revision


@pytest.mark.asyncio
async def test_published_source_and_learning_revisions_are_immutable_and_anchored(
    test_db,
) -> None:
    (
        service,
        user,
        document,
        source_revision,
        anchor,
        unit,
        unit_revision,
    ) = await _published_source_and_unit(test_db)

    document = await service.get_source_document(
        actor=user, document_id=document.document_id
    )
    source_revision_two = await service.save_source_revision(
        actor=user,
        document_id=document.document_id,
        draft=SourceDocumentRevisionDraft(
            revision_label="2026.08 reparse",
            source_type="file",
            source_uri="artifact://learning/source-handbook-v2",
            file_hash="c" * 64,
            parser_version="parser-v2",
            parse_status="ready",
        ),
        expected_document_version=document.version,
        idempotency_key="save-source-v2",
    )

    assert source_revision_two.revision_id != source_revision.revision_id
    assert source_revision_two.revision_no == 2
    original = await test_db.get(LearningSourceAnchor, anchor.anchor_id)
    assert original is not None
    assert original.source_revision_id == source_revision.revision_id
    persisted_unit = await service.get_learning_unit_revision(
        actor=user, revision_id=unit_revision.revision_id
    )
    assert persisted_unit.status == "published"
    assert persisted_unit.source_anchor_ids == (anchor.anchor_id,)

    with pytest.raises(LearningGovernanceError) as immutable:
        await service.update_published_learning_unit_revision(
            actor=user,
            revision_id=unit_revision.revision_id,
            title="不允许原地覆盖",
        )
    assert immutable.value.code == "[LEARNING_REVISION_IMMUTABLE]"


@pytest.mark.asyncio
async def test_ai_generation_persists_candidates_only_then_human_approval_creates_revision(
    test_db,
) -> None:
    (
        _,
        user,
        _,
        source_revision,
        anchor,
        _,
        unit_revision,
    ) = await _published_source_and_unit(test_db)
    tasks = CapturingTaskRuntime()
    service = LearningGovernanceService(test_db, task_runtime=tasks)
    request = QuestionGenerationRequest(
        source_revision_id=source_revision.revision_id,
        learning_unit_revision_id=unit_revision.revision_id,
        requested_count=2,
        prompt_template_id="question-generation",
        prompt_revision_id="prompt-revision-1",
        prompt_contract_hash="sha256:" + "d" * 64,
        model_routing_profile_id="question-generation-models",
        model_routing_revision_id="routing-revision-1",
        input_schema_version="question-generation-input-v1",
        output_schema_version="question-generation-output-v1",
    )
    batch = await service.start_question_generation(
        actor=user,
        request=request,
        idempotency_key="generate-customer-questions",
    )

    assert batch.status == "queued"
    assert batch.task_id == "task-question-generation"
    assert len(tasks.commands) == 1
    assert tasks.commands[0].task_type == "learning.question_generation.generate"
    assert int(await test_db.scalar(select(func.count(LearningQuestion.question_id))) or 0) == 0

    ai = GeneratedQuestionAI(source_anchor_id=anchor.anchor_id)
    result = await QuestionGenerationProcessor(test_db, ai=ai).process_batch(
        batch_id=batch.batch_id,
        task_id=batch.task_id,
    )

    assert result.created_count == 2
    assert result.passed_count == 1
    assert result.failed_count == 1
    candidates = (
        await test_db.execute(
            select(LearningQuestionCandidate).order_by(
                LearningQuestionCandidate.created_at,
                LearningQuestionCandidate.candidate_id,
            )
        )
    ).scalars().all()
    assert [candidate.gate_status for candidate in candidates] == ["passed", "failed"]
    assert candidates[1].gate_results_json["duplicate"]["passed"] is False
    assert candidates[0].prompt_revision_id == "prompt-revision-1"
    assert candidates[0].model_routing_revision_id == "routing-revision-1"
    assert candidates[0].source_anchor_ids_json == [anchor.anchor_id]
    assert len(ai.requests) == 1
    assert ai.requests[0].task_id == batch.task_id
    assert ai.requests[0].input_payload["learning_unit"]["title"] == "理解客户风险"
    assert ai.requests[0].input_payload["source_anchors"] == [
        {
            "anchor_id": anchor.anchor_id,
            "label": "客户风险澄清方法",
            "locator_type": "paragraph",
        }
    ]
    assert "风险澄清" in ai.requests[0].prompt_variables["learning_unit_json"]
    assert "客户风险澄清方法" in ai.requests[0].prompt_variables[
        "source_anchors_json"
    ]

    duplicate_in_review = await service.begin_question_candidate_review(
        actor=user,
        candidate_id=candidates[1].candidate_id,
        expected_version=candidates[1].version,
        idempotency_key="review-duplicate",
    )
    with pytest.raises(LearningGovernanceError) as failed_gate:
        await service.approve_question_candidate(
            actor=user,
            candidate_id=candidates[1].candidate_id,
            expected_version=duplicate_in_review.version,
            idempotency_key="approve-duplicate",
            review_reason="不应通过重复题",
        )
    assert failed_gate.value.code == "[QUESTION_CANDIDATE_GATES_FAILED]"

    in_review = await service.begin_question_candidate_review(
        actor=user,
        candidate_id=candidates[0].candidate_id,
        expected_version=candidates[0].version,
        idempotency_key="review-candidate",
    )
    approved = await service.approve_question_candidate(
        actor=user,
        candidate_id=candidates[0].candidate_id,
        expected_version=in_review.version,
        idempotency_key="approve-candidate",
        review_reason="来源和答案均已核对",
    )

    assert approved.status == "approved"
    assert approved.reviewed_by == user.actor_id
    assert approved.source_anchor_ids == (anchor.anchor_id,)
    assert approved.source_candidate_id == candidates[0].candidate_id
    assert int(await test_db.scalar(select(func.count(LearningQuestionRevision.revision_id))) or 0) == 1
    refreshed = await test_db.get(
        LearningQuestionCandidate, candidates[0].candidate_id
    )
    assert refreshed is not None
    assert refreshed.status == "approved"
    assert refreshed.approved_question_revision_id == approved.revision_id


@pytest.mark.asyncio
async def test_candidate_review_supports_edit_reject_supersede_and_idempotent_replay(
    test_db,
) -> None:
    (
        _,
        user,
        _,
        source_revision,
        anchor,
        _,
        unit_revision,
    ) = await _published_source_and_unit(test_db)
    tasks = CapturingTaskRuntime()
    service = LearningGovernanceService(test_db, task_runtime=tasks)
    batch = await service.start_question_generation(
        actor=user,
        request=QuestionGenerationRequest(
            source_revision_id=source_revision.revision_id,
            learning_unit_revision_id=unit_revision.revision_id,
            requested_count=2,
            prompt_template_id="question-generation",
            prompt_revision_id="prompt-revision-1",
            prompt_contract_hash="sha256:" + "d" * 64,
            model_routing_profile_id="question-generation-models",
            model_routing_revision_id="routing-revision-1",
            input_schema_version="question-generation-input-v1",
            output_schema_version="question-generation-output-v1",
        ),
        idempotency_key="generate-review-state-questions",
    )
    await QuestionGenerationProcessor(
        test_db, ai=GeneratedQuestionAI(source_anchor_id=anchor.anchor_id)
    ).process_batch(batch_id=batch.batch_id, task_id=batch.task_id or "")
    candidates = (
        await test_db.execute(
            select(LearningQuestionCandidate).order_by(
                LearningQuestionCandidate.created_at,
                LearningQuestionCandidate.candidate_id,
            )
        )
    ).scalars().all()

    in_review = await service.begin_question_candidate_review(
        actor=user,
        candidate_id=candidates[0].candidate_id,
        expected_version=candidates[0].version,
        idempotency_key="begin-edit-review",
    )
    edited_content = QuestionCandidateContent.model_validate(
        {
            **in_review.content.model_dump(mode="json"),
            "stem": "面对客户对交付风险的担忧，销售第一步应该确认哪些信息？",
            "explanation": "先确认担忧、业务影响和判断标准，再讨论可验证的方案。",
        }
    )
    edited = await service.edit_question_candidate(
        actor=user,
        candidate_id=in_review.candidate_id,
        content=edited_content,
        expected_version=in_review.version,
        idempotency_key="edit-candidate",
        review_reason="使问题指向具体的澄清信息",
    )
    assert edited.status == "in_review"
    assert edited.gate_status == "passed"

    rejected = await service.reject_question_candidate(
        actor=user,
        candidate_id=edited.candidate_id,
        expected_version=edited.version,
        idempotency_key="reject-candidate",
        review_reason="不纳入本次标准测验",
    )
    replay = await service.reject_question_candidate(
        actor=user,
        candidate_id=edited.candidate_id,
        expected_version=edited.version,
        idempotency_key="reject-candidate",
        review_reason="不纳入本次标准测验",
    )
    assert rejected.status == "rejected"
    assert replay.candidate_id == rejected.candidate_id
    assert replay.version == rejected.version

    superseded = await service.supersede_question_candidate(
        actor=user,
        candidate_id=candidates[1].candidate_id,
        expected_version=candidates[1].version,
        idempotency_key="supersede-duplicate",
        review_reason="由已修订的候选题替代",
    )
    assert superseded.status == "superseded"


@pytest.mark.asyncio
async def test_bulk_candidate_review_is_partial_safe_and_idempotent(test_db) -> None:
    (
        _,
        user,
        _,
        source_revision,
        anchor,
        _,
        unit_revision,
    ) = await _published_source_and_unit(test_db)
    tasks = CapturingTaskRuntime()
    service = LearningGovernanceService(test_db, task_runtime=tasks)
    batch = await service.start_question_generation(
        actor=user,
        request=QuestionGenerationRequest(
            source_revision_id=source_revision.revision_id,
            learning_unit_revision_id=unit_revision.revision_id,
            requested_count=2,
            prompt_template_id="question-generation",
            prompt_revision_id="prompt-revision-1",
            prompt_contract_hash="sha256:" + "d" * 64,
            model_routing_profile_id="question-generation-models",
            model_routing_revision_id="routing-revision-1",
            input_schema_version="question-generation-input-v1",
            output_schema_version="question-generation-output-v1",
        ),
        idempotency_key="generate-bulk-review-questions",
    )
    await QuestionGenerationProcessor(
        test_db, ai=GeneratedQuestionAI(source_anchor_id=anchor.anchor_id)
    ).process_batch(batch_id=batch.batch_id, task_id=batch.task_id or "")
    candidates = (
        await test_db.execute(
            select(LearningQuestionCandidate).order_by(
                LearningQuestionCandidate.created_at,
                LearningQuestionCandidate.candidate_id,
            )
        )
    ).scalars().all()
    selected = tuple(
        QuestionCandidateBulkItem(
            candidate_id=item.candidate_id,
            expected_version=item.version,
        )
        for item in candidates
    )

    begun = await service.bulk_review_question_candidates(
        actor=user,
        command="begin-review",
        items=selected,
        review_reason=None,
        idempotency_key="bulk-begin-review",
    )
    assert begun.status == "succeeded"
    assert begun.succeeded_count == 2

    preview = await service.preview_bulk_question_candidate_review(
        actor=user,
        command="approve",
        candidate_ids=tuple(item.candidate_id for item in begun.items),
        review_reason="批量核对来源、答案和重复门禁",
    )
    assert preview.eligible_count == 1
    assert preview.failure_count == 1
    approved = await service.confirm_bulk_question_candidate_review(
        actor=user,
        preview_token=preview.preview_token,
        impact_hash=preview.impact_hash,
        idempotency_key="bulk-approve-review",
    )
    replay = await service.confirm_bulk_question_candidate_review(
        actor=user,
        preview_token=preview.preview_token,
        impact_hash=preview.impact_hash,
        idempotency_key="bulk-approve-review",
    )

    assert approved.status == "partial"
    assert approved.succeeded_count == 1
    assert approved.failure_count == 1
    assert replay == approved
    assert {item.status for item in approved.items} == {"succeeded", "failed"}
    failed = next(item for item in approved.items if item.status == "failed")
    assert failed.error_code == "[QUESTION_CANDIDATE_PREVIEW_FAILED]"
    assert (
        int(
            await test_db.scalar(
                select(func.count(LearningQuestionRevision.revision_id))
            )
            or 0
        )
        == 1
    )


@pytest.mark.asyncio
async def test_human_authored_question_has_immutable_reviewed_revisions(test_db) -> None:
    _, user, _, _, anchor, _, _ = await _published_source_and_unit(test_db)
    service = LearningGovernanceService(test_db)
    content = QuestionCandidateContent.model_validate(
        {
            "question_type": "true_false",
            "stem": "理解客户风险时，应先确认担忧及其业务影响。",
            "options": [
                {"option_id": "true", "text": "正确", "is_correct": True},
                {"option_id": "false", "text": "错误", "is_correct": False},
            ],
            "explanation": "先澄清担忧和影响，后续方案才有依据。",
            "difficulty": "easy",
            "competency_keys": ["customer_understanding"],
            "source_anchor_ids": [anchor.anchor_id],
        }
    )

    first = await service.save_manual_question_revision(
        actor=user,
        stable_key="customer-risk-first-step",
        content=content,
        expected_question_version=None,
        idempotency_key="save-manual-question-v1",
        review_reason="人工依据手册编写并核对答案",
    )
    replay = await service.save_manual_question_revision(
        actor=user,
        stable_key="customer-risk-first-step",
        content=content,
        expected_question_version=None,
        idempotency_key="save-manual-question-v1",
        review_reason="人工依据手册编写并核对答案",
    )
    assert replay == first
    assert first.source_candidate_id is None
    assert first.reviewed_by == user.actor_id

    published = await service.publish_question_revision(
        actor=user,
        revision_id=first.revision_id,
        expected_revision_version=first.version,
        idempotency_key="publish-manual-question-v1",
    )
    changed = QuestionCandidateContent.model_validate(
        {
            **content.model_dump(mode="json"),
            "stem": "理解客户交付风险时，应先确认担忧、影响与判断标准。",
        }
    )
    second = await service.save_manual_question_revision(
        actor=user,
        stable_key="customer-risk-first-step",
        content=changed,
        expected_question_version=2,
        idempotency_key="save-manual-question-v2",
        review_reason="补充判断标准，保留历史题目修订",
    )

    assert published.status == "published"
    assert second.revision_no == 2
    assert second.revision_id != first.revision_id
    persisted_first = await test_db.get(
        LearningQuestionRevision, first.revision_id
    )
    assert persisted_first is not None
    assert persisted_first.content_json == content.model_dump(mode="json")
