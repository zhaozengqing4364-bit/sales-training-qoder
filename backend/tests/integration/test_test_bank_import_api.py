from __future__ import annotations

import csv
import json
import uuid
from io import StringIO

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.auth.service import create_access_token
from common.db.models import Base, User
from common.db.session import get_db
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
        wechat_user_id=f"test-bank-import-admin-{uuid.uuid4().hex[:8]}",
        name="Test Bank Import Admin",
        email=f"test-bank-import-admin-{uuid.uuid4().hex[:8]}@example.com",
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


async def _create_category(async_client: AsyncClient, admin_headers: dict[str, str]) -> str:
    response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=admin_headers,
        json={"name": "需求诊断", "description": "题库分类", "order_index": 1},
    )
    assert response.status_code == 200, response.json()
    return str(response.json()["data"]["category_id"])


def _row(category_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "category_id": category_id,
        "title": "识别客户预算",
        "stem": "客户说预算有限时如何追问？",
        "reference_answer": "先确认预算范围，再澄清优先级。",
        "scoring_criteria": {"dimensions": ["clarity"]},
        "scoring_dimensions": ["clarity"],
        "tags": ["discovery", "budget"],
        "difficulty": "medium",
        "department": "sales-enablement",
    }
    payload.update(overrides)
    return payload


async def _upload(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    *,
    filename: str,
    content: bytes,
) -> dict[str, object]:
    response = await async_client.post(
        "/api/v1/curriculum/test-bank/imports",
        headers=admin_headers,
        files={"file": (filename, content, "text/plain")},
    )
    assert response.status_code == 200, response.json()
    return response.json()["data"]


@pytest.mark.asyncio
async def test_should_return_task_id_and_poll_success_stats_when_upload_valid_jsonl(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category_id = await _create_category(async_client, admin_headers)
    content = (json.dumps(_row(category_id), ensure_ascii=False) + "\n").encode()

    upload = await _upload(
        async_client, admin_headers, filename="questions.jsonl", content=content
    )
    poll_response = await async_client.get(
        f"/api/v1/curriculum/test-bank/imports/{upload['task_id']}",
        headers=admin_headers,
    )

    assert upload["task_id"]
    assert poll_response.status_code == 200, poll_response.json()
    result = poll_response.json()["data"]["result"]
    assert poll_response.json()["data"]["status"] == "completed"
    assert result["imported"] == 1
    assert result["failed"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_should_reject_oversized_file_at_10mb_limit(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    response = await async_client.post(
        "/api/v1/curriculum/test-bank/imports",
        headers=admin_headers,
        files={"file": ("questions.jsonl", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["error"] == "[TEST_BANK_IMPORT_FILE_TOO_LARGE]"


@pytest.mark.asyncio
async def test_should_reject_non_utf8_encoding(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    response = await async_client.post(
        "/api/v1/curriculum/test-bank/imports",
        headers=admin_headers,
        files={"file": ("questions.jsonl", b"\xff\xfe\x00", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "[TEST_BANK_IMPORT_ENCODING_INVALID]"


@pytest.mark.asyncio
async def test_should_persist_csv_escaping_for_title_stem_and_reference_answer(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category_id = await _create_category(async_client, admin_headers)
    stream = StringIO()
    csv.writer(stream).writerows(
        [
            [
                "category_id",
                "title",
                "stem",
                "reference_answer",
                "scoring_criteria",
                "scoring_dimensions",
                "tags",
                "difficulty",
                "department",
            ],
            [
                category_id,
                '报价异议, "高级"处理',
                '客户说"太贵了, 再便宜点"时怎么办？',
                '先确认预算, 再解释"价值"。',
                json.dumps({"dimensions": ["clarity"]}, ensure_ascii=False),
                '["clarity"]',
                '["objection","price"]',
                "hard",
                "sales-enablement",
            ],
        ]
    )

    await _upload(
        async_client,
        admin_headers,
        filename="questions.csv",
        content=stream.getvalue().encode(),
    )
    list_response = await async_client.get(
        "/api/v1/curriculum/test-bank/questions",
        headers=admin_headers,
        params={"category_id": category_id},
    )

    assert list_response.status_code == 200, list_response.json()
    item = list_response.json()["data"]["items"][0]
    assert item["title"] == '报价异议, "高级"处理'
    assert item["stem"] == '客户说"太贵了, 再便宜点"时怎么办？'
    assert item["reference_answer"] == '先确认预算, 再解释"价值"。'


@pytest.mark.asyncio
async def test_should_report_jsonl_format_error_as_row_error(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    upload = await _upload(
        async_client,
        admin_headers,
        filename="questions.jsonl",
        content=b'{"title": "broken"\n',
    )
    poll_response = await async_client.get(
        f"/api/v1/curriculum/test-bank/imports/{upload['task_id']}",
        headers=admin_headers,
    )

    data = poll_response.json()["data"]
    assert data["status"] == "completed"
    assert data["result"]["imported"] == 0
    assert data["result"]["failed"] == 1
    assert data["result"]["errors"][0]["row"] == 1
    assert data["result"]["errors"][0]["field"] == "file"
