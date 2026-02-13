import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.auth.service import create_access_token
from common.db.models import Base, User
from common.db.session import get_db
from common.knowledge.models import KnowledgeBase
from main import app


class _StorageStub:
    async def save_document(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_data: bytes,
        file_type: str,
    ) -> str:
        return f"/tmp/{knowledge_base_id}/{document_id}.{file_type}"

    async def delete_document(
        self,
        knowledge_base_id: str,
        document_id: str,
        file_type: str,
    ) -> bool:
        return True


@pytest_asyncio.fixture(scope="function")
async def session_factory(tmp_path):
    db_file = tmp_path / "knowledge_upload_persistence.db"
    database_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_user_and_kb(factory: async_sessionmaker[AsyncSession]) -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    kb_id = str(uuid.uuid4())

    async with factory() as session:
        user = User(
            user_id=user_id,
            wechat_user_id=f"upload_test_{uuid.uuid4().hex[:8]}",
            name="Upload Test Admin",
            email=f"upload_test_{uuid.uuid4().hex[:8]}@example.com",
            role="admin",
            is_active=True,
        )
        kb = KnowledgeBase(
            id=kb_id,
            name="上传持久化测试知识库",
            description="用于验证上传后列表可见性",
            category="product",
            vector_collection=f"kb_{kb_id.replace('-', '_')}",
            embedding_model="text-embedding-v4",
            document_count=0,
            total_chunks=0,
            status="active",
        )
        session.add(user)
        session.add(kb)
        await session.commit()

    return user_id, kb_id


@pytest_asyncio.fixture(scope="function")
async def async_client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


async def test_upload_document_visible_in_followup_list_request(
    async_client,
    session_factory,
    monkeypatch,
):
    user_id, kb_id = await _seed_user_and_kb(session_factory)
    token = create_access_token(data={"sub": user_id})
    headers = {"Authorization": f"Bearer {token}"}

    async def _noop_process_document_background(**kwargs):
        return None

    monkeypatch.setattr(
        "common.knowledge.api.get_document_storage_service",
        lambda: _StorageStub(),
    )
    monkeypatch.setattr(
        "common.knowledge.api.process_document_background",
        _noop_process_document_background,
    )

    upload_response = await async_client.post(
        f"/api/v1/admin/knowledge/{kb_id}/documents",
        headers=headers,
        files={"file": ("产品介绍.txt", "石犀科技主营智能销售训练平台".encode("utf-8"), "text/plain")},
        data={"title": "产品介绍"},
    )

    assert upload_response.status_code == 202
    upload_data = upload_response.json()
    assert upload_data["success"] is True
    uploaded_doc_id = upload_data["data"]["id"]

    list_response = await async_client.get(
        f"/api/v1/admin/knowledge/{kb_id}/documents",
        headers=headers,
    )

    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["success"] is True
    assert list_data["data"]["total"] == 1
    assert any(
        doc["id"] == uploaded_doc_id for doc in list_data["data"]["documents"]
    )
