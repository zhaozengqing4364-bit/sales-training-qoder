from __future__ import annotations

from types import SimpleNamespace

import pytest

from sales_trainer.orchestration.activities.assignment import AssignmentActivityHandler
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AssignmentActivity


class _Storage:
    async def store(self, **kwargs):
        raise AssertionError(f"text-only assignment must not store a file: {kwargs}")


class _Attempts:
    async def create(self, **kwargs):
        del kwargs
        return SimpleNamespace(status="not_started", passed=None, result_snapshot=None)


@pytest.mark.asyncio
async def test_should_mark_manual_assignment_as_needs_review(test_db, test_user):
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="revision-1",
        phase_id="phase-1",
        module_id="module-1",
        activity=AssignmentActivity.model_validate(
            {
                "activity_id": "assignment-1",
                "type": "assignment",
                "title": "完成环境搭建",
                "order_index": 1,
                "config": {
                    "submission_type": "text",
                    "review_mode": "manual_review",
                },
            }
        ),
    )
    handler = AssignmentActivityHandler(
        test_db, storage=_Storage(), attempts=_Attempts()
    )

    attempt = await handler.submit(
        context,
        text="完成技术环境搭建",
        file=None,
        client_token="assignment-token-1",
        actor=test_user,
    )

    assert attempt.status == "needs_review"
    assert attempt.result_snapshot["text"] == "完成技术环境搭建"
