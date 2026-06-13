from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.models import (
    SalesTrainerAiCoachSession,
    SalesTrainerAudioSubmission,
    SalesTrainerMaterial,
    SalesTrainerMaterialVersion,
    SalesTrainerQuizAttempt,
    SalesTrainerUnit,
)


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str, *, department: str | None = None) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"phase2-contract-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Phase2 Contract {role}",
        email=f"phase2-contract-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        department=department,
    )


def _unit(admin: User, *, name: str = "阶段 2 训练") -> SalesTrainerUnit:
    return SalesTrainerUnit(
        unit_id=str(uuid.uuid4()),
        name=name,
        unit_type="quiz",
        config={},
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )


@pytest.mark.asyncio
async def test_manager_dashboard_should_match_phase2_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user", department="销售一部")
    unit = _unit(admin)
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=55,
        max_score=100,
        passed=False,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    test_db.add_all([admin, learner, unit, attempt])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/manager-dashboard",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["policy"]["key"] == "sales_trainer.phase2.closed_loop_policy"
    assert data["summary"]["record_count"] == 1
    assert data["summary"]["low_score_record_count"] == 1
    assert data["risk_learners"][0]["suggested_action"]
    assert data["intervention_suggestions"][0]["action"]


@pytest.mark.asyncio
async def test_training_records_should_page_after_unified_union_window(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit(admin)
    base = datetime(2026, 6, 12, tzinfo=UTC)
    attempts = [
        SalesTrainerQuizAttempt(
            attempt_id=str(uuid.uuid4()),
            unit_id=unit.unit_id,
            user_id=learner.user_id,
            total_score=80,
            max_score=100,
            passed=True,
            status="scored",
            submitted_at=base + timedelta(seconds=index),
        )
        for index in range(505)
    ]
    test_db.add_all([admin, learner, unit, *attempts])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records?limit=1&offset=500",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 505
    assert data["items"][0]["record_id"] == attempts[4].attempt_id
    assert data["items"][0]["score"] == 80
    assert data["items"][0]["effective_score"]["score"] == 80


@pytest.mark.asyncio
async def test_training_record_detail_should_cover_all_record_types(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit(admin)
    audio = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/pitch.wav",
        status="uploaded",
        created_at=datetime.now(UTC),
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=90,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        module_key="business_skills",
        status="in_progress",
        trace_id="trace-phase2-detail",
        created_at=datetime.now(UTC),
    )
    test_db.add_all([admin, learner, unit, audio, attempt, session])
    await test_db.commit()

    for record_type, record_id in (
        ("audio_submission", audio.submission_id),
        ("quiz_attempt", attempt.attempt_id),
        ("ai_coach_session", session.session_id),
    ):
        response = await async_client.get(
            f"/api/v1/admin/sales-trainer/training-records/detail/{record_type}/{record_id}",
            headers=_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["record_type"] == record_type
        assert data["effective_score"] is not None
        assert data["score_explanation"] is not None
        assert data["ability_profile"] is not None
        assert data["remediation"] is not None

    unit_filter = await async_client.get(
        f"/api/v1/admin/sales-trainer/training-records?unit_id={unit.unit_id}",
        headers=_headers(admin),
    )
    assert unit_filter.status_code == 200
    assert {
        item["record_type"] for item in unit_filter.json()["data"]["items"]
    } == {"audio_submission", "quiz_attempt"}


@pytest.mark.asyncio
async def test_training_records_material_version_filter_should_only_match_audio(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    unit = _unit(admin)
    material = SalesTrainerMaterial(
        material_id=str(uuid.uuid4()),
        material_key=f"phase2-{uuid.uuid4().hex[:8]}",
        name="阶段 2 材料",
        material_type="ppt_deck",
        purpose="ppt_pitch",
        status="published",
        created_by=admin.user_id,
        updated_by=admin.user_id,
    )
    version = SalesTrainerMaterialVersion(
        version_id=str(uuid.uuid4()),
        material_id=material.material_id,
        version_label="v1",
        title="阶段 2 材料 v1",
        file_name="phase2.pdf",
        content_type="application/pdf",
        file_size_bytes=1024,
        storage_key="/tmp/phase2.pdf",
        status="published",
        created_by=admin.user_id,
    )
    material.current_version_id = version.version_id
    audio = SalesTrainerAudioSubmission(
        submission_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        purpose="ppt_pitch",
        original_filename="pitch.wav",
        content_type="audio/wav",
        size_bytes=1024,
        storage_key="/tmp/pitch.wav",
        confirmed_material_version_id=version.version_id,
        status="uploaded",
        created_at=datetime.now(UTC),
    )
    attempt = SalesTrainerQuizAttempt(
        attempt_id=str(uuid.uuid4()),
        unit_id=unit.unit_id,
        user_id=learner.user_id,
        total_score=90,
        max_score=100,
        passed=True,
        status="scored",
        submitted_at=datetime.now(UTC),
    )
    session = SalesTrainerAiCoachSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        module_key="business_skills",
        status="in_progress",
        trace_id="trace-phase2-material-filter",
    )
    test_db.add_all([
        admin,
        learner,
        unit,
        material,
        version,
        audio,
        attempt,
        session,
    ])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records"
        f"?material_version_id={version.version_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["record_type"] == "audio_submission"


@pytest.mark.asyncio
async def test_training_records_should_filter_department_scope(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    manager = _user("training_manager", department="销售一部")
    admin = _user("admin")
    learner_a = _user("user", department="销售一部")
    learner_b = _user("user", department="销售二部")
    unit = _unit(admin)
    attempts = [
        SalesTrainerQuizAttempt(
            attempt_id=str(uuid.uuid4()),
            unit_id=unit.unit_id,
            user_id=learner_a.user_id,
            total_score=80,
            max_score=100,
            passed=True,
            status="scored",
            submitted_at=datetime.now(UTC),
        ),
        SalesTrainerQuizAttempt(
            attempt_id=str(uuid.uuid4()),
            unit_id=unit.unit_id,
            user_id=learner_b.user_id,
            total_score=80,
            max_score=100,
            passed=True,
            status="scored",
            submitted_at=datetime.now(UTC),
        ),
    ]
    test_db.add_all([manager, admin, learner_a, learner_b, unit, *attempts])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/admin/sales-trainer/training-records",
        headers=_headers(manager),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["user_id"] == learner_a.user_id
