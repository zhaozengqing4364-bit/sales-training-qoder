from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.orchestration.repository import (
    AttemptRepository,
    EnrollmentRepository,
)


async def _published_revision(
    test_db, *, revision_no: int = 1
) -> SalesTrainerAssetRevision:
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
async def test_should_sync_existing_enrollment_to_current_published_revision(
    test_db, test_user
):
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
    assert second.path_revision_id == second_revision.revision_id


@pytest.mark.asyncio
async def test_should_keep_attempt_snapshot_on_original_revision_when_enrollment_syncs(
    test_db, test_user
):
    first_revision = await _published_revision(test_db)
    second_revision = await _published_revision(test_db, revision_no=2)
    repository = EnrollmentRepository(test_db)
    enrollment = await repository.get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=first_revision.revision_id,
    )
    attempt = await AttemptRepository(test_db).create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=first_revision.revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot={"title": "旧版小测"},
        client_token="sync-history-token",
    )

    synced = await repository.get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=second_revision.revision_id,
    )

    assert synced.path_revision_id == second_revision.revision_id
    assert attempt.path_revision_id == first_revision.revision_id
    assert attempt.activity_snapshot == {"title": "旧版小测"}


@pytest.mark.asyncio
async def test_should_create_first_attempt_when_no_prior_attempts(test_db, test_user):
    revision = await _published_revision(test_db)
    enrollment = await EnrollmentRepository(test_db).get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=revision.revision_id,
    )
    attempt = await AttemptRepository(test_db).create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-first",
        activity_type="quiz",
        activity_snapshot={},
        client_token="first-attempt-token",
    )
    assert attempt.attempt_no == 1


@pytest.mark.asyncio
async def test_should_lock_latest_attempt_row_without_max_aggregate(
    test_db, test_user, monkeypatch
):
    revision = await _published_revision(test_db)
    enrollment = await EnrollmentRepository(test_db).get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=revision.revision_id,
    )
    repository = AttemptRepository(test_db)
    await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-lock",
        activity_type="quiz",
        activity_snapshot={},
        client_token="lock-token-1",
    )

    captured: list[Any] = []
    original_scalar = test_db.scalar

    async def _capture_scalar(statement: Any, *args: Any, **kwargs: Any) -> Any:
        captured.append(statement)
        return await original_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(test_db, "scalar", _capture_scalar)

    second = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-lock",
        activity_type="quiz",
        activity_snapshot={},
        client_token="lock-token-2",
    )
    assert second.attempt_no == 2

    lock_statements = [
        stmt
        for stmt in captured
        if getattr(stmt, "_for_update_arg", None) is not None
        or "FOR UPDATE"
        in str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": False},
            )
        ).upper()
    ]
    assert lock_statements, "expected a FOR UPDATE lock query during create"
    compiled = str(
        lock_statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).upper()
    assert "FOR UPDATE" in compiled
    assert "MAX(" not in compiled


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
    assert (
        await repository.latest_for_activity(
            enrollment_id=enrollment.enrollment_id, activity_id="activity-a"
        )
        == second
    )


@pytest.mark.asyncio
async def test_should_load_latest_attempts_for_an_enrollment_in_one_projection(
    test_db, test_user
):
    revision = await _published_revision(test_db)
    enrollment = await EnrollmentRepository(test_db).get_or_create(
        learner_id=str(test_user.user_id),
        path_id="default",
        path_revision_id=revision.revision_id,
    )
    repository = AttemptRepository(test_db)
    first_a = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot={},
        client_token="batch-token-a1",
    )
    latest_a = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-a",
        activity_type="quiz",
        activity_snapshot={},
        client_token="batch-token-a2",
    )
    latest_b = await repository.create(
        enrollment_id=enrollment.enrollment_id,
        path_revision_id=enrollment.path_revision_id,
        activity_id="activity-b",
        activity_type="assignment",
        activity_snapshot={},
        client_token="batch-token-b1",
    )

    attempts = await repository.latest_for_enrollment(
        enrollment_id=enrollment.enrollment_id
    )

    assert attempts == {"activity-a": latest_a, "activity-b": latest_b}
    assert attempts["activity-a"] != first_a
