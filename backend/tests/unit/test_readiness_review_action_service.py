from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import User
from sales_trainer.models import (
    SalesTrainerOperationLog,
    SalesTrainerReadinessReviewAction,
)
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.readiness_review_action_service import (
    ReadinessAuditContext,
    ReadinessReviewActionError,
    ReadinessReviewActionService,
)
from sales_trainer.services.readiness_state import (
    READINESS_DOSSIER_TARGET_TYPE,
    REVIEW_ACTION_CREATED,
)


def _user(role: str, *, department: str | None = "销售一部") -> User:
    suffix = uuid.uuid4().hex
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"readiness-{role}-{suffix}",
        name=role,
        email=f"readiness-{role}-{suffix}@example.com",
        role=role,
        department=department,
    )


def _audit_context() -> ReadinessAuditContext:
    return ReadinessAuditContext(
        request_id="trace-readiness-review",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )


async def _persist_users(db: AsyncSession, *users: User) -> None:
    db.add_all(list(users))
    await db.commit()


async def _create(
    service: ReadinessReviewActionService,
    *,
    learner: User,
    actor: User,
    decision: str = "approve",
    reason: str = "证据完整。",
    capability_keys: list[str] | None = None,
    source_evidence_ids: list[str] | None = None,
    idempotency_key: str | None = None,
    expected_latest_review_action_id: str | None = None,
    team_department: str | None = None,
    request_capability_keys: list[str] | None = None,
    request_source_evidence_ids: list[str] | None = None,
) -> SalesTrainerReadinessReviewAction:
    return await service.create(
        learner_id=str(learner.user_id),
        actor=actor,
        team_department=team_department,
        decision=decision,  # type: ignore[arg-type]
        reason=reason,
        capability_keys=capability_keys or ["expression_clarity"],
        source_evidence_ids=source_evidence_ids or ["audio_submission:one"],
        idempotency_key=idempotency_key or f"review-{uuid.uuid4().hex}",
        expected_latest_review_action_id=expected_latest_review_action_id,
        audit_context=_audit_context(),
        request_capability_keys=request_capability_keys,
        request_source_evidence_ids=request_source_evidence_ids,
    )


@pytest.mark.asyncio
async def test_should_replay_same_request_before_version_conflict(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    key = "review-request-replay-0001"

    first = await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
    )
    replayed = await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
        # Deliberately stale after the first create. Idempotency wins.
        expected_latest_review_action_id=None,
    )

    action_count = await test_db.scalar(
        select(func.count()).select_from(SalesTrainerReadinessReviewAction)
    )
    audit_count = await test_db.scalar(
        select(func.count())
        .select_from(SalesTrainerOperationLog)
        .where(SalesTrainerOperationLog.action == REVIEW_ACTION_CREATED)
    )
    assert replayed.action_id == first.action_id
    assert action_count == 1
    assert audit_count == 1


@pytest.mark.asyncio
async def test_should_fingerprint_raw_lists_not_mutable_persistence_defaults(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    key = "review-request-dynamic-defaults-0001"

    first = await _create(
        service,
        learner=learner,
        actor=admin,
        capability_keys=["expression_clarity"],
        source_evidence_ids=["audio_submission:first-default"],
        request_capability_keys=[],
        request_source_evidence_ids=[],
        idempotency_key=key,
    )
    replayed = await _create(
        service,
        learner=learner,
        actor=admin,
        capability_keys=["objection_handling"],
        source_evidence_ids=["audio_submission:later-default"],
        request_capability_keys=[],
        request_source_evidence_ids=[],
        idempotency_key=key,
        expected_latest_review_action_id=None,
    )

    assert replayed.action_id == first.action_id
    assert replayed.capability_keys == ["expression_clarity"]
    assert replayed.source_evidence_ids == ["audio_submission:first-default"]

    with pytest.raises(ReadinessReviewActionError) as reused:
        await _create(
            service,
            learner=learner,
            actor=admin,
            capability_keys=["objection_handling"],
            source_evidence_ids=["audio_submission:later-default"],
            request_capability_keys=["objection_handling"],
            request_source_evidence_ids=["audio_submission:later-default"],
            idempotency_key=key,
            expected_latest_review_action_id=None,
        )
    assert reused.value.code == "[READINESS_IDEMPOTENCY_KEY_REUSED]"


@pytest.mark.asyncio
async def test_should_reject_same_idempotency_key_with_different_body(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    key = "review-request-reused-0001"
    await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
    )

    with pytest.raises(ReadinessReviewActionError) as error:
        await _create(
            service,
            learner=learner,
            actor=admin,
            decision="require_retraining",
            reason="需要重练。",
            idempotency_key=key,
        )

    assert error.value.code == "[READINESS_IDEMPOTENCY_KEY_REUSED]"
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_should_replay_after_unique_constraint_race(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    key = "review-request-race-replay-0001"
    first = await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
    )
    first_id = str(first.action_id)
    original_find = service._find_idempotent
    find_calls = 0

    async def miss_before_unique_conflict(
        *, actor_id: str, key: str
    ) -> SalesTrainerReadinessReviewAction | None:
        nonlocal find_calls
        find_calls += 1
        if find_calls == 1:
            return None
        return await original_find(actor_id=actor_id, key=key)

    monkeypatch.setattr(service, "_find_idempotent", miss_before_unique_conflict)

    replayed = await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
        expected_latest_review_action_id=first_id,
    )

    assert find_calls == 2
    assert replayed.action_id == first_id
    assert (
        await test_db.scalar(
            select(func.count()).select_from(SalesTrainerReadinessReviewAction)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_should_reject_different_body_after_unique_constraint_race(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    key = "review-request-race-reused-0001"
    first = await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
    )
    first_id = str(first.action_id)
    original_find = service._find_idempotent
    find_calls = 0

    async def miss_before_unique_conflict(
        *, actor_id: str, key: str
    ) -> SalesTrainerReadinessReviewAction | None:
        nonlocal find_calls
        find_calls += 1
        if find_calls == 1:
            return None
        return await original_find(actor_id=actor_id, key=key)

    monkeypatch.setattr(service, "_find_idempotent", miss_before_unique_conflict)

    with pytest.raises(ReadinessReviewActionError) as error:
        await _create(
            service,
            learner=learner,
            actor=admin,
            decision="require_retraining",
            reason="同一标识下的不同内容。",
            idempotency_key=key,
            expected_latest_review_action_id=first_id,
        )

    assert find_calls == 2
    assert error.value.code == "[READINESS_IDEMPOTENCY_KEY_REUSED]"
    assert error.value.status_code == 409
    assert (
        await test_db.scalar(
            select(func.count()).select_from(SalesTrainerReadinessReviewAction)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_should_not_swallow_non_idempotency_integrity_error(
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    key = "review-request-non-idempotency-0001"
    first = await _create(
        service,
        learner=learner,
        actor=admin,
        idempotency_key=key,
    )
    first_id = str(first.action_id)
    original_find = service._find_idempotent
    find_calls = 0

    async def miss_before_integrity_error(
        *, actor_id: str, key: str
    ) -> SalesTrainerReadinessReviewAction | None:
        nonlocal find_calls
        find_calls += 1
        if find_calls == 1:
            return None
        return await original_find(actor_id=actor_id, key=key)

    async def fail_with_other_constraint(*_: Any, **__: Any) -> None:
        raise IntegrityError(
            "INSERT INTO sales_trainer_readiness_review_actions",
            {},
            RuntimeError(
                "UNIQUE constraint failed: "
                "sales_trainer_readiness_review_actions.action_id"
            ),
        )

    monkeypatch.setattr(service, "_find_idempotent", miss_before_integrity_error)
    monkeypatch.setattr(test_db, "flush", fail_with_other_constraint)

    with pytest.raises(IntegrityError, match="action_id"):
        await _create(
            service,
            learner=learner,
            actor=admin,
            idempotency_key=key,
            expected_latest_review_action_id=first_id,
        )

    assert find_calls == 1


@pytest.mark.asyncio
async def test_should_reject_stale_expected_latest_action_id(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    first = await _create(service, learner=learner, actor=admin)

    with pytest.raises(ReadinessReviewActionError) as error:
        await _create(
            service,
            learner=learner,
            actor=admin,
            decision="mark_manual_follow_up",
            reason="需要人工跟进。",
            expected_latest_review_action_id=None,
        )

    assert error.value.code == "[READINESS_REVIEW_VERSION_CONFLICT]"
    assert error.value.status_code == 409
    assert error.value.details == {"latest_review_action_id": str(first.action_id)}


@pytest.mark.asyncio
async def test_should_accept_legacy_log_id_as_first_canonical_version(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    legacy = await OperationLogService(test_db).record(
        actor=admin,
        action=REVIEW_ACTION_CREATED,
        target_type=READINESS_DOSSIER_TARGET_TYPE,
        target_id=str(learner.user_id),
        metadata={
            "decision": "approve",
            "reason": "历史复核。",
            "state_storage": "operation_log",
        },
    )
    await test_db.commit()
    service = ReadinessReviewActionService(test_db)

    with pytest.raises(ReadinessReviewActionError) as conflict:
        await _create(
            service,
            learner=learner,
            actor=admin,
            decision="mark_manual_follow_up",
            reason="需要补充人工复核。",
            expected_latest_review_action_id=None,
        )
    action = await _create(
        service,
        learner=learner,
        actor=admin,
        decision="mark_manual_follow_up",
        reason="需要补充人工复核。",
        expected_latest_review_action_id=str(legacy.log_id),
    )

    assert conflict.value.code == "[READINESS_REVIEW_VERSION_CONFLICT]"
    assert conflict.value.details["latest_review_action_id"] == str(legacy.log_id)
    assert action.expected_previous_action_id == str(legacy.log_id)


@pytest.mark.asyncio
async def test_should_exclude_canonical_audit_mirror_from_version_baseline(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    first = await _create(service, learner=learner, actor=admin)

    second = await _create(
        service,
        learner=learner,
        actor=admin,
        decision="require_retraining",
        reason="表达稳定性不足。",
        expected_latest_review_action_id=str(first.action_id),
    )

    assert second.expected_previous_action_id == str(first.action_id)
    assert second.retraining_task == {
        "task_id": f"retraining:{second.action_id}",
        "status": "pending",
        "source": "readiness_review_action",
        "capability_keys": ["expression_clarity"],
        "source_evidence_ids": ["audio_submission:one"],
        "target_learner_id": str(learner.user_id),
    }


@pytest.mark.asyncio
async def test_should_enforce_role_and_department_scope_inside_service(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin", department="总部")
    manager = _user("training_manager", department="华东销售")
    same_department = _user("user", department="华东销售")
    other_department = _user("user", department="华南销售")
    ops = _user("operations", department="华东销售")
    content_admin = _user("content_admin", department="华东销售")
    ordinary_user = _user("user", department="华东销售")
    await _persist_users(
        test_db,
        admin,
        manager,
        same_department,
        other_department,
        ops,
        content_admin,
        ordinary_user,
    )
    service = ReadinessReviewActionService(test_db)

    allowed = await _create(
        service,
        learner=same_department,
        actor=manager,
        team_department="华东销售",
    )
    with pytest.raises(ReadinessReviewActionError) as outside_scope:
        await _create(
            service,
            learner=other_department,
            actor=manager,
            # Passing None must not make a manager global.
            team_department=None,
        )
    global_action = await _create(
        service,
        learner=other_department,
        actor=admin,
        team_department=None,
    )
    denied_errors: list[ReadinessReviewActionError] = []
    for denied_actor in (ops, content_admin, ordinary_user):
        with pytest.raises(ReadinessReviewActionError) as role_required:
            await _create(
                service,
                learner=same_department,
                actor=denied_actor,
                team_department=None,
            )
        denied_errors.append(role_required.value)

    assert allowed.actor_id == str(manager.user_id)
    assert global_action.actor_id == str(admin.user_id)
    assert outside_scope.value.code == "[TRAINING_RECORD_NOT_FOUND]"
    assert outside_scope.value.status_code == 404
    assert [error.code for error in denied_errors] == [
        "[READINESS_REVIEW_ROLE_REQUIRED]",
        "[READINESS_REVIEW_ROLE_REQUIRED]",
        "[READINESS_REVIEW_ROLE_REQUIRED]",
    ]
    assert all(error.status_code == 403 for error in denied_errors)


@pytest.mark.asyncio
async def test_should_reject_decisions_outside_append_only_allowlist(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)

    with pytest.raises(ReadinessReviewActionError) as error:
        await _create(
            ReadinessReviewActionService(test_db),
            learner=learner,
            actor=admin,
            decision="revoke",
            reason="不支持撤销。",
        )

    assert error.value.code == "[READINESS_REVIEW_DECISION_INVALID]"
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_should_roll_back_action_when_audit_write_fails(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)

    class FailingOperationLogs:
        async def record(self, **_: Any) -> SalesTrainerOperationLog:
            raise RuntimeError("audit unavailable")

        async def list_logs(
            self, **_: Any
        ) -> tuple[list[SalesTrainerOperationLog], int]:
            return [], 0

    service = ReadinessReviewActionService(
        test_db,
        logs=FailingOperationLogs(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await _create(service, learner=learner, actor=admin)
    await test_db.rollback()

    action_count = await test_db.scalar(
        select(func.count()).select_from(SalesTrainerReadinessReviewAction)
    )
    assert action_count == 0


@pytest.mark.asyncio
async def test_should_list_append_only_actions_newest_first(
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    await _persist_users(test_db, admin, learner)
    service = ReadinessReviewActionService(test_db)
    first = await _create(service, learner=learner, actor=admin)
    second = await _create(
        service,
        learner=learner,
        actor=admin,
        decision="mark_manual_follow_up",
        reason="需要主管跟进。",
        expected_latest_review_action_id=str(first.action_id),
    )

    actions = await service.list_for_learner(str(learner.user_id))

    assert [item.action_id for item in actions] == [
        second.action_id,
        first.action_id,
    ]
