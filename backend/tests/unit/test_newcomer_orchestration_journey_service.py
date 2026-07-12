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
                    "order_index": 1,
                    "modules": [
                        {
                            "module_id": "product-a",
                            "title": "产品 A",
                            "order_index": 1,
                            "completion_policy": {"mode": "all_required"},
                            "activities": [
                                {
                                    "activity_id": "activity-product-a-assignment",
                                    "type": "assignment",
                                    "title": "总结产品 A",
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
