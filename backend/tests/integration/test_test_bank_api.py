from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.auth.service import create_access_token
from common.db.models import Base, User
from common.db.session import get_db
from curriculum_practice.models import QuestionCategory, QuestionItem
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
        wechat_user_id=f"test-bank-admin-{uuid.uuid4().hex[:8]}",
        name="Test Bank Admin",
        email=f"test-bank-admin-{uuid.uuid4().hex[:8]}@example.com",
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


@pytest.mark.asyncio
async def test_should_persist_question_category_and_question_item_model_fields(
    db_session: AsyncSession,
) -> None:
    category = QuestionCategory(
        name="需求诊断",
        description="需求澄清能力题库",
        order_index=1,
    )
    db_session.add(category)
    await db_session.flush()

    question = QuestionItem(
        category_id=category.category_id,
        title="识别客户预算",
        stem="客户说预算有限时如何追问？",
        reference_answer="先确认预算范围，再澄清优先级。",
        scoring_criteria={"dimensions": ["clarity"]},
        scoring_dimensions=["clarity"],
        tags=["discovery", "budget"],
        difficulty="medium",
        department="sales-enablement",
    )
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)

    assert question.status == "draft"
    assert question.version == 1
    assert question.content_hash is None
    assert question.scoring_dimensions == ["clarity"]
    assert question.tags == ["discovery", "budget"]
    assert question.department == "sales-enablement"


def _category_payload(name: str = "需求诊断") -> dict[str, object]:
    return {"name": name, "description": "需求澄清能力题库", "order_index": 1}


async def _create_category(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    name: str = "需求诊断",
) -> str:
    response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=admin_headers,
        json=_category_payload(name),
    )
    assert response.status_code == 200, response.json()
    return str(response.json()["data"]["category_id"])


def _question_payload(category_id: str, title: str = "识别客户预算") -> dict[str, object]:
    return {
        "category_id": category_id,
        "title": title,
        "stem": "客户说预算有限时如何追问？",
        "reference_answer": "先确认预算范围，再澄清优先级。",
        "scoring_criteria": {"dimensions": ["clarity"]},
        "scoring_dimensions": ["clarity"],
        "tags": ["discovery", "budget"],
        "difficulty": "medium",
        "department": "sales-enablement",
    }


@pytest.mark.asyncio
async def test_should_create_update_list_and_delete_category_tree_with_protection(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    root_response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=admin_headers,
        json=_category_payload(),
    )
    assert root_response.status_code == 200, root_response.json()
    root = root_response.json()["data"]

    child_response = await async_client.post(
        "/api/v1/curriculum/test-bank/categories",
        headers=admin_headers,
        json=_category_payload("预算澄清") | {"parent_id": root["category_id"]},
    )
    assert child_response.status_code == 200, child_response.json()

    update_response = await async_client.put(
        f"/api/v1/curriculum/test-bank/categories/{root['category_id']}",
        headers=admin_headers,
        json={"name": "需求诊断更新", "order_index": 2},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["name"] == "需求诊断更新"

    list_response = await async_client.get(
        "/api/v1/curriculum/test-bank/categories",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 2

    protected_response = await async_client.delete(
        f"/api/v1/curriculum/test-bank/categories/{root['category_id']}",
        headers=admin_headers,
    )
    assert protected_response.status_code == 409
    assert protected_response.json()["error"] == "[QUESTION_CATEGORY_HAS_CHILDREN]"

    child_id = child_response.json()["data"]["category_id"]
    delete_child_response = await async_client.delete(
        f"/api/v1/curriculum/test-bank/categories/{child_id}",
        headers=admin_headers,
    )
    assert delete_child_response.status_code == 200
    assert delete_child_response.json()["data"] == {"deleted": True}


@pytest.mark.asyncio
async def test_should_create_edit_filter_publish_archive_question_and_keep_snapshot_immutable(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category_id = await _create_category(async_client, admin_headers)
    other_category_id = await _create_category(async_client, admin_headers, "异议处理")
    create_response = await async_client.post(
        "/api/v1/curriculum/test-bank/questions",
        headers=admin_headers,
        json=_question_payload(category_id),
    )
    assert create_response.status_code == 200, create_response.json()
    question = create_response.json()["data"]
    assert question["status"] == "draft"
    assert question["version"] == 1
    assert question["content_hash"] is None

    update_response = await async_client.put(
        f"/api/v1/curriculum/test-bank/questions/{question['question_id']}",
        headers=admin_headers,
        json={"difficulty": "hard", "tags": ["discovery", "priority"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["difficulty"] == "hard"

    await async_client.post(
        "/api/v1/curriculum/test-bank/questions",
        headers=admin_headers,
        json=_question_payload(other_category_id, "处理竞品异议")
        | {"difficulty": "easy", "tags": ["objection"]},
    )

    filter_response = await async_client.get(
        "/api/v1/curriculum/test-bank/questions",
        headers=admin_headers,
        params={"category_id": category_id, "difficulty": "hard", "tag": "priority"},
    )
    assert filter_response.status_code == 200
    filtered = filter_response.json()["data"]
    assert filtered["total"] == 1
    assert filtered["items"][0]["question_id"] == question["question_id"]

    protected_category_response = await async_client.delete(
        f"/api/v1/curriculum/test-bank/categories/{category_id}",
        headers=admin_headers,
    )
    assert protected_category_response.status_code == 409
    assert protected_category_response.json()["error"] == "[QUESTION_CATEGORY_HAS_QUESTIONS]"

    publish_response = await async_client.post(
        f"/api/v1/curriculum/test-bank/questions/{question['question_id']}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200, publish_response.json()
    published = publish_response.json()["data"]
    assert published["status"] == "published"
    assert published["version"] == 1
    assert published["content_hash"].startswith("sha256:")

    immutable_response = await async_client.put(
        f"/api/v1/curriculum/test-bank/questions/{question['question_id']}",
        headers=admin_headers,
        json={"title": "不应修改已发布题目"},
    )
    assert immutable_response.status_code == 409
    assert immutable_response.json()["error"] == "[QUESTION_ITEM_NOT_EDITABLE]"

    archive_response = await async_client.post(
        f"/api/v1/curriculum/test-bank/questions/{question['question_id']}/archive",
        headers=admin_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_should_publish_question_when_dimensions_are_submitted_separately(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category_id = await _create_category(async_client, admin_headers)
    create_response = await async_client.post(
        "/api/v1/curriculum/test-bank/questions",
        headers=admin_headers,
        json=_question_payload(category_id)
        | {
            "scoring_criteria": {"rubric": "按澄清度评分"},
            "scoring_dimensions": ["clarity"],
        },
    )
    assert create_response.status_code == 200, create_response.json()
    question = create_response.json()["data"]
    assert question["scoring_criteria"]["dimensions"] == ["clarity"]

    publish_response = await async_client.post(
        f"/api/v1/curriculum/test-bank/questions/{question['question_id']}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 200, publish_response.json()
    assert publish_response.json()["data"]["status"] == "published"


@pytest.mark.asyncio
async def test_should_reject_question_publish_when_required_gates_fail(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category_id = await _create_category(async_client, admin_headers)
    create_response = await async_client.post(
        "/api/v1/curriculum/test-bank/questions",
        headers=admin_headers,
        json=_question_payload(category_id)
        | {
            "reference_answer": "   ",
            "scoring_criteria": {"dimensions": []},
            "scoring_dimensions": [],
            "safety_flagged": True,
        },
    )
    assert create_response.status_code == 200, create_response.json()
    question_id = create_response.json()["data"]["question_id"]

    publish_response = await async_client.post(
        f"/api/v1/curriculum/test-bank/questions/{question_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 400
    assert _reason_codes(publish_response) == [
        "missing_reference_answer",
        "invalid_scoring_criteria",
        "invalid_scoring_dimensions",
        "security_flagged_question",
    ]


def _reason_codes(response) -> list[str]:
    return [
        item["reason_code"] for item in response.json()["details"]["gate_results"]
    ]
