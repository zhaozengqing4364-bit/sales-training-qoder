from __future__ import annotations

import uuid
from types import MethodType, SimpleNamespace

import pytest

from agent.models import VoiceRuntimeProfile
from curriculum_practice.models import PracticeTemplate
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import RealtimeRoleplayActivity
from sales_trainer.services.realtime_roleplay_start_service import (
    RealtimeRoleplayStartService,
)


class _Attempts:
    def __init__(self) -> None:
        self.attempt = SimpleNamespace(attempt_id="attempt-1")

    async def create(self, **kwargs):
        self.snapshot = kwargs["activity_snapshot"]
        return self.attempt

    async def attach_evidence(self, **kwargs):
        self.evidence = kwargs
        return self.attempt


class _ExternalStart:
    async def start(self, payload, *, current_user, external_binding):
        self.payload = payload
        self.current_user = current_user
        self.binding = external_binding
        return SimpleNamespace(session_id="practice-session-1")


@pytest.mark.asyncio
async def test_should_freeze_activity_binding_when_starting_stepaudio(
    test_db, test_user
):
    template_id = str(uuid.uuid4())
    runtime_id = str(uuid.uuid4())
    test_db.add(
        VoiceRuntimeProfile(
            id=runtime_id,
            name=f"runtime-{runtime_id}",
            is_active=True,
            voice_mode="stepfun_realtime",
        )
    )
    test_db.add(
        PracticeTemplate(
            template_id=template_id,
            name="产品对练",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id=str(uuid.uuid4()),
            persona_id=str(uuid.uuid4()),
            runtime_profile_id=runtime_id,
            scoring_ruleset_id=str(uuid.uuid4()),
            status="published",
        )
    )
    await test_db.flush()
    context = ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="path-revision-1",
        phase_id="phase-1",
        module_id="product-a",
        activity=RealtimeRoleplayActivity.model_validate(
            {
                "activity_id": "realtime-1",
                "type": "realtime_roleplay",
                "title": "产品 A 对练",
                "order_index": 1,
                "config": {
                    "practice_template_id": template_id,
                    "runtime_profile_id": runtime_id,
                },
            }
        ),
    )
    attempts = _Attempts()
    external = _ExternalStart()
    service = RealtimeRoleplayStartService(
        test_db, session_start_service=external, attempts=attempts
    )

    async def ready_registry(self, profile_id):
        assert profile_id == runtime_id
        return {"descriptor": {"provider": "fake", "readiness": {"ready": True}}}

    service._validated_runtime_registry = MethodType(ready_registry, service)
    result = await service.start(
        actor=test_user,
        execution_context=context,
        client_token="realtime-token-1",
    )

    binding = result["external_binding"]
    assert binding["owner"] == "newcomer_training"
    assert binding["activity_id"] == "realtime-1"
    assert binding["path_revision_id"] == "path-revision-1"
    assert attempts.evidence["evidence_id"] == "practice-session-1"
