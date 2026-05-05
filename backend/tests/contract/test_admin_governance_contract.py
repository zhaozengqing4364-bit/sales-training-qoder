from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import BusinessRuleConfig, BusinessRuleConfigAuditLog, User

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
