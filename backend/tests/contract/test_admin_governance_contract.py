from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from common.auth.service import create_access_token
from common.db.models import (
    BusinessRuleConfig,
    BusinessRuleConfigAuditLog,
    ConfigBundle,
    ConfigVersion,
    EvaluationRun,
    PracticeSession,
    Scenario,
    TrainingReportSnapshot,
    User,
)

GENERAL_DEFAULT = {
    "version": "admin_general_settings_v1",
    "enabled": True,
    "platform_name": "Intelligent Coach AI",
    "support_email": "support@company.com",
    "welcome_message": "欢迎使用高级训练平台，开启您的学习之旅！",
    "default_language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "date_format": "YYYY-MM-DD",
}


async def _create_admin(test_db: AsyncSession) -> User:
    admin = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"admin_{uuid.uuid4().hex[:8]}",
        name="Governance Admin",
        department="QA",
        email=f"governance-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        is_active=True,
    )
    test_db.add(admin)
    await test_db.commit()
    return admin


async def _create_user(test_db: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"user_{uuid.uuid4().hex[:8]}",
        name="Governance User",
        department="QA",
        email=f"governance-user-{uuid.uuid4().hex[:8]}@example.com",
        role="user",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    return user


async def _seed_explainable_session(
    test_db: AsyncSession,
    *,
    scenario_type: str,
) -> str:
    learner = await _create_user(test_db)
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type=scenario_type,
        name=f"{scenario_type}_explain_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=scenario.scenario_id,
        status="completed",
        report_status="completed",
        logic_score=82.0,
        accuracy_score=84.0,
        completeness_score=86.0,
    )
    bundle = ConfigBundle(
        bundle_id=str(uuid.uuid4()),
        bundle_key=f"{scenario_type}.explain.{uuid.uuid4().hex[:8]}",
        domain="scoring",
        display_name=f"{scenario_type} explain bundle",
        adapter_key="explainability_contract",
        read_path="/admin/config-bundles/explain",
        admin_entry="/admin/config-center",
        enabled=True,
    )
    version = ConfigVersion(
        version_id=str(uuid.uuid4()),
        bundle_id=bundle.bundle_id,
        source_config_id=str(uuid.uuid4()),
        version_number=3,
        version_label=f"{scenario_type}-v3",
        status="published",
        snapshot_json={
            "model": {"provider": "stepfun", "name": f"{scenario_type}-model"},
            "prompt": {"template_id": f"{scenario_type}-prompt"},
            "rag": {"profile": f"{scenario_type}-rag"},
            "knowledge": {"sources": [f"{scenario_type}-kb"]},
            "scoring": {"ruleset": f"{scenario_type}-rules"},
        },
        source_updated_at=datetime.now(UTC),
    )
    run = EvaluationRun(
        run_id=str(uuid.uuid4()),
        session_id=session.session_id,
        config_bundle_id=bundle.bundle_id,
        config_version_id=version.version_id,
        status="succeeded",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        input_evidence_reference={
            "conversation_messages": ["turn-1", "turn-2"],
            "evidence_sources": [f"{scenario_type}-transcript"],
        },
        result_payload={"overall_score": 84, "dimension_scores": {"logic": 82}},
        result_summary=f"{scenario_type} evaluation succeeded",
    )
    snapshot = TrainingReportSnapshot(
        snapshot_id=str(uuid.uuid4()),
        session_id=session.session_id,
        evaluation_run_id=run.run_id,
        report_payload={
            "report_id": f"{scenario_type}-report",
            "summary": f"{scenario_type} report summary",
            "evidence": {"highlights": ["turn-2"]},
        },
        config_bundle_id=bundle.bundle_id,
        config_bundle_snapshot={
            "source": "config_version",
            "config_bundle_id": bundle.bundle_id,
            "config_version_id": version.version_id,
            "bundle_key": bundle.bundle_key,
            "domain": bundle.domain,
            "version_number": version.version_number,
            "version_label": version.version_label,
            "status": version.status,
            "source_config_id": version.source_config_id,
            "ruleset_source": f"{scenario_type}_ruleset",
            "ruleset_version": "2026.05",
            "score_basis": "persisted_snapshot",
            "evidence_completeness": {"conversation": True, "knowledge": True},
            "config_snapshot": version.snapshot_json,
            "source_updated_at": version.source_updated_at.isoformat(),
        },
        ruleset_source=f"{scenario_type}_ruleset",
        ruleset_version="2026.05",
        score_basis="persisted_snapshot",
        evidence_completeness={"conversation": True, "knowledge": True},
        generated_at=datetime.now(UTC),
    )
    test_db.add_all([scenario, session, bundle, version, run, snapshot])
    await test_db.commit()
    return str(session.session_id)


async def _seed_session_without_lineage(
    test_db: AsyncSession,
    *,
    scenario_type: str = "sales",
) -> str:
    learner = await _create_user(test_db)
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type=scenario_type,
        name=f"{scenario_type}_missing_lineage_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=str(learner.user_id),
        scenario_id=scenario.scenario_id,
        status="completed",
        report_status="completed",
    )
    test_db.add_all([scenario, session])
    await test_db.commit()
    return str(session.session_id)


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.contract
@pytest.mark.asyncio
async def test_admin_governance_permissions_matrix_contract(async_client: AsyncClient, test_db: AsyncSession) -> None:
    admin = await _create_admin(test_db)
    response = await async_client.get(
        "/api/v1/admin/governance/permissions-matrix",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 1
    assert payload["items"]
    assert payload["support_log_redaction"]["diagnostic_allowlist"]
    assert payload["positive_control_route_families"]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_admin_governance_settings_backlog_contract(async_client: AsyncClient, test_db: AsyncSession) -> None:
    admin = await _create_admin(test_db)
    response = await async_client.get(
        "/api/v1/admin/governance/settings-backlog",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 1
    assert payload["items"]
    assert "/api/v1/admin/settings/{surface}" in payload["policy"]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_admin_settings_surface_defaults_validation_publish_rollback_and_audit(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _create_admin(test_db)
    headers = _headers(admin)

    default_response = await async_client.get(
        "/api/v1/admin/settings/general",
        headers=headers,
    )
    assert default_response.status_code == 200
    default_payload = default_response.json()["data"]
    assert default_payload["active"]["source"] == "default"
    assert default_payload["active"]["value"]["platform_name"] == "Intelligent Coach AI"

    preview_response = await async_client.post(
        "/api/v1/admin/settings/general/preview",
        headers=headers,
        json={
            "value": {**GENERAL_DEFAULT, "platform_name": "Coach QA"},
            "reason": "preview general settings",
        },
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["data"]["valid"] is True

    still_default = await async_client.get(
        "/api/v1/admin/settings/general",
        headers=headers,
    )
    assert still_default.json()["data"]["active"]["source"] == "default"

    invalid = await async_client.post(
        "/api/v1/admin/settings/general/drafts",
        headers=headers,
        json={
            "value": {**GENERAL_DEFAULT, "support_email": "not-an-email"},
            "reason": "invalid email must fail",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["success"] is False
    assert invalid.json()["error"] == "[ADMIN_SETTINGS_SCHEMA_INVALID]"

    draft_v1 = await async_client.post(
        "/api/v1/admin/settings/general/drafts",
        headers=headers,
        json={
            "value": {**GENERAL_DEFAULT, "platform_name": "Coach QA"},
            "reason": "save general v1",
        },
    )
    assert draft_v1.status_code == 200
    draft_v1_id = draft_v1.json()["data"]["id"]
    publish_v1 = await async_client.post(
        "/api/v1/admin/settings/general/publish",
        headers=headers,
        json={"config_id": draft_v1_id, "reason": "publish general v1"},
    )
    assert publish_v1.status_code == 200
    assert publish_v1.json()["data"]["status"] == "published"

    draft_v2 = await async_client.post(
        "/api/v1/admin/settings/general/drafts",
        headers=headers,
        json={
            "value": {**GENERAL_DEFAULT, "platform_name": "Coach QA 2"},
            "reason": "save general v2",
        },
    )
    draft_v2_id = draft_v2.json()["data"]["id"]
    await async_client.post(
        "/api/v1/admin/settings/general/publish",
        headers=headers,
        json={"config_id": draft_v2_id, "reason": "publish general v2"},
    )

    rollback = await async_client.post(
        "/api/v1/admin/settings/general/rollback",
        headers=headers,
        json={"target_config_id": draft_v1_id, "reason": "restore general v1"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["value"]["platform_name"] == "Coach QA"

    audit = await async_client.get(
        "/api/v1/admin/settings/general/audit",
        headers=headers,
    )
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["data"]["items"]]
    assert "preview" in actions
    assert "publish" in actions
    assert "rollback" in actions

    rows = (
        await test_db.execute(
            select(BusinessRuleConfig).where(
                BusinessRuleConfig.key == "admin.settings.general"
            )
        )
    ).scalars().all()
    audit_rows = (
        await test_db.execute(
            select(BusinessRuleConfigAuditLog).where(
                BusinessRuleConfigAuditLog.config_key == "admin.settings.general"
            )
        )
    ).scalars().all()
    assert rows
    assert audit_rows


@pytest.mark.contract
@pytest.mark.asyncio
async def test_admin_settings_rejects_non_admin_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    user = await _create_user(test_db)
    response = await async_client.get(
        "/api/v1/admin/settings/general",
        headers=_headers(user),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "[ROLE_REQUIRED]"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_ai_governance_explain_sales_session_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _create_admin(test_db)
    session_id = await _seed_explainable_session(test_db, scenario_type="sales")

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session"]["session_id"] == session_id
    assert payload["session"]["scenario_type"] == "sales"
    assert payload["model"] is None
    assert payload["prompt"] is None
    assert payload["rag"] is None
    assert payload["knowledge"] is None
    assert payload["scoring"] is None
    assert payload["evidence"]["completeness"] == {
        "conversation": True,
        "knowledge": True,
    }
    assert payload["evaluation"]["status"] == "succeeded"
    assert payload["report"]["lineage"]["ruleset_source"] == "sales_ruleset"
    assert payload["report"]["lineage"]["config_bundle_id"] is None
    assert payload["report"]["lineage"]["config_version_id"] is None
    assert payload["report"]["lineage"]["config_bundle_snapshot"] == {}


@pytest.mark.contract
@pytest.mark.asyncio
async def test_ai_governance_explain_presentation_session_contract(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _create_admin(test_db)
    session_id = await _seed_explainable_session(
        test_db,
        scenario_type="presentation",
    )

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session"]["scenario_type"] == "presentation"
    assert payload["model"] is None
    assert payload["prompt"] is None
    assert payload["rag"] is None
    assert payload["knowledge"] is None
    assert payload["scoring"] is None
    assert payload["report"]["payload"]["report_id"] == "presentation-report"
    assert payload["report"]["lineage"]["ruleset_source"] == "presentation_ruleset"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_ai_governance_explain_missing_lineage_returns_clear_error(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _create_admin(test_db)
    session_id = await _seed_session_without_lineage(test_db)

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 409
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "[AI_GOVERNANCE_EXPLAINABILITY_INCOMPLETE]"
    assert body["data"]["session_id"] == session_id
    assert "EvaluationRun" in body["data"]["missing"]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_ai_governance_explain_should_not_select_legacy_session_columns(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await _create_admin(test_db)
    session_id = await _seed_explainable_session(test_db, scenario_type="sales")
    original_execute = AsyncSession.execute

    async def fail_on_missing_dev_column_shape(
        self: AsyncSession,
        statement: Executable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        sql = str(statement)
        if "practice_sessions.report_status_updated_at" in sql:
            raise AssertionError(
                "explainability selected legacy-missing session column"
            )
        return await original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", fail_on_missing_dev_column_shape)

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200, response.json()
    assert response.json()["data"]["session"]["scenario_type"] == "sales"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_ai_governance_explain_should_not_select_legacy_snapshot_columns(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await _create_admin(test_db)
    session_id = await _seed_explainable_session(test_db, scenario_type="presentation")
    original_execute = AsyncSession.execute

    async def fail_on_missing_dev_column_shape(
        self: AsyncSession,
        statement: Executable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        sql = str(statement)
        missing_columns = (
            "training_report_snapshots.config_bundle_id",
            "training_report_snapshots.config_bundle_snapshot",
        )
        if any(column in sql for column in missing_columns):
            raise AssertionError(
                "explainability selected legacy-missing snapshot column"
            )
        return await original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", fail_on_missing_dev_column_shape)

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200, response.json()
    lineage = response.json()["data"]["report"]["lineage"]
    assert lineage["config_bundle_id"] is None
    assert lineage["config_bundle_snapshot"] == {}


@pytest.mark.contract
@pytest.mark.asyncio
async def test_ai_governance_explain_should_not_select_legacy_evaluation_columns(
    async_client: AsyncClient,
    test_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await _create_admin(test_db)
    session_id = await _seed_explainable_session(test_db, scenario_type="sales")
    original_execute = AsyncSession.execute

    async def fail_on_missing_dev_column_shape(
        self: AsyncSession,
        statement: Executable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        sql = str(statement)
        missing_columns = (
            "evaluation_runs.config_bundle_id",
            "evaluation_runs.config_version_id",
        )
        if any(column in sql for column in missing_columns):
            raise AssertionError(
                "explainability selected legacy-missing evaluation column"
            )
        return await original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", fail_on_missing_dev_column_shape)

    response = await async_client.get(
        f"/api/v1/admin/ai-governance/explain/{session_id}",
        headers=_headers(admin),
    )

    assert response.status_code == 200, response.json()
    evaluation = response.json()["data"]["evaluation"]
    assert evaluation["status"] == "succeeded"
    assert evaluation["config_bundle_id"] is None
    assert evaluation["config_version_id"] is None
