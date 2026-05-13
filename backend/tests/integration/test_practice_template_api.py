from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent.models import Agent, Persona, VoiceRuntimeProfile
from common.auth.service import create_access_token
from common.db.models import Base, ScoringRuleset, User
from common.db.session import get_db
from common.knowledge.models import KnowledgeBase
from curriculum_practice.services.content_assets import (
    case_item_content_hash,
    role_profile_content_hash,
)
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
        wechat_user_id="curriculum-admin",
        name="Curriculum Admin",
        email="curriculum-admin@example.com",
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


async def _seed_publishable_references(db: AsyncSession) -> None:
    db.add_all(
        [
            Agent(
                id="agent-1",
                name="Published Agent",
                description="agent",
                category="sales",
                status="published",
            ),
            Persona(
                id="persona-1",
                name="Active Persona",
                description="persona",
                category="customer",
                system_prompt="Act as a customer.",
                status="active",
            ),
            VoiceRuntimeProfile(
                id="runtime-1",
                name="StepFun Runtime",
                is_active=True,
                voice_mode="stepfun_realtime",
                model_name="step-audio-2",
                voice_name="qingchunshaonv",
            ),
            ScoringRuleset(
                ruleset_id="ruleset-1",
                scenario_type="sales",
                version="sales-v1",
                display_name="Sales v1",
                status="published",
                definition_json={"scenario_type": "sales"},
                is_active=True,
            ),
            KnowledgeBase(
                id="kb-1",
                name="Sales KB",
                description="kb",
                category="product",
                vector_collection="sales_kb",
                status="active",
            ),
        ]
    )
    await db.commit()


def _template_payload() -> dict[str, object]:
    return {
        "name": "客户异议处理训练",
        "description": "最小 PracticeTemplate 草稿",
        "scenario_type": "sales",
        "mode": "customer_roleplay",
        "agent_id": "agent-1",
        "persona_id": "persona-1",
        "runtime_profile_id": "runtime-1",
        "voice_mode": "stepfun_realtime",
        "scoring_ruleset_id": "ruleset-1",
        "knowledge_base_refs": ["kb-1"],
    }


def _curriculum_plan_payload(child_template: dict[str, object]) -> dict[str, object]:
    return {
        "name": "多阶段课程训练",
        "description": None,
        "max_stage_duration_seconds": 900,
        "stages": [
            {
                "template_stage_key": "template_stage_opening",
                "order": 1,
                "name": "开场",
                "template_ref": {
                    "asset_type": "practice_template",
                    "asset_id": child_template["template_id"],
                    "version": child_template["version"],
                    "hash": child_template["content_hash"],
                    "snapshot_label": "published",
                },
                "completion_policy": {
                    "min_score": 7.0,
                    "min_rounds": 1,
                    "max_duration_seconds": 600,
                },
                "failure_policy": "retry_current",
                "prerequisites": [],
            }
        ],
    }


def _case_item_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "industry": "金融科技",
        "company_profile": "中型支付平台，正在评估企业级销售训练系统。",
        "customer_role": "CTO",
        "pain_points": ["销售新人上手慢"],
        "objections": ["预算紧张"],
        "hidden_information": "真实预算已批复，但客户不会主动透露。",
        "success_criteria": ["识别预算状态"],
        "allowed_disclosure_policy": {
            "phases": [{"trigger": "询问预算", "keywords": ["预算"], "disclose": "预算范围"}]
        },
        "content_hash": "sha256:pending",
    }
    payload["content_hash"] = case_item_content_hash(payload)
    return payload


def _role_profile_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "role_type": "customer",
        "role_name": "谨慎型 CTO",
        "persona_ref": None,
        "communication_style": "直接、重视技术细节和风险控制",
        "pressure_level": "high",
        "knowledge_boundary": ["了解内部预算流程"],
        "behavior_rules": ["只回答被直接提问的问题"],
        "voice_style_hint": "语速偏快，语调克制",
        "content_hash": "sha256:pending",
    }
    payload["content_hash"] = role_profile_content_hash(payload)
    return payload


@pytest.mark.asyncio
async def test_should_manage_case_item_and_role_profile_assets_lifecycle(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    case_payload = _case_item_payload()
    case_create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/case-items",
        headers=admin_headers,
        json=case_payload,
    )
    assert case_create_response.status_code == 200
    created_case = case_create_response.json()["data"]
    assert created_case["status"] == "draft"

    case_list_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/case-items",
        headers=admin_headers,
    )
    assert case_list_response.status_code == 200
    assert case_list_response.json()["data"]["total"] == 1

    updated_case_payload = case_payload | {
        "pain_points": ["销售新人上手慢", "异议处理话术不一致"],
    }
    updated_case_payload["content_hash"] = case_item_content_hash(updated_case_payload)
    case_update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/case-items/{created_case['case_item_id']}",
        headers=admin_headers,
        json=updated_case_payload,
    )
    assert case_update_response.status_code == 200
    assert case_update_response.json()["data"]["pain_points"] == [
        "销售新人上手慢",
        "异议处理话术不一致",
    ]

    case_publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/case-items/{created_case['case_item_id']}/publish",
        headers=admin_headers,
    )
    assert case_publish_response.status_code == 200
    assert case_publish_response.json()["data"]["status"] == "published"

    case_read_response = await async_client.get(
        f"/api/v1/admin/curriculum-practice/case-items/{created_case['case_item_id']}",
        headers=admin_headers,
    )
    assert case_read_response.status_code == 200
    assert case_read_response.json()["data"]["case_item_id"] == created_case["case_item_id"]

    case_archive_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/case-items/{created_case['case_item_id']}/archive",
        headers=admin_headers,
    )
    assert case_archive_response.status_code == 200
    assert case_archive_response.json()["data"]["status"] == "archived"

    role_payload = _role_profile_payload()
    role_create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/role-profiles",
        headers=admin_headers,
        json=role_payload,
    )
    assert role_create_response.status_code == 200
    created_role = role_create_response.json()["data"]
    assert created_role["status"] == "draft"

    role_list_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/role-profiles",
        headers=admin_headers,
    )
    assert role_list_response.status_code == 200
    assert role_list_response.json()["data"]["total"] == 1

    updated_role_payload = role_payload | {"pressure_level": "medium"}
    updated_role_payload["content_hash"] = role_profile_content_hash(updated_role_payload)
    role_update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/role-profiles/{created_role['role_profile_id']}",
        headers=admin_headers,
        json=updated_role_payload,
    )
    assert role_update_response.status_code == 200
    assert role_update_response.json()["data"]["pressure_level"] == "medium"

    role_publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/role-profiles/{created_role['role_profile_id']}/publish",
        headers=admin_headers,
    )
    assert role_publish_response.status_code == 200
    assert role_publish_response.json()["data"]["status"] == "published"

    role_read_response = await async_client.get(
        f"/api/v1/admin/curriculum-practice/role-profiles/{created_role['role_profile_id']}",
        headers=admin_headers,
    )
    assert role_read_response.status_code == 200
    assert role_read_response.json()["data"]["role_profile_id"] == created_role["role_profile_id"]

    role_archive_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/role-profiles/{created_role['role_profile_id']}/archive",
        headers=admin_headers,
    )
    assert role_archive_response.status_code == 200
    assert role_archive_response.json()["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_should_create_list_and_update_practice_template_draft(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["name"] == "客户异议处理训练"
    assert created["status"] == "draft"
    assert created["version"] == 1

    list_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1

    read_response = await async_client.get(
        f"/api/v1/admin/curriculum-practice/templates/{created['template_id']}",
        headers=admin_headers,
    )
    assert read_response.status_code == 200
    assert read_response.json()["data"]["template_id"] == created["template_id"]

    update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/templates/{created['template_id']}",
        headers=admin_headers,
        json={"description": "更新后的草稿说明"},
    )

    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["template_id"] == created["template_id"]
    assert updated["description"] == "更新后的草稿说明"

    archive_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{created['template_id']}/archive",
        headers=admin_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_should_return_publish_gate_failure_when_template_reference_is_missing(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )
    template_id = create_response.json()["data"]["template_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 400
    payload = publish_response.json()
    assert payload["error"] == "[PRACTICE_TEMPLATE_PUBLISH_GATE_FAILED]"
    assert [item["reason_code"] for item in payload["details"]["gate_results"]] == [
        "reference_missing",
        "reference_missing",
        "reference_missing",
        "scoring_rubric_missing",
        "reference_missing",
    ]


@pytest.mark.asyncio
async def test_should_publish_practice_template_when_gate_passes(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_publishable_references(db_session)
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )
    template_id = create_response.json()["data"]["template_id"]

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}/publish",
        headers=admin_headers,
    )

    assert publish_response.status_code == 200
    published = publish_response.json()["data"]
    assert published["status"] == "published"
    assert published["published_ref"] == {
        "asset_type": "practice_template",
        "asset_id": template_id,
        "version": 1,
        "hash": published["content_hash"],
        "snapshot_label": "published",
    }


@pytest.mark.asyncio
async def test_should_roundtrip_curriculum_plan_and_publish_parent_template(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_publishable_references(db_session)
    child_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload() | {"name": "子阶段模板"},
    )
    assert child_response.status_code == 200
    child_template_id = child_response.json()["data"]["template_id"]
    child_publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{child_template_id}/publish",
        headers=admin_headers,
    )
    assert child_publish_response.status_code == 200
    child = child_publish_response.json()["data"]
    curriculum_plan = _curriculum_plan_payload(child)

    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload()
        | {
            "name": "父课程模板",
            "curriculum_plan": curriculum_plan,
            "max_stage_duration_seconds": 900,
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["data"]
    assert created["curriculum_plan"] == curriculum_plan
    assert created["max_stage_duration_seconds"] == 900

    list_response = await async_client.get(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
    )
    assert list_response.status_code == 200
    listed = next(
        item
        for item in list_response.json()["data"]["items"]
        if item["template_id"] == created["template_id"]
    )
    assert listed["curriculum_plan"] == curriculum_plan
    assert listed["max_stage_duration_seconds"] == 900

    updated_plan = curriculum_plan | {"name": "更新后的课程训练"}
    update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/templates/{created['template_id']}",
        headers=admin_headers,
        json={"curriculum_plan": updated_plan, "max_stage_duration_seconds": 800},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["curriculum_plan"] == updated_plan
    assert updated["max_stage_duration_seconds"] == 800

    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{created['template_id']}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["data"]["status"] == "published"


@pytest.mark.asyncio
async def test_should_reject_update_when_practice_template_is_not_draft(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await _seed_publishable_references(db_session)
    create_response = await async_client.post(
        "/api/v1/admin/curriculum-practice/templates",
        headers=admin_headers,
        json=_template_payload(),
    )
    template_id = create_response.json()["data"]["template_id"]
    publish_response = await async_client.post(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}/publish",
        headers=admin_headers,
    )
    assert publish_response.status_code == 200

    update_response = await async_client.put(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}",
        headers=admin_headers,
        json={"description": "不应写入的修改"},
    )

    assert update_response.status_code == 409
    assert update_response.json()["error"] == "[PRACTICE_TEMPLATE_NOT_EDITABLE]"

    read_response = await async_client.get(
        f"/api/v1/admin/curriculum-practice/templates/{template_id}",
        headers=admin_headers,
    )
    assert read_response.status_code == 200
    unchanged = read_response.json()["data"]
    assert unchanged["status"] == "published"
    assert unchanged["description"] == "最小 PracticeTemplate 草稿"
