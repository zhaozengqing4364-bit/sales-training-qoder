from __future__ import annotations

import pytest

from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService


async def _publish_assignment_path(test_db, actor):
    payload = TrainingPathPayload.model_validate(
        {
            "title": "新人训练",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "入门",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "module-1",
                            "title": "基础任务",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "assignment-1",
                                    "type": "assignment",
                                    "title": "提交学习总结",
                                    "order_index": 1,
                                    "config": {
                                        "submission_type": "text",
                                        "review_mode": "automatic_complete",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    service = TrainingPathRevisionService(test_db)
    await service.save_draft(payload=payload, actor=actor, reason="测试路径")
    await service.publish(actor=actor, reason="测试路径")
    await test_db.commit()


@pytest.mark.asyncio
async def test_learner_journey_has_one_primary_action_and_assignment_closes_it(
    async_client, auth_headers, test_db, test_user
):
    await _publish_assignment_path(test_db, test_user)

    before = await async_client.get(
        "/api/v1/newcomer-training/journey", headers=auth_headers
    )
    assert before.status_code == 200, before.text
    journey = before.json()["data"]
    assert journey["primary_next_action"]["activity_id"] == "assignment-1"

    submitted = await async_client.post(
        "/api/v1/newcomer-training/activities/assignment-1/assignments",
        headers=auth_headers,
        data={"client_token": "assignment-api-token", "text": "完成学习总结"},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["activity"]["completed"] is True

    after = await async_client.get(
        "/api/v1/newcomer-training/journey", headers=auth_headers
    )
    assert after.json()["data"]["primary_next_action"] is None
    assert after.json()["data"]["progress"]["completed"] is True
