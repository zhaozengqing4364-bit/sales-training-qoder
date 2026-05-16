from __future__ import annotations

import pytest
from pydantic import ValidationError

from common.training_tasks.schemas import (
    TrainingTaskBatchAssignRequest,
    TrainingTaskBatchAssignResponse,
    TrainingTaskCreate,
    TrainingTaskResponse,
    TrainingTaskScenarioType,
)


@pytest.mark.contract
def test_training_task_contract_accepts_optional_practice_template_id() -> None:
    payload = TrainingTaskCreate(
        title="客户异议训练",
        assignee_id="user-1",
        scenario_type=TrainingTaskScenarioType.SALES,
        goal="练习处理价格异议",
        practice_template_id="template-1",
    )

    assert payload.practice_template_id == "template-1"


@pytest.mark.contract
def test_training_task_contract_rejects_runtime_state_fields() -> None:
    base_payload = {
        "task_id": "task-1",
        "title": "客户异议训练",
        "assignee_id": "user-1",
        "scenario_type": "sales",
        "goal": "练习处理价格异议",
        "completion_criteria": {},
        "practice_template_id": "template-1",
        "source": "manual",
        "status": "assigned",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    }

    response = TrainingTaskResponse.model_validate(base_payload)

    assert response.practice_template_id == "template-1"
    assert not hasattr(response, "preflight")
    assert not hasattr(response, "stage")
    assert not hasattr(response, "reconnect")


@pytest.mark.contract
def test_training_task_create_rejects_runtime_state_fields() -> None:
    with pytest.raises(ValidationError):
        TrainingTaskCreate(
            title="客户异议训练",
            assignee_id="user-1",
            scenario_type=TrainingTaskScenarioType.SALES,
            goal="练习处理价格异议",
            stage="preflight",
        )


@pytest.mark.contract
def test_training_task_batch_assign_contract_accepts_curriculum_plan_binding() -> None:
    payload = TrainingTaskBatchAssignRequest(
        user_ids=["user-1", "user-2"],
        template_id="template-1",
        curriculum_plan_id="template-1",
        title="学习-考核-实战训练",
        scenario_type=TrainingTaskScenarioType.SALES,
        goal="完成三阶段训练闭环",
    )

    response = TrainingTaskBatchAssignResponse(
        assigned_count=1,
        skipped_count=1,
        failed_count=0,
        assigned=[{"user_id": "user-1", "task_id": "task-1"}],
        skipped=[{"user_id": "user-2", "reason": "[TRAINING_TASK_ALREADY_ASSIGNED]"}],
        failed=[],
    )

    assert payload.curriculum_plan_id == "template-1"
    assert response.assigned_count == 1
    assert response.skipped[0].reason == "[TRAINING_TASK_ALREADY_ASSIGNED]"
