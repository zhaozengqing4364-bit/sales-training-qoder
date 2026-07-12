from __future__ import annotations

import pytest

from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.journey_service import NewcomerJourneyService
from sales_trainer.orchestration.revision_service import TrainingPathRevisionService


def _payload(title: str) -> TrainingPathPayload:
    return TrainingPathPayload.model_validate(
        {
            "title": title,
            "phases": [
                {
                    "phase_id": "phase-product",
                    "title": "产品能力",
                    "outcome": "能独立讲解核心产品",
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "product-a",
                            "title": "产品 A",
                            "outcome": "能说明产品 A 的适用场景",
                            "order_index": 1,
                            "estimated_minutes": 35,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "activity-product-a-assignment",
                                    "type": "assignment",
                                    "title": "总结产品 A",
                                    "objective": "用客户语言总结产品 A",
                                    "why_it_matters": "客户只关心产品能解决什么问题",
                                    "steps": ["回顾资料", "整理要点", "提交总结"],
                                    "success_criteria": ["包含适用场景", "包含客户收益"],
                                    "primary_action_label": "开始整理总结",
                                    "order_index": 1,
                                    "estimated_minutes": 15,
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


async def _publish(test_db, actor, title):
    service = TrainingPathRevisionService(test_db)
    await service.save_draft(payload=_payload(title), actor=actor, reason=title)
    result = await service.publish(actor=actor, reason=title)
    await test_db.commit()
    return result.revision


@pytest.mark.asyncio
async def test_should_pin_revision_and_return_one_primary_next_action(
    test_db, test_user
):
    published = await _publish(test_db, test_user, "版本一")
    journey = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )

    detail = await NewcomerJourneyService(test_db).activity_detail(
        learner=test_user, activity_id="activity-product-a-assignment"
    )
    assert detail.runner.model_dump() == {
        "type": "assignment",
        "submission_type": "text",
        "review_mode": "automatic_complete",
        "max_file_size_bytes": 10485760,
    }

    assert journey.path_revision_id == published.revision_id
    assert journey.primary_next_action.activity_id == "activity-product-a-assignment"
    assert journey.phases[0].modules[0].estimated_minutes == 35
    assert journey.phases[0].modules[0].activities[0].estimated_minutes == 15
    assert journey.phases[0].outcome == "能独立讲解核心产品"
    assert journey.phases[0].modules[0].outcome == "能说明产品 A 的适用场景"
    activity = journey.phases[0].modules[0].activities[0]
    assert activity.objective == "用客户语言总结产品 A"
    assert activity.why_it_matters == "客户只关心产品能解决什么问题"
    assert activity.steps == ["回顾资料", "整理要点", "提交总结"]
    assert activity.success_criteria == ["包含适用场景", "包含客户收益"]
    assert journey.primary_next_action.label == "开始整理总结"
    assert (
        sum(
            activity.is_primary_next_action
            for phase in journey.phases
            for module in phase.modules
            for activity in module.activities
        )
        == 1
    )


@pytest.mark.asyncio
async def test_should_keep_existing_enrollment_on_old_revision_after_publish(
    test_db, test_user
):
    first = await _publish(test_db, test_user, "版本一")
    before = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )
    await _publish(test_db, test_user, "版本二")
    after = await NewcomerJourneyService(test_db).get_or_create_for_learner(
        learner=test_user
    )

    assert before.path_revision_id == first.revision_id
    assert after.path_revision_id == first.revision_id
