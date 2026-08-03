from __future__ import annotations

import pytest

from learning.contracts import LearningActor
from learning.errors import LearningGovernanceError
from learning.lesson_runtime import (
    LessonAttemptContext,
    LessonRuntimeService,
)
from learning.models import LearningLessonAttempt


def context(
    *, attempt_id: str = "attempt-1", relearn_of_detail_id: str | None = None
) -> LessonAttemptContext:
    return LessonAttemptContext(
        organization_id="org-1",
        learner_id="learner-1",
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        activity_id="lesson-1",
        attempt_id=attempt_id,
        learning_unit_revision_id="unit-revision-1",
        required_checkpoint_ids=("checkpoint-1", "checkpoint-2"),
        relearn_of_detail_id=relearn_of_detail_id,
    )


def admin() -> LearningActor:
    return LearningActor(
        organization_id="org-1",
        actor_id="training-admin",
        capabilities=frozenset({"learning.lesson.invalidate"}),
        trace_id="trace-admin",
    )


@pytest.mark.asyncio
async def test_lesson_saves_resumes_and_requires_real_checkpoints_before_completion(
    test_db,
) -> None:
    service = LessonRuntimeService(test_db)
    detail = await service.start_or_resume(
        context=context(), idempotency_key="start-lesson"
    )
    assert detail.status == "in_progress"
    assert detail.completed_checkpoint_ids == ()

    saved = await service.save_progress(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=detail.detail_id,
        completed_checkpoint_ids=("checkpoint-1",),
        reading_position={"concept_id": "risk-discovery", "offset": 42},
        expected_version=detail.version,
        idempotency_key="save-checkpoint-1",
    )
    replay = await service.save_progress(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=detail.detail_id,
        completed_checkpoint_ids=("checkpoint-1",),
        reading_position={"concept_id": "risk-discovery", "offset": 42},
        expected_version=detail.version,
        idempotency_key="save-checkpoint-1",
    )
    assert saved == replay
    assert saved.completed_checkpoint_ids == ("checkpoint-1",)
    assert saved.reading_position == {"concept_id": "risk-discovery", "offset": 42}

    resumed = await service.start_or_resume(
        context=context(), idempotency_key="start-lesson"
    )
    assert resumed.detail_id == detail.detail_id
    assert resumed.completed_checkpoint_ids == ("checkpoint-1",)

    with pytest.raises(LearningGovernanceError) as incomplete:
        await service.complete(
            organization_id="org-1",
            learner_id="learner-1",
            detail_id=detail.detail_id,
            expected_version=saved.version,
            idempotency_key="complete-too-early",
        )
    assert incomplete.value.code == "[LESSON_CHECKPOINTS_INCOMPLETE]"

    saved_all = await service.save_progress(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=detail.detail_id,
        completed_checkpoint_ids=("checkpoint-1", "checkpoint-2"),
        reading_position={"concept_id": "complete", "offset": 0},
        expected_version=saved.version,
        idempotency_key="save-checkpoint-2",
    )
    completed = await service.complete(
        organization_id="org-1",
        learner_id="learner-1",
        detail_id=detail.detail_id,
        expected_version=saved_all.version,
        idempotency_key="complete-lesson",
    )
    assert completed.status == "completed"
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_lesson_rejects_stale_scope_and_supports_invalidation_then_relearning(
    test_db,
) -> None:
    service = LessonRuntimeService(test_db)
    detail = await service.start_or_resume(
        context=context(), idempotency_key="start-lesson"
    )

    with pytest.raises(LearningGovernanceError) as stale:
        await service.save_progress(
            organization_id="org-1",
            learner_id="learner-1",
            detail_id=detail.detail_id,
            completed_checkpoint_ids=("checkpoint-1",),
            reading_position={},
            expected_version=detail.version + 1,
            idempotency_key="stale-save",
        )
    assert stale.value.status_code == 412

    with pytest.raises(LearningGovernanceError) as hidden:
        await service.save_progress(
            organization_id="org-2",
            learner_id="learner-1",
            detail_id=detail.detail_id,
            completed_checkpoint_ids=("checkpoint-1",),
            reading_position={},
            expected_version=detail.version,
            idempotency_key="cross-org-save",
        )
    assert hidden.value.status_code == 404

    invalidated = await service.invalidate(
        actor=admin(),
        detail_id=detail.detail_id,
        expected_version=detail.version,
        reason="来源修订已被确认无效，需要重新学习",
        idempotency_key="invalidate-lesson",
    )
    assert invalidated.status == "invalidated"
    assert invalidated.invalidated_at is not None

    relearn = await service.start_or_resume(
        context=context(
            attempt_id="attempt-2", relearn_of_detail_id=invalidated.detail_id
        ),
        idempotency_key="start-relearning",
    )
    assert relearn.status == "in_progress"
    assert relearn.detail_id != invalidated.detail_id
    assert relearn.relearn_of_detail_id == invalidated.detail_id
    persisted = await test_db.get(LearningLessonAttempt, relearn.detail_id)
    assert persisted is not None
    assert persisted.learning_unit_revision_id == "unit-revision-1"
