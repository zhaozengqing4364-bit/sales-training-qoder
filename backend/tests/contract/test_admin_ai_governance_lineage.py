from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import (
    EvaluationRun,
    PracticeSession,
    Scenario,
    TrainingReportSnapshot,
    User,
)


async def _create_admin(test_db: AsyncSession) -> User:
    admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"lineage_admin_{uuid.uuid4().hex[:8]}",
        name="Lineage Admin",
        role="admin",
        is_active=True,
    )
    test_db.add(admin)
    await test_db.commit()
    return admin


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.contract
@pytest.mark.asyncio
async def test_report_lineage_prefers_session_evidence_projection_source(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _create_admin(test_db)
    learner = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"lineage_user_{uuid.uuid4().hex[:8]}",
        name="Lineage Learner",
        role="user",
        is_active=True,
    )
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name=f"lineage_sales_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=learner.user_id,
        scenario_id=scenario.scenario_id,
        status="completed",
        report_status="completed",
    )
    run = EvaluationRun(
        run_id=str(uuid.uuid4()),
        session_id=session.session_id,
        status="succeeded",
        input_evidence_reference={
            "source": "session_evidence_projection",
            "ruleset_version": "session_evidence_projection_v1",
        },
        result_payload={"overall_score": 84},
    )
    snapshot = TrainingReportSnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session.session_id,
        evaluation_run_id=run.run_id,
        report_payload={
            "overall_score": 84,
            "scoring_metadata": {"source": "admin"},
        },
        ruleset_source="admin",
        ruleset_version="sales-admin-v2",
        score_basis="configured_scoring_ruleset_weighted_canonical_dimensions",
        evidence_completeness={"conversation": True},
        generated_at=datetime.now(UTC),
    )
    test_db.add_all([learner, scenario, session, run, snapshot])
    await test_db.commit()

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session.session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["report"]["lineage"]["ruleset_source"] == (
        "session_evidence_projection"
    )
    assert payload["report"]["payload"]["scoring_metadata"]["source"] == "admin"
