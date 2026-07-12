from __future__ import annotations

from types import SimpleNamespace

import pytest

from sales_trainer.orchestration.activities.ai_coach import AiCoachActivityHandler
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import AiCoachActivity


class _Sessions:
    async def create_activity_session(self, *, context, actor):
        self.context = context
        self.actor = actor
        return SimpleNamespace(session_id="coach-session-1")


class _Attempts:
    async def create(self, **kwargs):
        self.snapshot = kwargs["activity_snapshot"]
        return SimpleNamespace(attempt_id="attempt-1")

    async def attach_evidence(self, **kwargs):
        return SimpleNamespace(**kwargs, activity_snapshot=self.snapshot)


@pytest.mark.asyncio
async def test_should_create_ai_coach_session_from_activity_profile(test_db, test_user):
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="revision-1",
        phase_id="phase-1",
        module_id="product-a",
        activity=AiCoachActivity.model_validate(
            {
                "activity_id": "coach-1",
                "type": "ai_coach",
                "title": "产品 A 教练",
                "order_index": 1,
                "config": {"coach_profile_id": "coach-profile-product"},
            }
        ),
    )
    handler = AiCoachActivityHandler(
        test_db, sessions=_Sessions(), attempts=_Attempts()
    )

    attempt = await handler.start(
        context, actor=test_user, client_token="coach-token-1"
    )

    assert attempt.evidence_type == "ai_coach_session"
    assert (
        attempt.activity_snapshot["config"]["coach_profile_id"]
        == "coach-profile-product"
    )
