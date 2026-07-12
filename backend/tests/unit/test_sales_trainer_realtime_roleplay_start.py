from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from agent.models import VoiceRuntimeProfile
from curriculum_practice.models import PracticeTemplate
from sales_trainer.orchestration.activities.base import ActivityExecutionContext
from sales_trainer.orchestration.contracts import (
    AssignmentActivity,
    RealtimeRoleplayActivity,
)
from sales_trainer.permissions import can_enter_sales_trainer_realtime
from sales_trainer.services.realtime_roleplay_start_service import (
    RealtimeRoleplayStartError,
    RealtimeRoleplayStartService,
)


class _Attempts:
    async def create(self, **kwargs):
        del kwargs
        return SimpleNamespace(attempt_id="attempt-1")

    async def attach_evidence(self, **kwargs):
        return SimpleNamespace(**kwargs)


class _External:
    async def start(self, payload, *, current_user, external_binding):
        del payload, current_user
        self.binding = external_binding
        return SimpleNamespace(session_id="session-1")


async def _runtime_context(test_db, test_user, *, published=True, runtime_active=True):
    template_id = str(uuid.uuid4())
    runtime_id = str(uuid.uuid4())
    test_db.add(
        VoiceRuntimeProfile(
            id=runtime_id,
            name=f"runtime-{runtime_id}",
            is_active=runtime_active,
            voice_mode="stepfun_realtime",
        )
    )
    test_db.add(
        PracticeTemplate(
            template_id=template_id,
            name="实时对练",
            scenario_type="sales",
            mode="customer_roleplay",
            agent_id=str(uuid.uuid4()),
            persona_id=str(uuid.uuid4()),
            runtime_profile_id=runtime_id,
            scoring_ruleset_id=str(uuid.uuid4()),
            status="published" if published else "draft",
        )
    )
    await test_db.flush()
    return ActivityExecutionContext(
        learner_id=str(test_user.user_id),
        enrollment_id="enrollment-1",
        path_revision_id="revision-1",
        phase_id="phase-1",
        module_id="module-1",
        activity=RealtimeRoleplayActivity.model_validate(
            {
                "activity_id": "realtime-1",
                "type": "realtime_roleplay",
                "title": "实时对练",
                "order_index": 1,
                "config": {
                    "practice_template_id": template_id,
                    "runtime_profile_id": runtime_id,
                },
            }
        ),
    )


@pytest.mark.asyncio
async def test_start_requires_published_template(test_db, test_user):
    context = await _runtime_context(test_db, test_user, published=False)
    service = RealtimeRoleplayStartService(test_db, attempts=_Attempts())
    with pytest.raises(RealtimeRoleplayStartError) as error:
        await service.start(
            actor=test_user, execution_context=context, client_token="token"
        )
    assert error.value.code == "[NEWCOMER_REALTIME_TEMPLATE_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_start_requires_active_stepaudio_runtime(test_db, test_user):
    context = await _runtime_context(test_db, test_user, runtime_active=False)
    service = RealtimeRoleplayStartService(test_db, attempts=_Attempts())
    with pytest.raises(RealtimeRoleplayStartError) as error:
        await service.start(
            actor=test_user, execution_context=context, client_token="token"
        )
    assert error.value.code == "[NEWCOMER_REALTIME_RUNTIME_NOT_READY]"


@pytest.mark.asyncio
async def test_start_rejects_cross_learner_context(test_db, test_user):
    context = await _runtime_context(test_db, test_user)
    context = ActivityExecutionContext(
        learner_id="another-user",
        enrollment_id=context.enrollment_id,
        path_revision_id=context.path_revision_id,
        phase_id=context.phase_id,
        module_id=context.module_id,
        activity=context.activity,
    )
    service = RealtimeRoleplayStartService(test_db, attempts=_Attempts())
    with pytest.raises(RealtimeRoleplayStartError) as error:
        await service.start(
            actor=test_user, execution_context=context, client_token="token"
        )
    assert error.value.code == "[NEWCOMER_ACTIVITY_SCOPE_MISMATCH]"


@pytest.mark.asyncio
async def test_start_rejects_non_realtime_activity(test_db, test_user):
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
                "title": "作业",
                "order_index": 1,
                "config": {
                    "submission_type": "text",
                    "review_mode": "automatic_complete",
                },
            }
        ),
    )
    with pytest.raises(RealtimeRoleplayStartError) as error:
        await RealtimeRoleplayStartService(test_db, attempts=_Attempts()).start(
            actor=test_user, execution_context=context, client_token="token"
        )
    assert error.value.code == "[NEWCOMER_ACTIVITY_TYPE_MISMATCH]"


def test_realtime_entry_permission_matches_learning_path_permission(test_user):
    assert can_enter_sales_trainer_realtime(test_user) is True
