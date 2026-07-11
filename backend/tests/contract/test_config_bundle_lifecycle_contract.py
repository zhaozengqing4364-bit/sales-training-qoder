from __future__ import annotations

import uuid
from copy import deepcopy

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.db.models import ConfigBundleAuditLog, User
from curriculum_practice.models import SituationPack


async def _user(db: AsyncSession, *, role: str) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"config-bundle-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Config Bundle {role}",
        email=f"config-bundle-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _snapshot(version: str, suffix: str) -> dict:
    value = deepcopy(DEFAULT_ROLEPLAY_SITUATION_PACKS)
    value["version"] = version
    value["packs"] = [
        {**item, "label": f"{item['label']}{suffix}"}
        if item["code"] == "first_visit"
        else item
        for item in value["packs"]
    ]
    return value


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_bundle_http_lifecycle_preserves_contract_and_audit(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = await _user(test_db, role="admin")
    headers = _headers(admin)
    base = f"/api/v1/admin/config-bundles/{ROLEPLAY_SITUATION_PACKS_KEY}"
    first = _snapshot("gate4-config-v1", "-V1")
    second = _snapshot("gate4-config-v2", "-V2")

    listing = await async_client.get(
        "/api/v1/admin/config-bundles",
        headers=headers,
    )
    assert listing.status_code == 200
    assert ROLEPLAY_SITUATION_PACKS_KEY in {
        item["bundle_key"] for item in listing.json()["data"]["items"]
    }

    validation = await async_client.post(
        f"{base}/validate",
        headers=headers,
        json={"value": first, "reason": "validate first"},
    )
    assert validation.status_code == 200
    assert validation.json()["data"]["valid"] is True

    preview = await async_client.post(
        f"{base}/preview",
        headers=headers,
        json={"value": first, "reason": "preview first"},
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["audit"]["action"] == "preview"

    draft_v1 = await async_client.post(
        f"{base}/drafts",
        headers=headers,
        json={"value": first, "reason": "draft first"},
    )
    assert draft_v1.status_code == 200
    first_id = draft_v1.json()["data"]["version"]["source_config_id"]
    publish_v1 = await async_client.post(
        f"{base}/publish",
        headers=headers,
        json={"config_id": first_id, "reason": "publish first"},
    )
    assert publish_v1.status_code == 200
    assert publish_v1.json()["data"]["version"]["status"] == "published"

    draft_v2 = await async_client.post(
        f"{base}/drafts",
        headers=headers,
        json={"value": second, "reason": "draft second"},
    )
    second_id = draft_v2.json()["data"]["version"]["source_config_id"]
    publish_v2 = await async_client.post(
        f"{base}/publish",
        headers=headers,
        json={"config_id": second_id, "reason": "publish second"},
    )
    assert publish_v2.status_code == 200

    rollback = await async_client.post(
        f"{base}/rollback",
        headers=headers,
        json={"target_version": 1, "reason": "restore first"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["version"]["version"] == 1

    disabled = await async_client.post(
        f"{base}/disable",
        headers=headers,
        json={"reason": "pause roleplay configuration"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["version"]["status"] == "disabled"

    versions = await async_client.get(f"{base}/versions", headers=headers)
    assert versions.status_code == 200
    assert versions.json()["data"]["total"] == 2

    invalid = await async_client.post(
        f"{base}/validate",
        headers=headers,
        json={"value": {"version": "invalid", "packs": []}, "reason": "invalid"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"] == "[CONFIG_BUNDLE_SCHEMA_INVALID]"

    missing = await async_client.post(
        "/api/v1/admin/config-bundles/not-a-bundle/validate",
        headers=headers,
        json={"value": {}, "reason": "missing"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"] == "[CONFIG_BUNDLE_NOT_FOUND]"

    audits = (
        await test_db.execute(
            select(ConfigBundleAuditLog).where(
                ConfigBundleAuditLog.bundle_key == ROLEPLAY_SITUATION_PACKS_KEY
            )
        )
    ).scalars().all()
    assert {item.action for item in audits} >= {
        "create_draft",
        "validate",
        "preview",
        "publish",
        "rollback",
        "disable",
    }
    assert all(item.trace_id for item in audits)
    projected = (
        await test_db.execute(
            select(SituationPack).where(SituationPack.code == "first_visit")
        )
    ).scalar_one()
    assert projected.label == "首次拜访-V1"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_config_bundle_http_lifecycle_rejects_non_admin(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    user = await _user(test_db, role="user")
    response = await async_client.get(
        "/api/v1/admin/config-bundles",
        headers=_headers(user),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "[PERMISSION_REQUIRED]"
