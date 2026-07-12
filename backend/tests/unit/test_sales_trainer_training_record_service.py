from __future__ import annotations

import uuid

import pytest

from sales_trainer.models import (
    NewcomerTrainingActivityAttempt,
    NewcomerTrainingEnrollment,
    SalesTrainerAssetRevision,
)
from sales_trainer.services.training_record_service import TrainingRecordService


@pytest.mark.asyncio
async def test_records_project_activity_identity_and_frozen_titles(test_db, test_user):
    revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="newcomer_training_path_orchestration",
        logical_id="default",
        revision_no=1,
        status="published",
        payload_json={},
        payload_hash=uuid.uuid4().hex,
    )
    enrollment = NewcomerTrainingEnrollment(
        learner_id=str(test_user.user_id),
        path_revision_id=revision.revision_id,
        path_id="default",
    )
    test_db.add_all([revision, enrollment])
    await test_db.flush()
    attempt = NewcomerTrainingActivityAttempt(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=revision.revision_id,
        activity_id="activity-product-a-quiz",
        activity_type="quiz",
        attempt_no=1,
        status="completed",
        client_token="record-token",
        activity_snapshot={
            "activity_id": "activity-product-a-quiz",
            "type": "quiz",
            "title": "产品 A 小测",
            "context": {
                "phase_id": "phase-product",
                "module_id": "product-a",
                "phase_title": "产品能力",
                "module_title": "产品 A",
            },
        },
    )
    test_db.add(attempt)
    await test_db.flush()

    records, total = await TrainingRecordService(test_db).list_records(
        user_id=str(test_user.user_id),
        activity_type="quiz",
        module_id="product-a",
        limit=20,
    )

    assert total == 1
    assert records[0]["activity_id"] == "activity-product-a-quiz"
    assert records[0]["activity_type"] == "quiz"
    assert records[0]["module_title"] == "产品 A"
    assert records[0]["activity_title"] == "产品 A 小测"
