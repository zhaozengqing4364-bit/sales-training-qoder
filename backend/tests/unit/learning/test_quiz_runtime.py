from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_platform import (
    AIErrorClassification,
    AIInvocationFailure,
    AIInvocationResult,
    AIInvocationStatus,
    AIUsageSummary,
    AIWorkloadKind,
    StructuredValidationSummary,
)
from learning.application import LearningGovernanceService
from learning.contracts import LearningActor, QuizRevisionDraft
from learning.errors import LearningGovernanceError
from learning.models import (
    LearningQuestion,
    LearningQuestionRevision,
    LearningQuizAttempt,
)
from learning.ports import ActivityOutcomePayload
from learning.quiz_runtime import (
    QuizAnswerInput,
    QuizAttemptContext,
    QuizRuntimeService,
    ShortAnswerScoringProcessor,
)
from task_runtime.contracts import TaskReference, TaskState


class CapturingTaskRuntime:
    def __init__(self) -> None:
        self.commands = []

    async def enqueue(self, command):
        self.commands.append(command)
        return TaskReference(
            task_id="task-short-answer",
            state=TaskState.QUEUED,
            organization_id=command.organization_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            created_at=datetime.now(UTC),
        )

    async def get(self, task_id, viewer):  # pragma: no cover
        raise AssertionError((task_id, viewer))

    async def request_cancel(self, task_id, actor, *, idempotency_key=None):
        raise AssertionError((task_id, actor, idempotency_key))


class CapturingOutcomeWriter:
    def __init__(self) -> None:
        self.payloads: list[ActivityOutcomePayload] = []

    async def record(self, payload: ActivityOutcomePayload) -> str:
        self.payloads.append(payload)
        return "outcome-short-answer"


class ShortAnswerAI:
    def __init__(self, *, fail: bool) -> None:
        self.fail = fail
        self.requests = []

    async def invoke(self, request):
        self.requests.append(request)
        if self.fail:
            return AIInvocationResult(
                invocation_id="invocation-failed",
                workload_kind=AIWorkloadKind.LLM,
                status=AIInvocationStatus.FAILED,
                failure=AIInvocationFailure(
                    code="provider_timeout",
                    classification=AIErrorClassification.TIMEOUT,
                    retryable=True,
                    message="评分服务超时。",
                ),
                prompt_template_id=request.prompt_template_id,
                prompt_revision_id=request.prompt_revision_id,
                prompt_contract_hash=request.prompt_contract_hash,
                model_routing_profile_id=request.model_routing_profile_id,
                model_routing_revision_id=request.model_routing_revision_id,
                usage=AIUsageSummary(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    cost_minor_units=0,
                    currency="CNY",
                ),
                created_at=datetime.now(UTC),
            )
        return AIInvocationResult(
            invocation_id="invocation-success",
            workload_kind=AIWorkloadKind.LLM,
            status=AIInvocationStatus.SUCCEEDED,
            validated_output={
                "answers": [
                    {
                        "question_revision_id": "question-short-rev-1",
                        "awarded_points": 1.0,
                        "max_points": 1.0,
                        "rubric_evidence": [
                            {
                                "criterion": "识别风险",
                                "met": True,
                                "reason": "回答说明了延期影响。",
                            }
                        ],
                        "confidence": 0.9,
                    }
                ]
            },
            prompt_template_id=request.prompt_template_id,
            prompt_revision_id=request.prompt_revision_id,
            prompt_contract_hash=request.prompt_contract_hash,
            model_routing_profile_id=request.model_routing_profile_id,
            model_routing_revision_id=request.model_routing_revision_id,
            provider="fake",
            model="fake-short-answer",
            usage=AIUsageSummary(
                input_tokens=50,
                output_tokens=30,
                total_tokens=80,
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
        actor_id="training-admin",
        capabilities=frozenset(
            {
                "learning.question.publish",
                "learning.quiz.manage",
            }
        ),
        trace_id="trace-quiz-admin",
    )


def attempt_context(
    *, attempt_id: str, quiz_revision_id: str
) -> QuizAttemptContext:
    return QuizAttemptContext(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="quiz-1",
        attempt_id=attempt_id,
        quiz_revision_id=quiz_revision_id,
        trace_id="trace-quiz-learner",
    )


async def _question(
    test_db,
    *,
    question_id: str,
    revision_id: str,
    question_type: str,
) -> LearningQuestionRevision:
    now = datetime.now(UTC)
    if question_type == "short_answer":
        content = {
            "question_type": "short_answer",
            "stem": "请说明如何澄清客户对交付延期的风险。",
            "options": [],
            "reference_answer": "确认担忧、业务影响和判断标准。",
            "rubric": {"criteria": ["识别担忧", "说明影响"]},
            "explanation": "回答应覆盖风险澄清的三个信息点。",
            "difficulty": "medium",
            "competency_keys": ["customer_understanding"],
            "source_anchor_ids": ["anchor-1"],
        }
    else:
        content = {
            "question_type": "single_choice",
            "stem": "客户担忧交付延期时，首先应该做什么？",
            "options": [
                {"option_id": "a", "text": "澄清具体担忧和影响", "is_correct": True},
                {"option_id": "b", "text": "直接承诺降价", "is_correct": False},
            ],
            "reference_answer": None,
            "rubric": None,
            "explanation": "先澄清问题，才能给出可靠方案。",
            "difficulty": "medium",
            "competency_keys": ["customer_understanding"],
            "source_anchor_ids": ["anchor-1"],
        }
    question = LearningQuestion(
        question_id=question_id,
        organization_id="org-1",
        stable_key=question_id,
        status="published",
        published_revision_id=revision_id,
        version=2,
        created_by="training-admin",
        created_at=now,
        updated_at=now,
    )
    revision = LearningQuestionRevision(
        revision_id=revision_id,
        question_id=question_id,
        organization_id="org-1",
        revision_no=1,
        status="published",
        version=2,
        question_type=question_type,
        content_json=content,
        source_anchor_ids_json=["anchor-1"],
        competency_keys_json=["customer_understanding"],
        deterministic_fingerprint=("a" if question_type == "short_answer" else "b") * 64,
        content_hash="c" * 64,
        reviewed_by="training-admin",
        review_reason="人工核对",
        created_by="training-admin",
        published_by="training-admin",
        created_at=now,
        published_at=now,
    )
    test_db.add_all([question, revision])
    await test_db.flush()
    return revision


async def _quiz_revision(test_db, *, short_answer: bool):
    question_revision = await _question(
        test_db,
        question_id="question-short" if short_answer else "question-objective",
        revision_id=(
            "question-short-rev-1" if short_answer else "question-objective-rev-1"
        ),
        question_type="short_answer" if short_answer else "single_choice",
    )
    service = LearningGovernanceService(test_db)
    quiz = await service.create_quiz(
        actor=actor(),
        stable_key="quiz-short" if short_answer else "quiz-objective",
        title="客户理解测验",
        idempotency_key="create-quiz-short" if short_answer else "create-quiz-objective",
    )
    payload = {
        "revision_label": "2026.07",
        "title": "客户理解测验",
        "questions": [
            {"question_revision_id": question_revision.revision_id, "points": 1.0}
        ],
        "pass_threshold": 80,
        "max_attempts": 3,
        "retry_interval_seconds": 300,
        "feedback_policy": "after_submit",
        "time_limit_minutes": 20,
        "shuffle_questions": False,
        "shuffle_options": False,
        "short_answer_scoring": (
            {
                "prompt_template_id": "short-answer-score",
                "prompt_revision_id": "prompt-short-v1",
                "prompt_contract_hash": "sha256:" + "d" * 64,
                "model_routing_profile_id": "short-answer-models",
                "model_routing_revision_id": "routing-short-v1",
                "input_schema_version": "short-answer-input-v1",
                "output_schema_version": "short-answer-output-v1",
            }
            if short_answer
            else None
        ),
    }
    working = await service.save_quiz_revision(
        actor=actor(),
        quiz_id=quiz.quiz_id,
        draft=QuizRevisionDraft.model_validate(payload),
        expected_quiz_version=quiz.version,
        idempotency_key="save-quiz-short" if short_answer else "save-quiz-objective",
    )
    return await service.publish_quiz_revision(
        actor=actor(),
        revision_id=working.revision_id,
        expected_revision_version=working.version,
        idempotency_key="publish-quiz-short" if short_answer else "publish-quiz-objective",
    )


@pytest.mark.asyncio
async def test_quiz_attempt_freezes_question_and_rule_snapshots_and_scores_objective(
    test_db,
) -> None:
    revision = await _quiz_revision(test_db, short_answer=False)
    outcomes = CapturingOutcomeWriter()
    runtime = QuizRuntimeService(test_db, outcomes=outcomes)
    started = await runtime.start_or_resume(
        context=attempt_context(
            attempt_id="generic-attempt-objective",
            quiz_revision_id=revision.revision_id,
        ),
        idempotency_key="start-objective",
    )
    assert started.status == "in_progress"
    assert started.rule_snapshot["pass_threshold"] == 80
    assert started.questions[0]["question_revision_id"] == "question-objective-rev-1"
    assert started.questions[0]["stem"] == "客户担忧交付延期时，首先应该做什么？"

    # Later question changes cannot mutate the frozen attempt snapshot.
    persisted_question = await test_db.get(
        LearningQuestionRevision, "question-objective-rev-1"
    )
    assert persisted_question is not None
    persisted_question.content_json = {
        **persisted_question.content_json,
        "stem": "后台数据被错误修改也不能改变已冻结尝试",
    }
    await test_db.flush([persisted_question])
    resumed = await runtime.start_or_resume(
        context=attempt_context(
            attempt_id="generic-attempt-objective",
            quiz_revision_id=revision.revision_id,
        ),
        idempotency_key="start-objective",
    )
    assert resumed.questions[0]["stem"] == "客户担忧交付延期时，首先应该做什么？"

    saved = await runtime.save_answers(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=started.detail_id,
        answers=(
            QuizAnswerInput(
                question_revision_id="question-objective-rev-1",
                selected_option_ids=("a",),
            ),
        ),
        expected_version=started.version,
        idempotency_key="save-objective-answer",
    )
    submitted = await runtime.submit(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=started.detail_id,
        expected_version=saved.version,
        idempotency_key="submit-objective",
    )
    assert submitted.status == "scored"
    assert submitted.score == 1.0
    assert submitted.max_score == 1.0
    assert submitted.passed is True
    assert len(outcomes.payloads) == 1
    assert outcomes.payloads[0].attempt_id == "generic-attempt-objective"
    assert outcomes.payloads[0].lineage["scoring_method"] == "deterministic"


@pytest.mark.asyncio
async def test_short_answer_is_durable_and_provider_failure_never_completes_attempt(
    test_db,
) -> None:
    revision = await _quiz_revision(test_db, short_answer=True)
    tasks = CapturingTaskRuntime()
    runtime = QuizRuntimeService(test_db, task_runtime=tasks)
    started = await runtime.start_or_resume(
        context=attempt_context(
            attempt_id="generic-attempt-short",
            quiz_revision_id=revision.revision_id,
        ),
        idempotency_key="start-short",
    )
    saved = await runtime.save_answers(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=started.detail_id,
        answers=(
            QuizAnswerInput(
                question_revision_id="question-short-rev-1",
                text_answer="先确认客户担忧，再说明延期对业务目标的影响。",
            ),
        ),
        expected_version=started.version,
        idempotency_key="save-short-answer",
    )
    submitted = await runtime.submit(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=started.detail_id,
        expected_version=saved.version,
        idempotency_key="submit-short-answer",
    )
    assert submitted.status == "scoring_pending"
    assert submitted.passed is None
    assert submitted.task_id == "task-short-answer"
    assert len(tasks.commands) == 1
    assert tasks.commands[0].task_type == "learning.quiz.short_answer_score"

    outcomes = CapturingOutcomeWriter()
    with pytest.raises(LearningGovernanceError) as failed:
        await ShortAnswerScoringProcessor(
            test_db,
            ai=ShortAnswerAI(fail=True),
            outcomes=outcomes,
        ).process_attempt(
            detail_id=started.detail_id,
            task_id=submitted.task_id,
        )
    assert failed.value.code == "[QUIZ_SHORT_ANSWER_SCORING_FAILED]"
    persisted = await test_db.get(LearningQuizAttempt, started.detail_id)
    assert persisted is not None
    assert persisted.status == "needs_review"
    assert persisted.passed is None
    assert persisted.completed_at is None
    assert outcomes.payloads == []


@pytest.mark.asyncio
async def test_short_answer_success_records_normalized_outcome(test_db) -> None:
    revision = await _quiz_revision(test_db, short_answer=True)
    tasks = CapturingTaskRuntime()
    runtime = QuizRuntimeService(test_db, task_runtime=tasks)
    started = await runtime.start_or_resume(
        context=attempt_context(
            attempt_id="generic-attempt-short-success",
            quiz_revision_id=revision.revision_id,
        ),
        idempotency_key="start-short-success",
    )
    saved = await runtime.save_answers(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=started.detail_id,
        answers=(
            QuizAnswerInput(
                question_revision_id="question-short-rev-1",
                text_answer="确认担忧、业务影响和客户的判断标准。",
            ),
        ),
        expected_version=started.version,
        idempotency_key="save-short-success",
    )
    submitted = await runtime.submit(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=started.detail_id,
        expected_version=saved.version,
        idempotency_key="submit-short-success",
    )
    outcomes = CapturingOutcomeWriter()
    ai = ShortAnswerAI(fail=False)
    result = await ShortAnswerScoringProcessor(
        test_db,
        ai=ai,
        outcomes=outcomes,
    ).process_attempt(
        detail_id=started.detail_id,
        task_id=submitted.task_id,
    )

    assert result.status == "scored"
    assert result.passed is True
    assert result.score == 1.0
    assert len(outcomes.payloads) == 1
    assert outcomes.payloads[0].attempt_id == "generic-attempt-short-success"
    assert outcomes.payloads[0].assessment_result == "passed"
    assert outcomes.payloads[0].lineage["quiz_revision_id"] == revision.revision_id
    assert len(ai.requests) == 1
    assert "确认担忧、业务影响" in ai.requests[0].prompt_variables["answers_json"]
