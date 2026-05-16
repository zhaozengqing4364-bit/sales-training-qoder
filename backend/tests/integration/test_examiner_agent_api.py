from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.auth.service import create_access_token
from common.db.models import Base, PracticeSession, ScoringRuleset, User
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
        wechat_user_id="examiner-admin",
        name="Examiner Admin",
        email="examiner-admin@example.com",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(admin_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


def _examiner_payload() -> dict[str, object]:
    return {
        "name": "新手考试官",
        "description": "面向新手销售的考试官配置",
        "question_source_ids": ["question-1"],
        "learner_level_strategy": {
            "default_level": "beginner",
            "allowed_levels": ["conservative", "beginner"],
        },
        "scoring_policy_id": "ruleset-1",
        "timeout_config": {"max_seconds": 600},
        "safety_config": {"reject_safety_flagged": True},
        "prompt_config": {"system_prompt": "严格但友好地提问。"},
        "simulation_config": {"sample_answer": "我会先确认客户预算。"},
    }


async def _seed_examiner_publish_refs(
    db: AsyncSession,
    *,
    question_status: str = "published",
    safety_flagged: bool = False,
    ruleset_status: str = "published",
    ruleset_active: bool = True,
) -> None:
    category = QuestionCategory(
        category_id="category-1",
        name="考试题库",
        order_index=1,
    )
    question = QuestionItem(
        question_id="question-1",
        category_id="category-1",
        title="预算确认",
        stem="你会如何确认客户预算？",
        reference_answer="先确认预算区间，再确认决策流程。",
        scoring_criteria={"dimensions": [{"id": "discovery", "max": 100}]},
        scoring_dimensions=["discovery"],
        status=question_status,
        safety_flagged=safety_flagged,
        content_hash="sha256:question-1",
    )
    ruleset = ScoringRuleset(
        ruleset_id="ruleset-1",
        scenario_type="sales",
        version="sales-v1",
        display_name="Sales v1",
        status=ruleset_status,
        definition_json={"scenario_type": "sales"},
        is_active=ruleset_active,
    )
    db.add_all([category, question, ruleset])
    await db.commit()


@pytest.mark.asyncio
async def test_should_create_list_get_update_and_archive_examiner_agent_draft(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/examiner-agents",
        headers=admin_headers,
        json=_examiner_payload(),
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["name"] == "新手考试官"
    assert created["status"] == "draft"
    assert created["question_source_ids"] == ["question-1"]

    list_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/examiner-agents",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1

    read_response = await async_client.get(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{created['examiner_agent_id']}",
        headers=admin_headers,
    )
    assert read_response.status_code == 200
    assert read_response.json()["data"]["examiner_agent_id"] == created[
        "examiner_agent_id"
    ]

    update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{created['examiner_agent_id']}",
        headers=admin_headers,
        json={"description": "更新后的草稿说明"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["description"] == "更新后的草稿说明"

    archive_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{created['examiner_agent_id']}/archive",
        headers=admin_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_should_reject_examiner_agent_publish_when_gate_fails(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/examiner-agents",
        headers=admin_headers,
        json=_examiner_payload() | {"question_source_ids": []},
    )
    examiner_agent_id = create_response.json()["data"]["examiner_agent_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 400
    payload = publish_response.json()
    assert payload["error"] == "[EXAMINER_AGENT_PUBLISH_GATE_FAILED]"
    assert [item["reason_code"] for item in payload["details"]["gate_results"]] == [
        "[EXAMINER_QUESTION_SOURCE_EMPTY]",
        "[EXAMINER_SCORING_POLICY_INVALID]",
    ]


@pytest.mark.asyncio
async def test_should_reject_examiner_agent_publish_for_unpublished_or_flagged_refs(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_examiner_publish_refs(db_session, question_status="draft")
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/examiner-agents",
        headers=admin_headers,
        json=_examiner_payload(),
    )
    examiner_agent_id = create_response.json()["data"]["examiner_agent_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 400
    assert [
        item["reason_code"]
        for item in publish_response.json()["details"]["gate_results"]
    ] == ["[EXAMINER_QUESTION_UNPUBLISHED]"]

    question = await db_session.get(QuestionItem, "question-1")
    assert question is not None
    question.status = "published"
    question.safety_flagged = True
    await db_session.commit()
    publish_flagged_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}/publish",
        headers=admin_headers,
    )
    assert [
        item["reason_code"]
        for item in publish_flagged_response.json()["details"]["gate_results"]
    ] == ["[EXAMINER_QUESTION_SAFETY_FLAGGED]"]


@pytest.mark.asyncio
async def test_should_publish_examiner_agent_and_reject_update_after_publish(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_examiner_publish_refs(db_session)
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/examiner-agents",
        headers=admin_headers,
        json=_examiner_payload(),
    )
    examiner_agent_id = create_response.json()["data"]["examiner_agent_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200
    published = publish_response.json()["data"]
    assert published["status"] == "published"
    assert published["content_hash"].startswith("sha256:")

    update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}",
        headers=admin_headers,
        json={"description": "published records are immutable"},
    )
    assert update_response.status_code == 409
    assert update_response.json()["error"] == "[EXAMINER_AGENT_NOT_EDITABLE]"


@pytest.mark.asyncio
async def test_should_simulate_examiner_agent_without_creating_formal_records(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_examiner_publish_refs(db_session)
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/examiner-agents",
        headers=admin_headers,
        json=_examiner_payload(),
    )
    examiner_agent_id = create_response.json()["data"]["examiner_agent_id"]
    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200

    simulate_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/examiner-agents/{examiner_agent_id}/simulate",
        headers=admin_headers,
        json={"learner_level": "beginner", "sample_answer": "我会确认预算和决策链。"},
    )

    assert simulate_response.status_code == 200
    data = simulate_response.json()["data"]
    assert data["mode"] == "dry_run"
    assert data["mutates_records"] is False
    assert data["selected_question_id"] == "question-1"
    assert data["learner_level"] == "beginner"
    assert data["timeout_seconds"] == 600
    assert data["result"] == {
        "passed": True,
        "score": 10,
        "feedback": "dry_run_examiner_check",
        "question_title": "预算确认",
    }
    assert (await db_session.execute(PracticeSession.__table__.select())).all() == []
