from __future__ import annotations

from datetime import UTC, datetime

import pytest

from learning.models import (
    LearningQuestion,
    LearningQuestionRevision,
    LearningQuiz,
    LearningQuizRevision,
    LearningUnit,
    LearningUnitRevision,
)
from learning.task_definitions import register_learning_task_definitions
from newcomer_foundation_composition import LearningActivityRuntimeAdapter
from newcomer_training.activity_application import (
    ActivityApplicationService,
    CompleteLessonCommand,
    SaveLessonProgressCommand,
    SaveQuizAnswersCommand,
    StartActivityCommand,
    SubmitQuizCommand,
)
from newcomer_training.application import CommandActor
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.journey import JourneyQueryService
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerCohort,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
)
from newcomer_training.ports import ActivityRuntimeResult
from task_runtime import TaskRegistry


class StubRuntime:
    def __init__(self, *, task_id: str | None = None) -> None:
        self._task_id = task_id

    def _result(self, attempt_id: str) -> ActivityRuntimeResult:
        return ActivityRuntimeResult(
            detail_id=f"detail:{attempt_id}",
            detail_status="in_progress",
            detail_version=1,
            task_id=self._task_id,
            runner={"kind": "stub"},
            available_commands=("save_progress",),
        )

    async def workspace(self, **kwargs) -> ActivityRuntimeResult | None:
        attempt_id = kwargs.get("attempt_id")
        return self._result(str(attempt_id)) if attempt_id is not None else None

    async def start(self, command) -> ActivityRuntimeResult:
        return self._result(command.attempt_id)

    async def execute(self, command) -> ActivityRuntimeResult:
        return self._result(command.attempt_id)


def _learner_actor(learner_id: str, *, allowed: bool = True) -> CommandActor:
    return CommandActor(
        organization_id="org-1",
        actor_id=learner_id,
        capabilities=(
            frozenset({"newcomer.activity.execute"}) if allowed else frozenset()
        ),
        trace_id="trace-learner",
    )


def _path_snapshot() -> dict[str, object]:
    return {
        "contract_version": "newcomer_training_path_v2",
        "title": "新人销售基础训练",
        "revision_label": "2026.07",
        "stages": [
            {
                "stage_id": "stage-foundation",
                "sequence": 1,
                "title": "客户理解基础",
                "objective": "先学习，再用测验验证掌握情况",
                "entry_conditions": [],
                "completion_rule": "all_required",
                "visibility": "learner",
                "activities": [
                    {
                        "activity_id": "lesson-customer",
                        "type": "lesson",
                        "title": "理解客户风险",
                        "objective": "掌握风险澄清方法",
                        "why_it_matters": "先理解客户，才能给出可靠方案",
                        "steps": ["阅读关键概念", "完成检查点"],
                        "success_criteria": ["完成风险澄清检查点"],
                        "competency_keys": ["customer_understanding"],
                        "estimated_minutes": 15,
                        "required": True,
                        "prerequisite_activity_ids": [],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 0,
                            "retry_interval_seconds": 0,
                        },
                        "config": {
                            "learning_unit_revision_id": "unit-revision-1",
                            "required_checkpoint_ids": ["checkpoint-risk"],
                        },
                    },
                    {
                        "activity_id": "quiz-customer",
                        "type": "quiz",
                        "title": "客户理解测验",
                        "objective": "验证风险澄清方法",
                        "why_it_matters": "确保能在客户沟通中正确应用",
                        "steps": ["回答全部题目", "提交测验"],
                        "success_criteria": ["达到 80 分"],
                        "competency_keys": ["customer_understanding"],
                        "estimated_minutes": 10,
                        "required": True,
                        "prerequisite_activity_ids": ["lesson-customer"],
                        "ai_dependency": "none",
                        "retry_policy": {
                            "max_attempts": 3,
                            "retry_interval_seconds": 300,
                        },
                        "config": {"quiz_revision_id": "quiz-revision-1"},
                    },
                ],
            }
        ],
    }


async def _seed(test_db, learner_id: str) -> None:
    now = datetime.now(UTC)
    unit = LearningUnit(
        unit_id="unit-1",
        organization_id="org-1",
        stable_key="customer-understanding",
        title="理解客户风险",
        status="active",
        published_revision_id="unit-revision-1",
        version=2,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    unit_revision = LearningUnitRevision(
        revision_id="unit-revision-1",
        unit_id="unit-1",
        organization_id="org-1",
        revision_no=1,
        revision_label="2026.07",
        status="published",
        snapshot_json={
            "revision_label": "2026.07",
            "title": "理解客户风险",
            "objectives": ["识别并澄清客户风险"],
            "key_concepts": [
                {
                    "concept_id": "risk-discovery",
                    "title": "风险澄清",
                    "content": "确认客户担忧、业务影响和判断标准。",
                    "source_anchor_ids": ["anchor-1"],
                }
            ],
            "examples": [],
            "checkpoints": [
                {
                    "checkpoint_id": "checkpoint-risk",
                    "prompt": "说出风险澄清的三个信息点",
                    "required": True,
                }
            ],
            "practice_hints": ["先问影响，再讨论方案"],
        },
        source_anchor_ids_json=[],
        content_hash="c" * 64,
        version=2,
        save_idempotency_key_hash="d" * 64,
        save_fingerprint="e" * 64,
        publish_idempotency_key_hash="f" * 64,
        publish_fingerprint="1" * 64,
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    question = LearningQuestion(
        question_id="question-1",
        organization_id="org-1",
        stable_key="customer-risk-first-step",
        status="published",
        published_revision_id="question-revision-1",
        version=2,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    question_revision = LearningQuestionRevision(
        revision_id="question-revision-1",
        question_id="question-1",
        organization_id="org-1",
        revision_no=1,
        status="published",
        version=2,
        question_type="single_choice",
        content_json={
            "question_type": "single_choice",
            "stem": "客户担忧交付延期时，首先应该做什么？",
            "options": [
                {
                    "option_id": "clarify",
                    "text": "澄清具体担忧和业务影响",
                    "is_correct": True,
                },
                {
                    "option_id": "discount",
                    "text": "立即承诺降价",
                    "is_correct": False,
                },
            ],
            "reference_answer": None,
            "rubric": None,
            "explanation": "先澄清问题，才能给出可靠方案。",
            "difficulty": "easy",
            "competency_keys": ["customer_understanding"],
            "source_anchor_ids": ["anchor-1"],
        },
        source_anchor_ids_json=["anchor-1"],
        competency_keys_json=["customer_understanding"],
        deterministic_fingerprint="2" * 64,
        content_hash="3" * 64,
        reviewed_by="admin-1",
        review_reason="人工核对",
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    quiz = LearningQuiz(
        quiz_id="quiz-1",
        organization_id="org-1",
        stable_key="customer-understanding-quiz",
        title="客户理解测验",
        status="active",
        published_revision_id="quiz-revision-1",
        version=2,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    quiz_revision = LearningQuizRevision(
        revision_id="quiz-revision-1",
        quiz_id="quiz-1",
        organization_id="org-1",
        revision_no=1,
        revision_label="2026.07",
        status="published",
        snapshot_json={
            "revision_label": "2026.07",
            "title": "客户理解测验",
            "questions": [
                {"question_revision_id": "question-revision-1", "points": 1.0}
            ],
            "pass_threshold": 80,
            "max_attempts": 3,
            "retry_interval_seconds": 300,
            "feedback_policy": "after_submit",
            "time_limit_minutes": 10,
            "shuffle_questions": False,
            "shuffle_options": False,
            "short_answer_scoring": None,
        },
        question_revision_ids_json=["question-revision-1"],
        content_hash="6" * 64,
        version=2,
        save_idempotency_key_hash="7" * 64,
        save_fingerprint="8" * 64,
        publish_idempotency_key_hash="9" * 64,
        publish_fingerprint="0" * 64,
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    path = NewcomerPath(
        path_id="path-1",
        organization_id="org-1",
        stable_key="foundation",
        title="新人销售基础训练",
        status="active",
        published_revision_id="path-revision-1",
        version=2,
        creation_idempotency_key_hash="a" * 64,
        creation_fingerprint="b" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    path_revision = NewcomerPathRevision(
        revision_id="path-revision-1",
        path_id="path-1",
        organization_id="org-1",
        revision_no=1,
        revision_label="2026.07",
        status="published",
        snapshot_json=_path_snapshot(),
        content_hash="c" * 64,
        version=2,
        save_idempotency_key_hash="d" * 64,
        save_fingerprint="e" * 64,
        publish_idempotency_key_hash="f" * 64,
        publish_fingerprint="1" * 64,
        created_by="admin-1",
        published_by="admin-1",
        created_at=now,
        published_at=now,
    )
    cohort = NewcomerCohort(
        cohort_id="cohort-1",
        organization_id="org-1",
        stable_key="july-2026",
        name="2026 年 7 月新人班",
        path_revision_id="path-revision-1",
        status="active",
        version=1,
        creation_idempotency_key_hash="2" * 64,
        creation_fingerprint="3" * 64,
        created_by="admin-1",
        created_at=now,
        updated_at=now,
    )
    enrollment = NewcomerEnrollment(
        enrollment_id="enrollment-1",
        organization_id="org-1",
        learner_id=learner_id,
        cohort_id="cohort-1",
        path_revision_id="path-revision-1",
        status="active",
        version=1,
        creation_idempotency_key_hash="4" * 64,
        creation_fingerprint="5" * 64,
        assigned_by="admin-1",
        assigned_at=now,
        updated_at=now,
    )
    test_db.add_all(
        [
            unit,
            unit_revision,
            question,
            question_revision,
            quiz,
            quiz_revision,
            path,
            path_revision,
            cohort,
            enrollment,
        ]
    )
    await test_db.flush()


@pytest.mark.asyncio
async def test_single_journey_entry_completes_lesson_then_objective_quiz(
    test_db,
    test_user,
) -> None:
    learner_id = str(test_user.user_id)
    await _seed(test_db, learner_id)
    registry = TaskRegistry()
    register_learning_task_definitions(registry)
    actor = CommandActor(
        organization_id="org-1",
        actor_id=learner_id,
        capabilities=frozenset(
            {"newcomer.journey.read", "newcomer.activity.execute"}
        ),
        trace_id="trace-learner",
    )
    app = ActivityApplicationService(
        test_db,
        runtime=LearningActivityRuntimeAdapter(test_db, task_registry=registry),
    )

    with pytest.raises(NewcomerTrainingError) as locked_workspace:
        await app.get_workspace(actor=actor, activity_id="quiz-customer")
    assert locked_workspace.value.code == "[NEWCOMER_ACTIVITY_LOCKED]"

    journey = await JourneyQueryService(test_db).get_my_journey(actor=actor)
    assert journey.primary_action is not None
    assert journey.primary_action.activity_id == "lesson-customer"

    lesson = await app.get_workspace(actor=actor, activity_id="lesson-customer")
    assert lesson.runner["kind"] == "lesson"
    assert lesson.available_commands == ("start",)
    lesson = await app.execute(
        actor=actor,
        activity_id="lesson-customer",
        command=StartActivityCommand(
            command_type="start",
            expected_enrollment_version=1,
        ),
        idempotency_key="start-lesson",
    )
    lesson = await app.execute(
        actor=actor,
        activity_id="lesson-customer",
        command=SaveLessonProgressCommand(
            command_type="save_progress",
            attempt_id=lesson.attempt.attempt_id,
            expected_attempt_version=lesson.runner["version"],
            payload={
                "completed_checkpoint_ids": ["checkpoint-risk"],
                "reading_position": {"concept_id": "risk-discovery"},
            },
        ),
        idempotency_key="save-lesson",
    )
    lesson = await app.execute(
        actor=actor,
        activity_id="lesson-customer",
        command=CompleteLessonCommand(
            command_type="complete",
            attempt_id=lesson.attempt.attempt_id,
            expected_attempt_version=lesson.runner["version"],
        ),
        idempotency_key="complete-lesson",
    )
    assert lesson.attempt.status == "completed"
    assert lesson.outcome["assessment_result"] == "not_applicable"

    journey = await JourneyQueryService(test_db).get_my_journey(actor=actor)
    assert journey.primary_action is not None
    assert journey.primary_action.activity_id == "quiz-customer"

    quiz = await app.execute(
        actor=actor,
        activity_id="quiz-customer",
        command=StartActivityCommand(
            command_type="start",
            expected_enrollment_version=1,
        ),
        idempotency_key="start-quiz",
    )
    assert "is_correct" not in quiz.runner["questions"][0]["options"][0]
    quiz = await app.execute(
        actor=actor,
        activity_id="quiz-customer",
        command=SaveQuizAnswersCommand(
            command_type="save_answers",
            attempt_id=quiz.attempt.attempt_id,
            expected_attempt_version=quiz.runner["version"],
            payload={
                "answers": [
                    {
                        "question_revision_id": "question-revision-1",
                        "selected_option_ids": ["clarify"],
                    }
                ]
            },
        ),
        idempotency_key="save-quiz",
    )
    quiz = await app.execute(
        actor=actor,
        activity_id="quiz-customer",
        command=SubmitQuizCommand(
            command_type="submit",
            attempt_id=quiz.attempt.attempt_id,
            expected_attempt_version=quiz.runner["version"],
        ),
        idempotency_key="submit-quiz",
    )
    assert quiz.attempt.status == "completed"
    assert quiz.outcome["passed"] is True
    assert quiz.runner["result"] == {"score": 1.0, "max_score": 1.0, "passed": True}

    completed = await JourneyQueryService(test_db).get_my_journey(actor=actor)
    assert completed.status == "completed"
    assert completed.primary_action is None


@pytest.mark.asyncio
async def test_activity_workspace_rejects_permission_and_missing_enrollment(
    test_db,
    test_user,
) -> None:
    learner_id = str(test_user.user_id)
    app = ActivityApplicationService(test_db, runtime=StubRuntime())

    with pytest.raises(NewcomerTrainingError) as denied:
        await app.get_workspace(
            actor=_learner_actor(learner_id, allowed=False),
            activity_id="lesson-customer",
        )
    assert denied.value.code == "[NEWCOMER_PERMISSION_DENIED]"

    with pytest.raises(NewcomerTrainingError) as missing:
        await app.get_workspace(
            actor=_learner_actor(learner_id),
            activity_id="lesson-customer",
        )
    assert missing.value.code == "[NEWCOMER_ENROLLMENT_NOT_FOUND]"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["revision", "activity"])
async def test_activity_workspace_rejects_unavailable_revision_and_unknown_activity(
    test_db,
    test_user,
    failure: str,
) -> None:
    learner_id = str(test_user.user_id)
    await _seed(test_db, learner_id)
    if failure == "revision":
        revision = await test_db.get(NewcomerPathRevision, "path-revision-1")
        assert revision is not None
        revision.status = "working"
        await test_db.flush([revision])
        activity_id = "lesson-customer"
        expected = "[NEWCOMER_PATH_REVISION_UNAVAILABLE]"
    else:
        activity_id = "missing-activity"
        expected = "[NEWCOMER_ACTIVITY_NOT_FOUND]"

    with pytest.raises(NewcomerTrainingError) as error:
        await ActivityApplicationService(test_db, runtime=StubRuntime()).get_workspace(
            actor=_learner_actor(learner_id),
            activity_id=activity_id,
        )
    assert error.value.code == expected


@pytest.mark.asyncio
async def test_start_with_background_task_marks_attempt_processing(
    test_db,
    test_user,
) -> None:
    learner_id = str(test_user.user_id)
    await _seed(test_db, learner_id)
    app = ActivityApplicationService(test_db, runtime=StubRuntime(task_id="task-1"))

    workspace = await app.execute(
        actor=_learner_actor(learner_id),
        activity_id="lesson-customer",
        command=StartActivityCommand(
            command_type="start",
            expected_enrollment_version=1,
        ),
        idempotency_key="start-background-lesson",
    )

    assert workspace.attempt is not None
    assert workspace.attempt.status == "processing"
    assert workspace.attempt.task_id == "task-1"


@pytest.mark.asyncio
async def test_existing_attempt_guards_mismatch_terminal_and_ownership(
    test_db,
    test_user,
) -> None:
    learner_id = str(test_user.user_id)
    await _seed(test_db, learner_id)
    actor = _learner_actor(learner_id)
    app = ActivityApplicationService(test_db, runtime=StubRuntime())
    started = await app.execute(
        actor=actor,
        activity_id="lesson-customer",
        command=StartActivityCommand(
            command_type="start",
            expected_enrollment_version=1,
        ),
        idempotency_key="start-guarded-lesson",
    )
    assert started.attempt is not None
    row = await test_db.get(NewcomerActivityAttempt, started.attempt.attempt_id)
    assert row is not None

    row.activity_id = "quiz-customer"
    await test_db.flush([row])
    with pytest.raises(NewcomerTrainingError) as mismatch:
        await app.execute(
            actor=actor,
            activity_id="lesson-customer",
            command=SaveLessonProgressCommand(
                command_type="save_progress",
                attempt_id=row.attempt_id,
                expected_attempt_version=1,
                payload={"completed_checkpoint_ids": []},
            ),
            idempotency_key="mismatched-attempt",
        )
    assert mismatch.value.code == "[NEWCOMER_ACTIVITY_ATTEMPT_MISMATCH]"

    row.activity_id = "lesson-customer"
    row.status = "completed"
    await test_db.flush([row])
    with pytest.raises(NewcomerTrainingError) as terminal:
        await app.execute(
            actor=actor,
            activity_id="lesson-customer",
            command=SaveLessonProgressCommand(
                command_type="save_progress",
                attempt_id=row.attempt_id,
                expected_attempt_version=1,
                payload={"completed_checkpoint_ids": []},
            ),
            idempotency_key="terminal-attempt",
        )
    assert terminal.value.code == "[NEWCOMER_ATTEMPT_STATE_CONFLICT]"

    row.organization_id = "org-2"
    await test_db.flush([row])
    with pytest.raises(NewcomerTrainingError) as hidden_attempt:
        await app._load_attempt(actor, row.attempt_id)
    assert hidden_attempt.value.code == "[NEWCOMER_ATTEMPT_NOT_FOUND]"

    row.organization_id = "org-1"
    enrollment = await test_db.get(NewcomerEnrollment, row.enrollment_id)
    assert enrollment is not None
    enrollment.learner_id = "another-learner"
    await test_db.flush([row, enrollment])
    with pytest.raises(NewcomerTrainingError) as hidden_enrollment:
        await app._load_attempt(actor, row.attempt_id)
    assert hidden_enrollment.value.code == "[NEWCOMER_ATTEMPT_NOT_FOUND]"


@pytest.mark.asyncio
async def test_workspace_audit_and_command_negative_branches(
    test_db,
    test_user,
) -> None:
    learner_id = str(test_user.user_id)
    await _seed(test_db, learner_id)
    actor = _learner_actor(learner_id)
    app = ActivityApplicationService(test_db, runtime=StubRuntime())
    started = await app.execute(
        actor=actor,
        activity_id="lesson-customer",
        command=StartActivityCommand(
            command_type="start",
            expected_enrollment_version=1,
        ),
        idempotency_key="start-negative-lesson",
    )
    assert started.attempt is not None
    attempt = await test_db.get(NewcomerActivityAttempt, started.attempt.attempt_id)
    assert attempt is not None
    activity = PathRevisionDraft.model_validate(_path_snapshot()).stages[0].activities[0]

    attempt.outcome_id = "missing-outcome"
    await test_db.flush([attempt])
    workspace = await app._workspace(
        enrollment_version=1,
        activity=activity,
        attempt=attempt,
        runtime=None,
    )
    assert workspace.outcome is None

    await app._audit_runtime_command(
        actor=actor,
        attempt=attempt,
        command_type="save_progress",
        idempotency_key="audit-replay",
        detail_version=1,
    )
    await app._audit_runtime_command(
        actor=actor,
        attempt=attempt,
        command_type="save_progress",
        idempotency_key="audit-replay",
        detail_version=1,
    )

    with pytest.raises(NewcomerTrainingError) as unsupported:
        app._validate_command_type(activity, "submit")
    assert unsupported.value.code == "[NEWCOMER_ACTIVITY_COMMAND_UNSUPPORTED]"
