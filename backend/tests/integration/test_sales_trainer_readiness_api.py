from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import (
    SalesTrainerOperationLog,
    SalesTrainerReadinessReviewAction,
)
from sales_trainer.services.readiness_state import REVIEW_ACTION_CREATED


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str, *, department: str | None = None) -> User:
    suffix = uuid.uuid4().hex
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"readiness-api-{role}-{suffix}",
        name=f"Readiness API {role}",
        email=f"readiness-api-{role}-{suffix}@example.com",
        role=role,
        department=department,
    )


def _review_payload(
    *,
    key: str,
    reason: str = "需要人工跟进。",
    expected_latest_review_action_id: str | None = None,
) -> dict[str, object]:
    return {
        "decision": "mark_manual_follow_up",
        "reason": reason,
        "capability_keys": [],
        "source_evidence_ids": [],
        "idempotency_key": key,
        "expected_latest_review_action_id": expected_latest_review_action_id,
    }


async def _post_review(
    client: AsyncClient,
    *,
    actor: User,
    learner: User,
    payload: dict[str, object],
):
    return await client.post(
        f"/api/v1/admin/sales-trainer/readiness/dossiers/{learner.user_id}/review-actions",
        headers=_auth_headers(actor),
        json=payload,
    )


async def _review_write_counts(db: AsyncSession) -> tuple[int, int]:
    action_count = await db.scalar(
        select(func.count()).select_from(SalesTrainerReadinessReviewAction)
    )
    audit_count = await db.scalar(
        select(func.count())
        .select_from(SalesTrainerOperationLog)
        .where(SalesTrainerOperationLog.action == REVIEW_ACTION_CREATED)
    )
    return int(action_count or 0), int(audit_count or 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "manager_role", ["support", "training_lead", "training_manager"]
)
async def test_should_allow_configured_training_manager_in_same_department(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    manager_role: str,
) -> None:
    monkeypatch.delenv("SALES_TRAINER_MANAGER_ROLES", raising=False)
    manager = _user(manager_role, department="华东销售")
    learner = _user("user", department="华东销售")
    test_db.add_all([manager, learner])
    await test_db.commit()

    response = await _post_review(
        async_client,
        actor=manager,
        learner=learner,
        payload=_review_payload(key=f"review-api-{manager_role}-0001"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["reviewer_id"] == str(manager.user_id)
    assert response.json()["data"]["state_storage"] == "readiness_review_action"


@pytest.mark.asyncio
async def test_should_allow_platform_admin_globally_and_hide_cross_department_records(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SALES_TRAINER_MANAGER_ROLES", raising=False)
    admin = _user("admin", department="总部")
    manager = _user("training_manager", department="华东销售")
    learner = _user("user", department="华南销售")
    test_db.add_all([admin, manager, learner])
    await test_db.commit()

    outside_response = await _post_review(
        async_client,
        actor=manager,
        learner=learner,
        payload=_review_payload(key="review-api-outside-manager-0001"),
    )
    admin_response = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=_review_payload(key="review-api-global-admin-0001"),
    )

    assert outside_response.status_code == 404
    assert outside_response.json()["error"] == "[TRAINING_RECORD_NOT_FOUND]"
    assert str(learner.user_id) not in str(outside_response.json())
    assert admin_response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("denied_role", ["operations", "content_admin", "user"])
async def test_should_keep_non_reviewer_roles_read_only(
    async_client: AsyncClient,
    test_db: AsyncSession,
    denied_role: str,
) -> None:
    actor = _user(denied_role, department="华东销售")
    learner = _user("user", department="华东销售")
    test_db.add_all([actor, learner])
    await test_db.commit()

    response = await _post_review(
        async_client,
        actor=actor,
        learner=learner,
        payload=_review_payload(key=f"review-api-denied-{denied_role}-0001"),
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[READINESS_REVIEW_ROLE_REQUIRED]"
    assert await _review_write_counts(test_db) == (0, 0)


@pytest.mark.asyncio
async def test_should_require_both_submission_preconditions(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    missing_idempotency = _review_payload(key="review-api-required-fields-0001")
    missing_idempotency.pop("idempotency_key")
    missing_version = _review_payload(key="review-api-required-fields-0002")
    missing_version.pop("expected_latest_review_action_id")

    idempotency_response = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=missing_idempotency,
    )
    version_response = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=missing_version,
    )

    assert idempotency_response.status_code == 422
    assert version_response.status_code == 422
    assert await _review_write_counts(test_db) == (0, 0)


@pytest.mark.asyncio
async def test_should_replay_same_body_once_and_reject_key_reuse(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    payload = _review_payload(key="review-api-idempotency-0001")

    first = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=payload,
    )
    replay = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=payload,
    )
    reused = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload={**payload, "reason": "同一标识下的不同内容。"},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["data"]["action_id"] == first.json()["data"]["action_id"]
    assert reused.status_code == 409
    assert reused.json()["error"] == "[READINESS_IDEMPOTENCY_KEY_REUSED]"
    assert (
        await test_db.scalar(
            select(func.count()).select_from(SalesTrainerReadinessReviewAction)
        )
        == 1
    )
    assert (
        await test_db.scalar(
            select(func.count())
            .select_from(SalesTrainerOperationLog)
            .where(SalesTrainerOperationLog.action == REVIEW_ACTION_CREATED)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_should_reject_stale_review_version_without_overwrite(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()

    first = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=_review_payload(key="review-api-version-0001"),
    )
    stale = await _post_review(
        async_client,
        actor=admin,
        learner=learner,
        payload=_review_payload(
            key="review-api-version-0002",
            reason="使用陈旧版本提交。",
            expected_latest_review_action_id=None,
        ),
    )

    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"] == "[READINESS_REVIEW_VERSION_CONFLICT]"
    assert (
        stale.json()["details"]["latest_review_action_id"]
        == (first.json()["data"]["action_id"])
    )
    assert (
        await test_db.scalar(
            select(func.count()).select_from(SalesTrainerReadinessReviewAction)
        )
        == 1
    )
