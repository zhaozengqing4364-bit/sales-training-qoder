from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User
from curriculum_practice.models import LearningChapter, LearningContent
from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerUnit
from sales_trainer.services.operation_log_service import OperationLogService
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
)


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"newcomer-article-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Newcomer Article API {role}",
        email=f"newcomer-article-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _content(content_id: str, *, status: str) -> LearningContent:
    return LearningContent(
        learning_content_id=content_id,
        title="见客户前商务礼仪",
        summary="阅读文章后再进入商务技巧考卷。",
        owner="新人训练路径",
        source="admin_learning_content",
        status=status,
    )


@pytest.mark.asyncio
async def test_should_fetch_newcomer_article_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    content = _content("newcomer-article-api-content", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-chapter",
        learning_content_id=content.learning_content_id,
        title="拜访前准备",
        content="![商务礼仪图](https://example.com/etiquette.png)\n\n确认客户背景。",
        order_index=1,
    )
    test_db.add_all([learner, content, chapter])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": content.learning_content_id},
    )

    assert response.status_code == 200
    article = response.json()["data"]
    assert article["module_key"] == "business_skills"
    assert article["title"] == "见客户前商务礼仪"
    assert article["chapters"][0]["content"].startswith("![商务礼仪图]")


@pytest.mark.asyncio
async def test_should_fetch_newcomer_article_from_module_binding_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    content = _content("newcomer-article-api-bound-content", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-bound-chapter",
        learning_content_id=content.learning_content_id,
        title="客户资料",
        content="![客户资料](https://example.com/client.png)\n\n提前确认客户资料。",
        order_index=1,
    )
    module_unit = SalesTrainerUnit(
        unit_id="newcomer-article-api-module-binding",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 2,
                "learning_content_id": content.learning_content_id,
            }
        },
    )
    test_db.add_all([learner, content, chapter, module_unit])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )

    assert response.status_code == 200
    article = response.json()["data"]
    assert article["learning_content_id"] == content.learning_content_id
    assert article["chapters"][0]["content"].startswith("![客户资料]")


@pytest.mark.asyncio
async def test_should_bind_newcomer_article_content_via_admin_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    content = _content("newcomer-article-admin-bound", status="published")
    chapter = LearningChapter(
        chapter_id="newcomer-article-api-admin-bound-chapter",
        learning_content_id=content.learning_content_id,
        title="拜访礼仪",
        content="![礼仪图片](https://example.com/etiquette.png)\n\n确认拜访礼仪。",
        order_index=1,
    )
    module_unit = SalesTrainerUnit(
        unit_id="article-admin-module-binding",
        name="商务技巧",
        unit_type="quiz",
        status="published",
        config={
            "path": {
                "enabled": True,
                "path_key": "newcomer_training_path_v1",
                "module_key": "business_skills",
                "module_type": "article_exam",
                "order_index": 2,
            }
        },
    )
    test_db.add_all([admin, learner, content, chapter, module_unit])
    await test_db.commit()

    bind_response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/article-binding",
        headers=_auth_headers(admin),
        json={
            "learning_content_id": content.learning_content_id,
            "reason": "配置商务技巧学习文章",
        },
    )
    assert bind_response.status_code == 200, bind_response.text
    bind_data = bind_response.json()["data"]
    assert bind_data["learning_content_id"] == content.learning_content_id
    assert bind_data["path_key"] == "newcomer_training_path_v1"
    assert bind_data["active_revision_id"] is None
    assert bind_data["active_revision_no"] is None
    assert bind_data["working_revision_id"]
    assert bind_data["working_revision_no"] == 1
    assert bind_data["has_unpublished_revision"] is True
    assert bind_data["impact_scope"] == "future_learners_only"
    bind_trace_id = bind_response.json()["trace_id"]

    await test_db.refresh(module_unit)
    assert "learning_content_id" not in module_unit.config["path"]

    learner_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )
    assert learner_response.status_code == 404
    assert learner_response.json()["error"] == "[LEARNING_CONTENT_NOT_PUBLISHED]"

    path_config_response = await async_client.get(
        "/api/v1/admin/newcomer-training/path-config",
        headers=_auth_headers(admin),
    )
    assert path_config_response.status_code == 200
    path_config = path_config_response.json()["data"]
    assert path_config["has_unpublished_revision"] is True
    revisions = await test_db.execute(
        select(SalesTrainerAssetRevision).where(
            SalesTrainerAssetRevision.resource_type == NEWCOMER_PATH_RESOURCE_TYPE,
            SalesTrainerAssetRevision.logical_id == NEWCOMER_PATH_LOGICAL_ID,
            SalesTrainerAssetRevision.status == "working",
        )
    )
    working_revision = revisions.scalar_one()
    assert bind_data["working_revision_id"] == working_revision.revision_id
    assert (
        working_revision.payload_json["modules"][0]["learning_content_id"]
        == content.learning_content_id
    )

    publish_response = await async_client.post(
        "/api/v1/admin/newcomer-training/path-config/publish",
        headers=_auth_headers(admin),
        json={"reason": "商务技巧学习文章绑定生效"},
    )
    assert publish_response.status_code == 200

    learner_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
    )
    assert learner_response.status_code == 200
    assert learner_response.json()["data"]["title"] == "见客户前商务礼仪"

    logs, total = await OperationLogService(test_db).list_logs(
        target_type="newcomer_path_config",
    )
    article_logs = [
        log
        for log in logs
        if log.action == "newcomer_path_config.article_binding_saved"
    ]
    assert total >= 2
    assert len(article_logs) == 1
    assert article_logs[0].request_id == bind_trace_id
    assert article_logs[0].metadata_json["trace_id"] == bind_trace_id
    assert article_logs[0].metadata_json["impact_scope"] == "future_learners_only"
    assert (
        article_logs[0].metadata_json["learning_content_id"]
        == content.learning_content_id
    )


@pytest.mark.asyncio
async def test_should_reject_draft_newcomer_article_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    content = _content("newcomer-article-api-draft", status="draft")
    test_db.add_all([learner, content])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": content.learning_content_id},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "[LEARNING_CONTENT_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_should_reject_legacy_path_key_for_article_binding_write(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    test_db.add(admin)
    await test_db.commit()

    response = await async_client.put(
        "/api/v1/admin/newcomer-training/modules/business_skills/article-binding",
        headers=_auth_headers(admin),
        json={
            "learning_content_id": "legacy-path-write-content",
            "path_key": "new_seller_modules_v1",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[NEWCOMER_PATH_CONFIG_ALIAS_READ_ONLY]"


@pytest.mark.asyncio
async def test_should_reject_empty_chapter_newcomer_article_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    learner = _user("user")
    content = _content("newcomer-article-api-empty-chapters", status="published")
    test_db.add_all([learner, content])
    await test_db.commit()

    response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": content.learning_content_id},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "[LEARNING_CONTENT_CHAPTERS_MISSING]"
