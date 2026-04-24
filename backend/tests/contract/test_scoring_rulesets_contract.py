from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User


@pytest.mark.contract
@pytest.mark.asyncio
async def test_admin_scoring_ruleset_active_contract_returns_default_schema(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin_{uuid.uuid4().hex[:8]}",
        name="Contract Admin",
        department="QA",
        email=f"contract-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        is_active=True,
    )
    test_db.add(admin)
    await test_db.commit()

    token = create_access_token(data={"sub": str(admin.user_id)})
    response = await async_client.get(
        "/api/v1/evaluation/admin/scoring-rulesets/active",
        params={"scenario_type": "sales"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["trace_id"], str) or payload["trace_id"] is None
    data = payload["data"]
    assert data["scenario_type"] == "sales"
    assert data["version"] == "session_evidence_projection_v1"
    assert data["status"] == "published"
    assert data["is_active"] is True
    assert data["source"] == "default"
    assert data["definition"]["schema_version"] == "scoring_ruleset_schema_v1"
    assert data["definition"]["score_basis"] == "session_evidence_projection_evaluable_only"
    assert data["definition"]["dimensions"]
    assert {
        "dimension_id",
        "label",
        "weight",
        "rollup_contributions",
        "min_evidence",
    }.issubset(data["definition"]["dimensions"][0])
    assert data["definition"]["min_evidence"]["require_score_evidence"] is True
