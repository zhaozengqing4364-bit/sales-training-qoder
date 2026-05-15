from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.auth.service import create_access_token
from common.db.models import Base, User
from common.db.session import get_db
from curriculum_practice.schemas import LearningChapterCreate, LearningContentCreate
from curriculum_practice.services.learning_contents import LearningContentService
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"learning-content-admin-{uuid.uuid4().hex[:8]}",
        name="Learning Content Admin",
        email=f"learning-content-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _content_payload() -> dict[str, object]:
    return {
        "title": "售前试点七章讲义",
        "summary": "面向售前顾问的基础训练讲义",
        "owner": "training-ops",
        "source": "manual-import-2026-05",
    }


@pytest.mark.asyncio
async def test_should_create_list_read_and_update_learning_content_draft(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload(),
    )

    assert create_response.status_code == 200, create_response.json()
    created = create_response.json()["data"]
    assert created["title"] == "售前试点七章讲义"
    assert created["status"] == "draft"
    assert created["chapters"] == []
    assert created["owner"] == "training-ops"
    assert created["source"] == "manual-import-2026-05"

    list_response = await async_client.get(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1

    content_id = created["learning_content_id"]
    read_response = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert read_response.status_code == 200
    assert read_response.json()["data"]["learning_content_id"] == content_id

    update_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
        json={"summary": "更新后的讲义说明", "safety_flagged": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["summary"] == "更新后的讲义说明"
    assert updated["safety_flagged"] is True


@pytest.mark.asyncio
async def test_should_add_update_delete_and_reorder_learning_chapters(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload(),
    )
    content_id = create_response.json()["data"]["learning_content_id"]

    first_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第一章", "content": "建立信任", "order_index": 1},
    )
    second_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第二章", "content": "需求澄清", "order_index": 2},
    )
    assert first_response.status_code == 200, first_response.json()
    assert second_response.status_code == 200, second_response.json()
    first = first_response.json()["data"]
    second = second_response.json()["data"]

    update_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/{first['chapter_id']}",
        headers=admin_headers,
        json={"title": "第一章：建立信任"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["title"] == "第一章：建立信任"

    reorder_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/reorder",
        headers=admin_headers,
        json={"chapter_ids": [second["chapter_id"], first["chapter_id"]]},
    )
    assert reorder_response.status_code == 200, reorder_response.json()
    reordered = reorder_response.json()["data"]
    assert [item["chapter_id"] for item in reordered] == [
        second["chapter_id"],
        first["chapter_id"],
    ]
    assert [item["order_index"] for item in reordered] == [1, 2]

    delete_response = await async_client.delete(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/{first['chapter_id']}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"deleted": True}

    read_response = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert read_response.status_code == 200
    chapters = read_response.json()["data"]["chapters"]
    assert [chapter["chapter_id"] for chapter in chapters] == [second["chapter_id"]]


@pytest.mark.asyncio
async def test_should_enforce_learning_content_publish_gates(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    no_chapters_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload(),
    )
    no_chapters_id = no_chapters_response.json()["data"]["learning_content_id"]

    publish_empty_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{no_chapters_id}/publish",
        headers=admin_headers,
    )
    assert publish_empty_response.status_code == 400
    assert _reason_codes(publish_empty_response) == ["no_chapters"]

    blank_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload() | {"title": "空内容讲义"},
    )
    blank_id = blank_response.json()["data"]["learning_content_id"]
    await async_client.post(
        f"/api/v1/curriculum/learning-contents/{blank_id}/chapters",
        headers=admin_headers,
        json={"title": "第一章", "content": "   ", "order_index": 1},
    )
    publish_blank_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{blank_id}/publish",
        headers=admin_headers,
    )
    assert publish_blank_response.status_code == 400
    assert _reason_codes(publish_blank_response) == ["empty_chapter_content"]

    order_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload() | {"title": "顺序缺口讲义"},
    )
    order_id = order_response.json()["data"]["learning_content_id"]
    await async_client.post(
        f"/api/v1/curriculum/learning-contents/{order_id}/chapters",
        headers=admin_headers,
        json={"title": "第一章", "content": "建立信任", "order_index": 1},
    )
    await async_client.post(
        f"/api/v1/curriculum/learning-contents/{order_id}/chapters",
        headers=admin_headers,
        json={"title": "第三章", "content": "推进成交", "order_index": 3},
    )
    publish_order_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{order_id}/publish",
        headers=admin_headers,
    )
    assert publish_order_response.status_code == 400
    assert _reason_codes(publish_order_response) == ["non_contiguous_chapter_order"]

    flagged_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload() | {"title": "安全标记讲义", "safety_flagged": True},
    )
    flagged_id = flagged_response.json()["data"]["learning_content_id"]
    await async_client.post(
        f"/api/v1/curriculum/learning-contents/{flagged_id}/chapters",
        headers=admin_headers,
        json={"title": "第一章", "content": "合规内容", "order_index": 1},
    )
    publish_flagged_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{flagged_id}/publish",
        headers=admin_headers,
    )
    assert publish_flagged_response.status_code == 400
    assert _reason_codes(publish_flagged_response) == ["security_flagged_content"]

    valid_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload() | {"title": "可发布讲义"},
    )
    valid_id = valid_response.json()["data"]["learning_content_id"]
    await async_client.post(
        f"/api/v1/curriculum/learning-contents/{valid_id}/chapters",
        headers=admin_headers,
        json={"title": "第一章", "content": "建立信任", "order_index": 1},
    )
    publish_valid_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{valid_id}/publish",
        headers=admin_headers,
    )
    assert publish_valid_response.status_code == 200, publish_valid_response.json()
    published = publish_valid_response.json()["data"]
    assert published["status"] == "published"
    assert published["content_hash"].startswith("sha256:")


def _reason_codes(response) -> list[str]:
    return [
        item["reason_code"]
        for item in response.json()["details"]["gate_results"]
    ]


@pytest.mark.asyncio
async def test_should_protect_archived_learning_content_from_mutation_and_publish(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json=_content_payload() | {"title": "归档保护讲义"},
    )
    content_id = create_response.json()["data"]["learning_content_id"]
    chapter_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第一章", "content": "建立信任", "order_index": 1},
    )
    chapter_id = chapter_response.json()["data"]["chapter_id"]

    archive_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/archive",
        headers=admin_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["status"] == "archived"

    update_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
        json={"summary": "不应写入"},
    )
    assert update_response.status_code == 409
    assert update_response.json()["error"] == "[LEARNING_CONTENT_NOT_EDITABLE]"

    add_chapter_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第二章", "content": "需求澄清", "order_index": 2},
    )
    assert add_chapter_response.status_code == 409

    update_chapter_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/{chapter_id}",
        headers=admin_headers,
        json={"title": "不应更新"},
    )
    assert update_chapter_response.status_code == 409

    publish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 409
    assert publish_response.json()["error"] == "[LEARNING_CONTENT_NOT_EDITABLE]"


@pytest.mark.asyncio
async def test_should_return_result_failure_when_service_reorder_payload_is_invalid(
    db_session: AsyncSession,
) -> None:
    service = LearningContentService(db_session)
    create_result = await service.create_content(
        LearningContentCreate.model_validate(_content_payload()), actor_id="admin-1"
    )
    assert create_result.is_success is True
    content = create_result.value
    assert content is not None
    first_result = await service.add_chapter(
        content,
        LearningChapterCreate(
            title="第一章",
            content="建立信任",
            order_index=1,
        ),
        actor_id="admin-1",
    )
    second_result = await service.add_chapter(
        content,
        LearningChapterCreate(
            title="第二章",
            content="需求澄清",
            order_index=2,
        ),
        actor_id="admin-1",
    )
    assert first_result.is_success is True
    assert second_result.is_success is True
    first = first_result.value
    assert first is not None

    reorder_result = await service.reorder_chapters(
        content,
        [first.chapter_id],
        actor_id="admin-1",
    )

    assert reorder_result.is_success is False
    assert reorder_result.fallback == "[LEARNING_CHAPTER_REORDER_INVALID]"
