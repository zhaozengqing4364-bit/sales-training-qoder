from __future__ import annotations

from types import SimpleNamespace

import pytest

from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.activities.quiz import QuizActivityHandler
from sales_trainer.orchestration.contracts import QuizActivity
from sales_trainer.schemas import QuizAnswerSubmit


class _Papers:
    def __init__(self) -> None:
        self.execution_context = None

    async def submit_paper_attempt(self, payload, *, actor, execution_context=None):
        del payload, actor
        self.execution_context = execution_context
        return SimpleNamespace(
            attempt_id="quiz-attempt-1", passed=True, total_score=90, max_score=100
        )


class _Attempts:
    def __init__(self) -> None:
        self.attempt = SimpleNamespace(
            attempt_id="attempt-1", score=None, max_score=None, passed=None
        )

    async def create(self, **kwargs):
        self.snapshot = kwargs["activity_snapshot"]
        return self.attempt

    async def attach_evidence(self, **kwargs):
        for key in ("evidence_type", "evidence_id", "status"):
            setattr(self.attempt, key, kwargs[key])
        return self.attempt


@pytest.mark.asyncio
async def test_should_submit_quiz_from_activity_without_business_module_key(
    test_db, test_user
):
    papers = _Papers()
    attempts = _Attempts()
    activity = QuizActivity.model_validate(
        {
            "activity_id": "quiz-1",
            "type": "quiz",
            "title": "产品 A 小测",
            "order_index": 1,
            "config": {"exam_paper_id": "paper-1", "pass_score": 80},
        }
    )
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="revision-1",
        phase_id="phase-1",
        module_id="product-a",
        activity=activity,
    )
    handler = QuizActivityHandler(test_db, papers=papers, attempts=attempts)

    attempt = await handler.submit(
        context,
        answers=[QuizAnswerSubmit(question_id="question-1", answer_payload="A")],
        client_token="quiz-activity-token",
        actor=test_user,
    )

    assert attempt.evidence_type == "quiz_attempt"
    assert attempt.passed is True
    assert attempts.snapshot["activity_id"] == "quiz-1"
    assert papers.execution_context is context
