from __future__ import annotations

from types import SimpleNamespace

import pytest

from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.activities.lesson import LessonActivityHandler
from sales_trainer.orchestration.contracts import LessonActivity


class _Progress:
    def __init__(self) -> None:
        self.completed = False

    async def study_content(self, **kwargs):
        del kwargs
        return SimpleNamespace(
            is_success=True,
            value=SimpleNamespace(
                progress=SimpleNamespace(
                    is_completed=self.completed,
                    state="completed" if self.completed else "in_progress",
                )
            ),
            fallback=None,
        )

    async def complete_chapter(self, **kwargs):
        del kwargs
        self.completed = True
        return SimpleNamespace(is_success=True, fallback=None)


class _Attempts:
    def __init__(self) -> None:
        self.attached = None

    async def create(self, **kwargs):
        del kwargs
        return SimpleNamespace(attempt_id="attempt-1")

    async def attach_evidence(self, **kwargs):
        self.attached = kwargs


def _context(learner_id: str) -> ActivityExecutionContext:
    return ActivityExecutionContext(
        learner_id=learner_id,
        enrollment_id="enrollment-1",
        path_revision_id="revision-1",
        phase_id="phase-1",
        module_id="module-1",
        activity=LessonActivity.model_validate(
            {
                "activity_id": "lesson-1",
                "type": "lesson",
                "title": "学习产品 A",
                "order_index": 1,
                "config": {"learning_content_id": "content-1"},
            }
        ),
    )


@pytest.mark.asyncio
async def test_should_complete_lesson_when_all_published_chapters_are_read(
    test_db, test_user
):
    progress = _Progress()
    attempts = _Attempts()
    handler = LessonActivityHandler(test_db, progress=progress, attempts=attempts)
    context = _context(str(test_user.user_id))

    projection = await handler.mark_chapter_complete(
        context, chapter_id="chapter-1", actor=test_user, client_token="lesson-token"
    )

    assert projection.status == "completed"
    assert projection.completed is True
    assert attempts.attached["evidence_type"] == "learning_progress"
