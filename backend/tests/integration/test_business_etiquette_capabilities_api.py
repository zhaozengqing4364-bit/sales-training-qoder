from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.business_etiquette_capability_service import (
    default_business_etiquette_capability_snapshot,
)
from sales_trainer.services.business_etiquette_import_service import (
    BUSINESS_ETIQUETTE_RESOURCE_TYPE,
    DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-cap-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette Cap API {role}",
        email=f"business-etiquette-cap-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


async def _seed_training_pack_revision(
    test_db: AsyncSession,
    *,
    admin: User,
) -> None:
    payload = {
        "schema_version": 1,
        "training_pack_key": DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        "learning_content_id": "business-etiquette-cap-api-content",
        "book_title": "商务礼仪：新人的第一本职业素养手册",
        "original_chapter_count": 8,
        "original_chapters": [
            {"title": f"第 {index} 章", "order_index": index}
            for index in range(1, 9)
        ],
    }
    await SalesTrainerAssetRevisionService(test_db).save_working_revision(
        resource_type=BUSINESS_ETIQUETTE_RESOURCE_TYPE,
        logical_id=DEFAULT_BUSINESS_ETIQUETTE_TRAINING_PACK_KEY,
        payload=payload,
        actor=admin,
        change_class="semantic",
        reason="导入商务礼仪训练包资料",
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_should_return_default_business_etiquette_capability_seed(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack_revision(test_db, admin=admin)

    response = await async_client.get(
        "/api/v1/admin/newcomer-training/business-etiquette/capabilities",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["source"] == "default_seed"
    assert data["needs_save"] is True
    assert len(data["capabilities"]) == 8
    assert data["capabilities"][0]["capability_key"] == "respect_boundaries"
    assert len(data["chapter_bindings"]) == 8


@pytest.mark.asyncio
async def test_should_reject_capability_save_without_manager_permission(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()
    await _seed_training_pack_revision(test_db, admin=admin)
    seed = default_business_etiquette_capability_snapshot()

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/business-etiquette/capabilities",
        headers=_auth_headers(learner),
        json={
            "capabilities": seed["capabilities"],
            "chapter_bindings": seed["chapter_bindings"],
            "reason": "普通用户不能保存能力点",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[ROLE_REQUIRED]"


@pytest.mark.asyncio
async def test_should_save_and_publish_business_etiquette_capability(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()
    await _seed_training_pack_revision(test_db, admin=admin)
    seed = default_business_etiquette_capability_snapshot()

    save_response = await async_client.put(
        "/api/v1/admin/newcomer-training/business-etiquette/capabilities",
        headers=_auth_headers(admin),
        json={
            "capabilities": seed["capabilities"],
            "chapter_bindings": seed["chapter_bindings"],
            "reason": "保存商务礼仪能力点",
        },
    )

    assert save_response.status_code == 200, save_response.text
    saved = save_response.json()["data"]
    assert saved["working_revision_no"] == 2
    assert saved["capabilities"][0]["status"] == "draft"

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/capabilities/"
        "respect_boundaries/publish",
        headers=_auth_headers(admin),
        json={"reason": "发布尊重与分寸感能力点"},
    )

    assert publish_response.status_code == 200, publish_response.text
    published = publish_response.json()["data"]
    assert published["working_revision_no"] == 3
    first_capability = published["capabilities"][0]
    assert first_capability["capability_key"] == "respect_boundaries"
    assert first_capability["status"] == "published"
