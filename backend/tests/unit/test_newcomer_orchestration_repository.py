from __future__ import annotations

import uuid

import pytest

from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.orchestration.repository import (
    AttemptRepository,
    EnrollmentRepository,
)


async def _published_revision(test_db, *, revision_no: int = 1) -> SalesTrainerAssetRevision:
    revision = SalesTrainerAssetRevision(
        revision_id=str(uuid.uuid4()),
        resource_type="newcomer_training_path",
        logical_id="default",
        revision_no=revision_no,
        status="published",
        payload_json={},
        payload_hash=uuid.uuid4().hex,
    )
    test_db.add(revision)
    await test_db.flush()
    return revision


@pytest.mark.asyncio
async def test_should_pin_first_enrollment_to_published_revision(test_db, test_user):
    first_revision = await _published_revision(test_db)
    second_revision = await _published_revision(test_db, revision_no=2)
    repository = EnrollmentRepository(test_db)

    first = await repository.get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=first_revision.revision_id,
    )
    second = await repository.get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=second_revision.revision_id,
    )

    assert second.enrollment_id == first.enrollment_id
    assert second.path_revision_id == first_revision.revision_id


@pytest.mark.asyncio
async def test_should_make_attempt_creation_idempotent(test_db, test_user):
    revision = await _published_revision(test_db)
    enrollment = await EnrollmentRepository(test_db).get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=revision.revision_id,
    )
    repository = AttemptRepository(test_db)
    snapshot = {"activity_id": "activity-a", "type": "quiz"}

    first = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot=snapshot,
        client_token="client-token-1",
    )
    second = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot=snapshot,
        client_token="client-token-1",
    )

    assert second.attempt_id == first.attempt_id
    assert second.attempt_no == 1


@pytest.mark.asyncio
async def test_should_increment_attempt_number_per_activity(test_db, test_user):
    revision = await _published_revision(test_db)
    enrollment = await EnrollmentRepository(test_db).get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=revision.revision_id,
    )
    repository = AttemptRepository(test_db)

    first = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot={},
        client_token="client-token-1",
    )
    second = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot={},
        client_token="client-token-2",
    )

    assert (first.attempt_no, second.attempt_no) == (1, 2)
    assert await repository.latest_for_activity(
        enrollment_id=enrollment.enrollment_id, activity_id="activity-a"
    ) == second
