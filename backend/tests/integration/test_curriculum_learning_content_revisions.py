from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.auth.service import create_access_token
from common.db.models import Base, User
from common.db.session import get_db
from main import app
from sales_trainer.models import (
    SalesTrainerAssetActiveRevision,
    SalesTrainerAssetRevision,
)

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
async def admin_headers(db_session: AsyncSession) -> dict[str, str]:
    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"curriculum-revision-admin-{uuid.uuid4().hex[:8]}",
        name="Curriculum Revision Admin",
        email=f"curriculum-revision-admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(data={"sub": str(user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_should_update_published_learning_content_as_future_revision(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json={
            "title": "商务技巧课",
            "summary": "旧说明",
            "owner": "training-ops",
            "source": "manual",
        },
    )
    assert create_response.status_code == 200, create_response.json()
    content_id = create_response.json()["data"]["learning_content_id"]
    chapter_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第一节", "content": "见客户前准备", "order_index": 1},
    )
    assert chapter_response.status_code == 200, chapter_response.json()
    publish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200, publish_response.json()
    initial_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="published",
    )
    assert initial_revision.payload_json["summary"] == "旧说明"

    update_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
        json={"summary": "新说明，只给后续学习使用"},
    )

    assert update_response.status_code == 200, update_response.json()
    assert update_response.json()["data"]["summary"] == "旧说明"
    working_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="working",
    )
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert working_revision.change_class == "semantic"
    assert working_revision.payload_json["summary"] == "新说明，只给后续学习使用"
    read_before_publish = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert read_before_publish.json()["data"]["summary"] == "旧说明"

    republish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )

    assert republish_response.status_code == 200, republish_response.json()
    assert republish_response.json()["data"]["summary"] == "新说明，只给后续学习使用"
    active_revision = await _active_revision(db_session, logical_id=content_id)
    assert active_revision.active_revision_id == working_revision.revision_id


@pytest.mark.asyncio
async def test_should_update_published_learning_chapter_as_future_revision(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json={
            "title": "商务技巧课",
            "summary": "章节更新说明",
            "owner": "training-ops",
            "source": "manual",
        },
    )
    assert create_response.status_code == 200, create_response.json()
    content_id = create_response.json()["data"]["learning_content_id"]
    chapter_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第一节", "content": "旧章节内容", "order_index": 1},
    )
    assert chapter_response.status_code == 200, chapter_response.json()
    chapter_id = chapter_response.json()["data"]["chapter_id"]
    publish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200, publish_response.json()
    initial_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="published",
    )

    update_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/{chapter_id}",
        headers=admin_headers,
        json={"content": "新章节内容，只给后续学习使用"},
    )

    assert update_response.status_code == 200, update_response.json()
    assert update_response.json()["data"]["content"] == "旧章节内容"
    working_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="working",
    )
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert working_revision.payload_json["chapters"][0]["content"] == (
        "新章节内容，只给后续学习使用"
    )
    read_before_publish = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert read_before_publish.json()["data"]["chapters"][0]["content"] == "旧章节内容"

    republish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )

    assert republish_response.status_code == 200, republish_response.json()
    assert republish_response.json()["data"]["chapters"][0]["content"] == (
        "新章节内容，只给后续学习使用"
    )
    active_revision = await _active_revision(db_session, logical_id=content_id)
    assert active_revision.active_revision_id == working_revision.revision_id


@pytest.mark.asyncio
async def test_should_add_published_learning_chapter_as_future_revision(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json={
            "title": "商务技巧课",
            "summary": "新增章节说明",
            "owner": "training-ops",
            "source": "manual",
        },
    )
    assert create_response.status_code == 200, create_response.json()
    content_id = create_response.json()["data"]["learning_content_id"]
    chapter_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第一节", "content": "旧章节内容", "order_index": 1},
    )
    assert chapter_response.status_code == 200, chapter_response.json()
    publish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200, publish_response.json()
    initial_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="published",
    )

    add_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第二节", "content": "新增章节，只给后续学习使用"},
    )

    assert add_response.status_code == 200, add_response.json()
    read_before_publish = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert len(read_before_publish.json()["data"]["chapters"]) == 1
    working_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="working",
    )
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert [chapter["title"] for chapter in working_revision.payload_json["chapters"]] == [
        "第一节",
        "第二节",
    ]

    republish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )

    assert republish_response.status_code == 200, republish_response.json()
    assert len(republish_response.json()["data"]["chapters"]) == 2


@pytest.mark.asyncio
async def test_should_delete_published_learning_chapter_as_future_revision(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    content_id, first_id, second_id = await _published_content_with_two_chapters(
        async_client,
        admin_headers,
    )
    initial_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="published",
    )

    delete_response = await async_client.delete(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/{second_id}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 200, delete_response.json()
    read_before_publish = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert [chapter["chapter_id"] for chapter in read_before_publish.json()["data"]["chapters"]] == [
        first_id,
        second_id,
    ]
    working_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="working",
    )
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert [chapter["chapter_id"] for chapter in working_revision.payload_json["chapters"]] == [
        first_id
    ]

    republish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )

    assert republish_response.status_code == 200, republish_response.json()
    assert [chapter["chapter_id"] for chapter in republish_response.json()["data"]["chapters"]] == [
        first_id
    ]


@pytest.mark.asyncio
async def test_should_reorder_published_learning_chapters_as_future_revision(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    content_id, first_id, second_id = await _published_content_with_two_chapters(
        async_client,
        admin_headers,
    )
    initial_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="published",
    )

    reorder_response = await async_client.put(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters/reorder",
        headers=admin_headers,
        json={"chapter_ids": [second_id, first_id]},
    )

    assert reorder_response.status_code == 200, reorder_response.json()
    read_before_publish = await async_client.get(
        f"/api/v1/curriculum/learning-contents/{content_id}",
        headers=admin_headers,
    )
    assert [chapter["chapter_id"] for chapter in read_before_publish.json()["data"]["chapters"]] == [
        first_id,
        second_id,
    ]
    working_revision = await _latest_revision(
        db_session,
        logical_id=content_id,
        status="working",
    )
    assert working_revision.source_revision_id == initial_revision.revision_id
    assert [chapter["chapter_id"] for chapter in working_revision.payload_json["chapters"]] == [
        second_id,
        first_id,
    ]

    republish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )

    assert republish_response.status_code == 200, republish_response.json()
    assert [chapter["chapter_id"] for chapter in republish_response.json()["data"]["chapters"]] == [
        second_id,
        first_id,
    ]


async def _published_content_with_two_chapters(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> tuple[str, str, str]:
    create_response = await async_client.post(
        "/api/v1/curriculum/learning-contents",
        headers=admin_headers,
        json={
            "title": "商务技巧课",
            "summary": "多章节说明",
            "owner": "training-ops",
            "source": "manual",
        },
    )
    assert create_response.status_code == 200, create_response.json()
    content_id = create_response.json()["data"]["learning_content_id"]
    first_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第一节", "content": "第一节内容", "order_index": 1},
    )
    assert first_response.status_code == 200, first_response.json()
    second_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/chapters",
        headers=admin_headers,
        json={"title": "第二节", "content": "第二节内容", "order_index": 2},
    )
    assert second_response.status_code == 200, second_response.json()
    publish_response = await async_client.post(
        f"/api/v1/curriculum/learning-contents/{content_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200, publish_response.json()
    return (
        content_id,
        first_response.json()["data"]["chapter_id"],
        second_response.json()["data"]["chapter_id"],
    )


async def _latest_revision(
    db: AsyncSession,
    *,
    logical_id: str,
    status: str,
) -> SalesTrainerAssetRevision:
    result = await db.execute(
        select(SalesTrainerAssetRevision)
        .where(
            SalesTrainerAssetRevision.resource_type == "curriculum_learning_content",
            SalesTrainerAssetRevision.logical_id == logical_id,
            SalesTrainerAssetRevision.status == status,
        )
        .order_by(SalesTrainerAssetRevision.revision_no.desc())
    )
    return result.scalars().first()


async def _active_revision(
    db: AsyncSession,
    *,
    logical_id: str,
) -> SalesTrainerAssetActiveRevision:
    result = await db.execute(
        select(SalesTrainerAssetActiveRevision).where(
            SalesTrainerAssetActiveRevision.resource_type
            == "curriculum_learning_content",
            SalesTrainerAssetActiveRevision.logical_id == logical_id,
        )
    )
    return result.scalar_one()
