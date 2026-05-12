from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import ReleaseVerificationRecord, User

BASE_PATH = "/api/v1/admin/release-verification"


async def _user(
    db: AsyncSession,
    *,
    role: str,
    email_prefix: str,
) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"{email_prefix}_{uuid.uuid4().hex[:8]}",
        name=f"{role.title()} Release Contract Tester",
        department="QA",
        email=f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(test_db: AsyncSession) -> dict[str, str]:
    admin = await _user(test_db, role="admin", email_prefix="release-admin")
    return _headers(admin)


@pytest.fixture
async def user_headers(test_db: AsyncSession) -> dict[str, str]:
    user = await _user(test_db, role="user", email_prefix="release-user")
    return _headers(user)


def _assert_success_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    assert payload["success"] is True
    assert "data" in payload
    assert "trace_id" in payload
    return payload["data"]


def _assert_error_envelope(payload: dict[str, Any], error_code: str) -> None:
    assert payload["success"] is False
    assert payload["error"] == error_code
    assert isinstance(payload["message"], str)
    assert "trace_id" in payload


async def _create_candidate(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    *,
    release_candidate_id: str | None = None,
    release_version: str | None = None,
    use_default_checks: bool = False,
) -> dict[str, Any]:
    rc_id = release_candidate_id or f"rc-{uuid.uuid4().hex[:10]}"
    version = release_version or f"v{uuid.uuid4().hex[:8]}"
    payload: dict[str, Any] = {
        "release_version": version,
        "release_candidate_id": rc_id,
    }
    if not use_default_checks:
        payload["checks"] = [
            {
                "check_type": "migration",
                "check_name": "Migration check",
                "check_description": "Migration smoke contract check",
            },
            {
                "check_type": "contract",
                "check_name": "Contract check",
                "check_description": "API contract check",
            },
        ]
    response = await async_client.post(
        f"{BASE_PATH}/candidates",
        headers=admin_headers,
        json=payload,
    )
    assert response.status_code == 200
    return _assert_success_envelope(response.json())


async def _record_ids(db: AsyncSession, release_candidate_id: str) -> list[str]:
    result = await db.execute(
        select(ReleaseVerificationRecord.record_id)
        .where(ReleaseVerificationRecord.release_candidate_id == release_candidate_id)
        .order_by(ReleaseVerificationRecord.created_at)
    )
    return [str(record_id) for record_id in result.scalars().all()]


async def _record_ids_by_type(
    db: AsyncSession, release_candidate_id: str
) -> dict[str, str]:
    result = await db.execute(
        select(ReleaseVerificationRecord)
        .where(ReleaseVerificationRecord.release_candidate_id == release_candidate_id)
        .order_by(ReleaseVerificationRecord.created_at)
    )
    return {record.check_type: str(record.record_id) for record in result.scalars().all()}


async def _complete_candidate_checks(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    release_candidate_id: str,
    *,
    failed_record: str | None = None,
) -> None:
    for record_id in await _record_ids(db, release_candidate_id):
        failed = record_id == failed_record
        response = await async_client.put(
            f"{BASE_PATH}/checks/{record_id}",
            headers=admin_headers,
            json={
                "status": "failed" if failed else "passed",
                "passed": not failed,
                "details": {"contract": True},
                "error_message": "contract failure" if failed else None,
                "duration_ms": 12,
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_requires_admin_for_all_contract_endpoints(
    async_client: AsyncClient,
    user_headers: dict[str, str],
) -> None:
    endpoints: list[tuple[str, str, dict[str, Any] | None]] = [
        (
            "POST",
            f"{BASE_PATH}/candidates",
            {"release_version": "v0", "release_candidate_id": "rc-auth"},
        ),
        ("GET", f"{BASE_PATH}/candidates", None),
        ("GET", f"{BASE_PATH}/candidates/latest", None),
        ("GET", f"{BASE_PATH}/candidates/missing/report", None),
        (
            "PUT",
            f"{BASE_PATH}/checks/missing",
            {"status": "passed", "passed": True},
        ),
        (
            "POST",
            f"{BASE_PATH}/candidates/missing/decision",
            {"decision": "go", "reason": "auth contract"},
        ),
        ("POST", f"{BASE_PATH}/candidates/missing/run-verification", None),
        ("GET", f"{BASE_PATH}/candidates/missing/quality-gate", None),
        ("POST", f"{BASE_PATH}/candidates/missing/auto-decision", None),
    ]

    for method, path, body in endpoints:
        response = await async_client.request(
            method,
            path,
            headers=user_headers,
            json=body,
        )
        assert response.status_code == 403, f"{method} {path}"
        payload = response.json()
        assert payload["detail"]["error"] == "[PERMISSION_REQUIRED]"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_candidate_list_latest_report_and_update_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    rc_id = f"rc-contract-{uuid.uuid4().hex[:8]}"
    created = await _create_candidate(
        async_client,
        admin_headers,
        release_candidate_id=rc_id,
        release_version=f"v-{uuid.uuid4().hex[:8]}",
    )
    assert created["release_candidate_id"] == rc_id
    assert created["total_checks"] == 2
    assert created["pending_checks"] == 2

    list_response = await async_client.get(
        f"{BASE_PATH}/candidates",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    listed = _assert_success_envelope(list_response.json())
    assert listed["total"] >= 1
    assert any(candidate["release_candidate_id"] == rc_id for candidate in listed["candidates"])

    latest_response = await async_client.get(
        f"{BASE_PATH}/candidates/latest",
        headers=admin_headers,
    )
    assert latest_response.status_code == 200
    latest = _assert_success_envelope(latest_response.json())
    assert latest["candidate"]["release_candidate_id"] == rc_id

    report_response = await async_client.get(
        f"{BASE_PATH}/candidates/{rc_id}/report",
        headers=admin_headers,
    )
    assert report_response.status_code == 200
    report = _assert_success_envelope(report_response.json())
    assert report["summary"]["release_candidate_id"] == rc_id
    assert len(report["checks"]) == 2
    assert "migration" in report["gate_status"]
    assert isinstance(report["recommendations"], list)

    record_id = (await _record_ids(test_db, rc_id))[0]
    update_response = await async_client.put(
        f"{BASE_PATH}/checks/{record_id}",
        headers=admin_headers,
        json={
            "status": "passed",
            "passed": True,
            "details": {"coverage_percentage": 88.0},
            "duration_ms": 25,
        },
    )
    assert update_response.status_code == 200
    updated = _assert_success_envelope(update_response.json())
    assert updated["record_id"] == record_id
    assert updated["status"] == "passed"
    assert updated["passed"] is True


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_missing_resources_return_error_envelope(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    missing_report = await async_client.get(
        f"{BASE_PATH}/candidates/missing-report/report",
        headers=admin_headers,
    )
    assert missing_report.status_code == 200
    _assert_error_envelope(missing_report.json(), "[SUMMARY_NOT_FOUND]")

    missing_check = await async_client.put(
        f"{BASE_PATH}/checks/missing-record",
        headers=admin_headers,
        json={"status": "passed", "passed": True},
    )
    assert missing_check.status_code == 200
    _assert_error_envelope(missing_check.json(), "[RECORD_NOT_FOUND]")

    missing_gate = await async_client.get(
        f"{BASE_PATH}/candidates/missing-gate/quality-gate",
        headers=admin_headers,
    )
    assert missing_gate.status_code == 200
    _assert_error_envelope(missing_gate.json(), "[SUMMARY_NOT_FOUND]")


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_rejects_invalid_status_and_decision_payloads(
    async_client: AsyncClient,
    test_db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    rc_id = f"rc-invalid-{uuid.uuid4().hex[:8]}"
    await _create_candidate(async_client, admin_headers, release_candidate_id=rc_id)
    record_id = (await _record_ids(test_db, rc_id))[0]

    invalid_status = await async_client.put(
        f"{BASE_PATH}/checks/{record_id}",
        headers=admin_headers,
        json={"status": "unknown", "passed": True},
    )
    assert invalid_status.status_code == 422

    invalid_decision = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/decision",
        headers=admin_headers,
        json={"decision": "ship_it", "reason": "invalid enum"},
    )
    assert invalid_decision.status_code == 422


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_decision_requires_completed_checks_and_records_decision(
    async_client: AsyncClient,
    test_db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    rc_id = f"rc-decision-{uuid.uuid4().hex[:8]}"
    await _create_candidate(async_client, admin_headers, release_candidate_id=rc_id)

    pending_decision = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/decision",
        headers=admin_headers,
        json={"decision": "go", "reason": "try before complete"},
    )
    assert pending_decision.status_code == 200
    _assert_error_envelope(pending_decision.json(), "[PENDING_CHECKS_EXIST]")

    await _complete_candidate_checks(async_client, admin_headers, test_db, rc_id)
    decision_response = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/decision",
        headers=admin_headers,
        json={"decision": "go", "reason": "all checks passed"},
    )
    assert decision_response.status_code == 200
    decision = _assert_success_envelope(decision_response.json())
    assert decision["release_candidate_id"] == rc_id
    assert decision["go_no_go_decision"] == "go"
    assert decision["decision_reason"] == "all checks passed"
    assert decision["overall_status"] == "passed"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_quality_gate_and_auto_decision_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    rc_id = f"rc-auto-{uuid.uuid4().hex[:8]}"
    await _create_candidate(
        async_client,
        admin_headers,
        release_candidate_id=rc_id,
        use_default_checks=True,
    )

    pending_auto_decision = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/auto-decision",
        headers=admin_headers,
    )
    assert pending_auto_decision.status_code == 200
    _assert_error_envelope(pending_auto_decision.json(), "[PENDING_CHECKS_EXIST]")

    await _complete_candidate_checks(async_client, admin_headers, test_db, rc_id)

    gate_response = await async_client.get(
        f"{BASE_PATH}/candidates/{rc_id}/quality-gate",
        headers=admin_headers,
    )
    assert gate_response.status_code == 200
    gate = _assert_success_envelope(gate_response.json())
    assert gate["overall_status"] == "pass"
    assert gate["can_release"] is True
    assert gate["blocking_failures"] == []

    auto_decision = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/auto-decision",
        headers=admin_headers,
    )
    assert auto_decision.status_code == 200
    decision = _assert_success_envelope(auto_decision.json())
    assert decision["release_candidate_id"] == rc_id
    assert decision["go_no_go_decision"] == "go"
    assert decision["overall_status"] == "passed"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_auto_decision_blocks_failed_contract_gate(
    async_client: AsyncClient,
    test_db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    rc_id = f"rc-no-go-{uuid.uuid4().hex[:8]}"
    await _create_candidate(
        async_client,
        admin_headers,
        release_candidate_id=rc_id,
        use_default_checks=True,
    )
    record_ids_by_type = await _record_ids_by_type(test_db, rc_id)

    await _complete_candidate_checks(
        async_client,
        admin_headers,
        test_db,
        rc_id,
        failed_record=record_ids_by_type["contract"],
    )

    auto_decision = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/auto-decision",
        headers=admin_headers,
    )
    assert auto_decision.status_code == 200
    decision = _assert_success_envelope(auto_decision.json())
    assert decision["go_no_go_decision"] == "no_go"
    assert decision["overall_status"] == "failed"
    assert "Blocking failures" in decision["decision_reason"]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_release_verification_run_verification_endpoint_returns_contract_envelope(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rc_id = f"rc-run-{uuid.uuid4().hex[:8]}"
    await _create_candidate(async_client, admin_headers, release_candidate_id=rc_id)

    async def fake_run_all_checks(
        db: AsyncSession,
        release_candidate_id: str,
        skip_checks: list[str] | None = None,
    ):
        from common.error_handling.result import Result

        return Result(
            value={
                "release_candidate_id": release_candidate_id,
                "skip_checks": skip_checks,
                "checks": [],
                "summary": {"can_release": True},
            }
        )

    monkeypatch.setattr(
        "common.analytics.verification_runner.verification_runner.run_all_checks",
        fake_run_all_checks,
    )

    response = await async_client.post(
        f"{BASE_PATH}/candidates/{rc_id}/run-verification",
        headers=admin_headers,
        params={"skip_checks": ["performance"]},
    )
    assert response.status_code == 200
    data = _assert_success_envelope(response.json())
    assert data["release_candidate_id"] == rc_id
    assert data["skip_checks"] == ["performance"]
    assert data["summary"]["can_release"] is True
