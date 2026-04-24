from __future__ import annotations

import uuid
from copy import deepcopy

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.business_rules.defaults import (
    DEFAULT_RECOMMENDATION_RULESET,
    NEXT_PRACTICE_RECOMMENDATION_KEY,
    get_business_rule_definition,
)
from common.db.models import BusinessRuleConfig, BusinessRuleConfigAuditLog, User


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_user(test_db: AsyncSession, *, role: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business_rule_{role}_{uuid.uuid4().hex[:8]}",
        name=f"Business Rule {role}",
        email=f"business-rule-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


def _recommendation_value(*, version: str, threshold: float) -> dict:
    value = deepcopy(DEFAULT_RECOMMENDATION_RULESET)
    value["version"] = version
    value["weak_score_threshold"] = threshold
    return value


@pytest.mark.asyncio
async def test_business_rule_mutation_rejects_non_admin_user(
    async_client: AsyncClient,
    test_db: AsyncSession,
):
    user = await _create_user(test_db, role="user")

    response = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/drafts",
        headers=_headers_for(str(user.user_id)),
        json={
            "value": _recommendation_value(version="blocked_v1", threshold=66),
            "reason": "user should not edit global rules",
        },
    )

    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_business_rule_preview_does_not_change_active_config(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _headers_for(str(test_user.user_id))

    draft_response = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/drafts",
        headers=headers,
        json={"value": _recommendation_value(version="active_v1", threshold=60)},
    )
    assert draft_response.status_code == 200
    draft_id = draft_response.json()["data"]["id"]
    publish_response = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/publish",
        headers=headers,
        json={"config_id": draft_id, "reason": "initial active"},
    )
    assert publish_response.status_code == 200

    preview_response = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/preview",
        headers=headers,
        json={
            "value": _recommendation_value(version="preview_v2", threshold=88),
            "reason": "impact check only",
        },
    )
    active_response = await async_client.get(
        f"/api/v1/admin/business-rules/active/{NEXT_PRACTICE_RECOMMENDATION_KEY}",
        headers=headers,
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()["data"]
    assert preview["summary"]["weak_score_threshold"] == 88.0
    assert active_response.status_code == 200
    active = active_response.json()["data"]
    assert active["value"]["version"] == "active_v1"
    assert active["value"]["weak_score_threshold"] == 60.0


@pytest.mark.asyncio
async def test_business_rule_publish_rollback_and_audit_log(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()
    headers = _headers_for(str(test_user.user_id))

    first_draft = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/drafts",
        headers=headers,
        json={"value": _recommendation_value(version="recommendation_v1", threshold=61)},
    )
    assert first_draft.status_code == 200
    first_id = first_draft.json()["data"]["id"]
    first_publish = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/publish",
        headers=headers,
        json={"config_id": first_id, "reason": "publish first"},
    )
    assert first_publish.status_code == 200

    second_draft = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/drafts",
        headers=headers,
        json={"value": _recommendation_value(version="recommendation_v2", threshold=75)},
    )
    assert second_draft.status_code == 200
    second_id = second_draft.json()["data"]["id"]
    second_publish = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/publish",
        headers=headers,
        json={"config_id": second_id, "reason": "publish second"},
    )
    assert second_publish.status_code == 200

    rollback = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/rollback",
        headers=headers,
        json={"target_version": 1, "reason": "rollback to stable"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["version"] == 1
    assert rollback.json()["data"]["status"] == "published"

    audit_rows = (
        await test_db.execute(
            select(BusinessRuleConfigAuditLog)
            .where(BusinessRuleConfigAuditLog.config_key == NEXT_PRACTICE_RECOMMENDATION_KEY)
            .order_by(BusinessRuleConfigAuditLog.created_at.asc())
        )
    ).scalars().all()
    actions = [row.action for row in audit_rows]

    assert actions == [
        "create_draft",
        "publish",
        "create_draft",
        "publish",
        "rollback",
    ]
    assert audit_rows[-1].before_version == 2
    assert audit_rows[-1].after_version == 1
    assert audit_rows[-1].reason == "rollback to stable"
    active_rows = (
        await test_db.execute(
            select(BusinessRuleConfig).where(
                BusinessRuleConfig.key == NEXT_PRACTICE_RECOMMENDATION_KEY,
                BusinessRuleConfig.status == "published",
            )
        )
    ).scalars().all()
    assert [row.version for row in active_rows] == [1]


@pytest.mark.asyncio
async def test_business_rule_publish_rejects_invalid_draft(
    async_client: AsyncClient,
    test_db: AsyncSession,
    test_user: User,
):
    test_user.role = "admin"
    await test_db.commit()
    definition = get_business_rule_definition(NEXT_PRACTICE_RECOMMENDATION_KEY)
    invalid = BusinessRuleConfig(
        domain=definition.domain,
        key=definition.key,
        schema_version=definition.schema_version,
        status="draft",
        version=1,
        value_json={"version": "", "dimensions": {}},
        default_value_json=deepcopy(definition.default_value),
        type=definition.type,
        range_or_allowlist_json=deepcopy(definition.range_or_allowlist),
        read_path=definition.read_path,
        admin_entry=definition.admin_entry,
        permission=definition.permission,
        audit_policy=definition.audit_policy,
        fallback_policy=definition.fallback_policy,
        rollback_policy=definition.rollback_policy,
        enabled=True,
        validation_errors_json=[],
        created_by=str(test_user.user_id),
        updated_by=str(test_user.user_id),
    )
    test_db.add(invalid)
    await test_db.commit()
    await test_db.refresh(invalid)

    response = await async_client.post(
        f"/api/v1/admin/business-rules/{NEXT_PRACTICE_RECOMMENDATION_KEY}/publish",
        headers=_headers_for(str(test_user.user_id)),
        json={"config_id": str(invalid.id), "reason": "should fail"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "[BUSINESS_RULE_SCHEMA_INVALID]"
