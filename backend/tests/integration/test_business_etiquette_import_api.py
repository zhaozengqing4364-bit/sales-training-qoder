from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _user(role: str) -> User:
    return User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"business-etiquette-api-{role}-{uuid.uuid4().hex[:8]}",
        name=f"Business Etiquette API {role}",
        email=f"business-etiquette-api-{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
    )


def _markdown() -> bytes:
    chapter_names = [
        "第一节：礼仪的底层逻辑",
        "第二节：职业形象塑造",
        "第三节：见面与社交礼仪",
        "第四节：商务沟通礼仪",
        "第五节：接待与拜访礼仪",
        "第六节：会议与活动礼仪",
        "第七节：商务餐饮礼仪",
        "第八节：礼仪的内化",
    ]
    lines = [
        "# 商务礼仪：新人的第一本职业素养手册",
        "",
        "## 全书总目录",
        "",
        "按 8 个原始章节组织。",
        "",
    ]
    for index, chapter_name in enumerate(chapter_names, start=1):
        lines.extend(
            [
                f"# {chapter_name}",
                "",
                "## 引子",
                "",
                f"第 {index} 章正文。",
                "",
                "### 核心知识点",
                "",
                f"第 {index} 章知识点。",
                "",
            ]
        )
    return "\n".join(lines).encode("utf-8")


@pytest.mark.asyncio
async def test_admin_should_import_business_etiquette_markdown_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    admin = _user("admin")
    learner = _user("user")
    test_db.add_all([admin, learner])
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/imports",
        headers=_auth_headers(admin),
        data={"reason": "导入商务礼仪训练包 v1"},
        files={
            "file": (
                "business-etiquette.md",
                _markdown(),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["data"]
    assert payload["trace_id"]
    assert data["training_pack_key"] == "business_etiquette_v1"
    assert data["learning_content_status"] == "draft"
    assert data["working_revision_no"] == 1
    assert data["active_revision_id"] is None
    assert data["original_chapter_count"] == 8
    assert data["micro_chapter_count"] == 8
    assert data["knowledge_point_count"] == 8
    assert (
        data["chapters"][0]["micro_chapters"][0]["knowledge_points"][0]["title"]
        == "核心知识点"
    )

    learner_response = await async_client.get(
        "/api/v1/newcomer-training/modules/business_skills/article",
        headers=_auth_headers(learner),
        params={"learning_content_id": data["learning_content_id"]},
    )
    assert learner_response.status_code == 404
    assert learner_response.json()["error"] == "[LEARNING_CONTENT_NOT_PUBLISHED]"


@pytest.mark.asyncio
async def test_user_should_not_import_business_etiquette_markdown_via_api(
    async_client: AsyncClient,
    test_db: AsyncSession,
) -> None:
    user = _user("user")
    test_db.add(user)
    await test_db.commit()

    response = await async_client.post(
        "/api/v1/admin/newcomer-training/business-etiquette/imports",
        headers=_auth_headers(user),
        files={
            "file": (
                "business-etiquette.md",
                _markdown(),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == "[ROLE_REQUIRED]"
