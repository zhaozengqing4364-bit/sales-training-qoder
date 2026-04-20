"""
Unit Tests for Persona Service

Tests CRUD operations and duplication for Personas.

References:
- Requirements: R3 (Persona Management)
- Design: Section 5 (Persona Service)
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent.models import Agent, AgentPersona, Persona, PersonaStatus
from agent.schemas import (
    BehaviorConfigSchema,
    CreatePersonaRequest,
    UpdatePersonaRequest,
)
from agent.services.persona_service import PersonaService
from common.db.models import Base, PracticeSession, Scenario, User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine with all tables"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Create test database session"""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def persona_service(db_session):
    """Create PersonaService instance"""
    return PersonaService(db_session)


@pytest_asyncio.fixture
async def sample_persona_data():
    """Sample data for creating a Persona"""
    return CreatePersonaRequest(
        name="怀疑型客户",
        description="对销售人员说的每句话都要求证据",
        icon="😤",
        category="customer",
        difficulty="hard",
        system_prompt="你是一个非常怀疑的客户...",
        traits={"性格": "怀疑", "关注点": "证据"},
        knowledge_base_ids=["kb-001"],
        behavior_config=BehaviorConfigSchema(
            response_length="medium",
            challenge_frequency=0.8,
            interruption_triggers=["竞品", "对比"],
            typical_questions=["你说的这个数据有什么依据？"]
        ),
        scoring_weights={"专业度": 0.3, "异议处理": 0.4},
        is_public=True
    )


class TestPersonaServiceCreate:
    """Tests for Persona creation - R3.1"""

    async def test_should_create_persona_with_active_status(
        self, persona_service, sample_persona_data
    ):
        """Should create Persona with active status"""
        result = await persona_service.create(sample_persona_data, user_id="user-001")

        assert result.is_success
        persona = result.value
        assert persona.name == "怀疑型客户"
        assert persona.status == PersonaStatus.ACTIVE.value
        assert persona.category == "customer"
        assert persona.difficulty == "hard"
        assert persona.created_by == "user-001"
        assert persona.id is not None

    async def test_should_create_persona_with_minimal_data(self, persona_service):
        """Should create Persona with minimal required fields"""
        data = CreatePersonaRequest(
            name="Minimal Persona",
            category="coach",
            system_prompt="你是一个教练..."
        )

        result = await persona_service.create(data)

        assert result.is_success
        persona = result.value
        assert persona.name == "Minimal Persona"
        assert persona.difficulty == "medium"
        assert persona.is_public is True

    async def test_should_create_persona_with_persona_policy(
        self, persona_service
    ):
        data = CreatePersonaRequest(
            name="Policy Persona",
            category="customer",
            system_prompt="legacy",
            persona_policy={
                "system_prompt": "persona policy prompt",
                "knowledge_base_ids": ["kb-p1"],
                "tool_policy": {"require_kb_grounding": True},
            },
        )

        result = await persona_service.create(data)

        assert result.is_success
        persona = result.value
        assert persona.system_prompt == "persona policy prompt"
        assert persona.knowledge_base_ids == ["kb-p1"]
        assert persona.persona_policy["tool_policy"]["require_kb_grounding"] is True


class TestPersonaServiceList:
    """Tests for Persona listing - R3.2"""

    async def test_should_return_empty_list_when_no_personas(self, persona_service):
        """Should return empty list when no personas exist"""
        items, total = await persona_service.list()

        assert items == []
        assert total == 0

    async def test_should_return_paginated_results(
        self, persona_service, sample_persona_data
    ):
        """Should return paginated results"""
        for i in range(5):
            data = CreatePersonaRequest(
                name=f"Persona {i}",
                category="customer",
                system_prompt=f"Prompt {i}"
            )
            await persona_service.create(data)

        items, total = await persona_service.list(page=1, page_size=2)

        assert len(items) == 2
        assert total == 5

    async def test_should_filter_by_category(self, persona_service):
        """Should filter by category"""
        await persona_service.create(CreatePersonaRequest(
            name="Customer 1", category="customer", system_prompt="..."
        ))
        await persona_service.create(CreatePersonaRequest(
            name="Coach 1", category="coach", system_prompt="..."
        ))

        items, total = await persona_service.list(category="customer")

        assert total == 1
        assert items[0].category == "customer"

    async def test_should_filter_by_difficulty(self, persona_service):
        """Should filter by difficulty"""
        await persona_service.create(CreatePersonaRequest(
            name="Easy", category="customer", difficulty="easy", system_prompt="..."
        ))
        await persona_service.create(CreatePersonaRequest(
            name="Hard", category="customer", difficulty="hard", system_prompt="..."
        ))

        items, total = await persona_service.list(difficulty="hard")

        assert total == 1
        assert items[0].difficulty == "hard"

    async def test_should_include_usage_and_agent_counts(self, persona_service, db_session):
        """Should populate usage_count and agent_count from database"""
        first = await persona_service.create(
            CreatePersonaRequest(name="Persona A", category="customer", system_prompt="A")
        )
        second = await persona_service.create(
            CreatePersonaRequest(name="Persona B", category="customer", system_prompt="B")
        )

        agent = Agent(name="Agent A", category="sales", status="draft")
        user = User(wechat_user_id="wx-persona-count", name="Count User", role="user")
        scenario = Scenario(scenario_type="sales", name="Count Scenario")
        db_session.add_all([agent, user, scenario])
        await db_session.flush()

        db_session.add(
            AgentPersona(
                agent_id=agent.id,
                persona_id=first.value.id,
                display_order=0,
            )
        )

        db_session.add_all(
            [
                PracticeSession(
                    user_id=user.user_id,
                    scenario_id=scenario.scenario_id,
                    persona_id=first.value.id,
                    status="completed",
                    voice_mode="legacy",
                ),
                PracticeSession(
                    user_id=user.user_id,
                    scenario_id=scenario.scenario_id,
                    persona_id=first.value.id,
                    status="completed",
                    voice_mode="legacy",
                ),
                PracticeSession(
                    user_id=user.user_id,
                    scenario_id=scenario.scenario_id,
                    persona_id=second.value.id,
                    status="completed",
                    voice_mode="legacy",
                ),
            ]
        )
        await db_session.flush()

        items, _ = await persona_service.list(page=1, page_size=20)
        by_name = {item.name: item for item in items}

        assert by_name["Persona A"].agent_count == 1
        assert by_name["Persona A"].usage_count == 2
        assert by_name["Persona B"].agent_count == 0
        assert by_name["Persona B"].usage_count == 1



class TestPersonaServiceGetById:
    """Tests for getting Persona by ID - R3.3"""

    async def test_should_return_persona_when_exists(
        self, persona_service, sample_persona_data
    ):
        """Should return Persona when it exists"""
        create_result = await persona_service.create(sample_persona_data)
        persona_id = create_result.value.id

        result = await persona_service.get_by_id(persona_id)

        assert result.is_success
        assert result.value.name == "怀疑型客户"
        assert result.value.system_prompt == "你是一个非常怀疑的客户..."

    async def test_should_return_error_when_not_found(self, persona_service):
        """Should return error for non-existent persona"""
        result = await persona_service.get_by_id("non-existent-id")

        assert not result.is_success
        assert result.fallback == "[PERSONA_NOT_FOUND]"


class TestPersonaServiceUpdate:
    """Tests for Persona update - R3.4"""

    async def test_should_support_partial_updates(
        self, persona_service, sample_persona_data
    ):
        """Should support partial updates"""
        create_result = await persona_service.create(sample_persona_data)
        persona_id = create_result.value.id

        update_data = UpdatePersonaRequest(name="Updated Name")
        result = await persona_service.update(persona_id, update_data)

        assert result.is_success
        assert result.value.name == "Updated Name"
        assert result.value.category == "customer"

    async def test_should_update_behavior_config(
        self, persona_service, sample_persona_data
    ):
        """Should update behavior_config"""
        create_result = await persona_service.create(sample_persona_data)
        persona_id = create_result.value.id

        new_config = BehaviorConfigSchema(
            response_length="short",
            challenge_frequency=0.5
        )
        update_data = UpdatePersonaRequest(behavior_config=new_config)
        result = await persona_service.update(persona_id, update_data)

        assert result.is_success
        assert result.value.behavior_config["response_length"] == "short"

    async def test_should_return_error_when_not_found(self, persona_service):
        """Should return error for non-existent persona"""
        update_data = UpdatePersonaRequest(name="New Name")
        result = await persona_service.update("non-existent-id", update_data)

        assert not result.is_success
        assert result.fallback == "[PERSONA_NOT_FOUND]"


class TestPersonaServiceDelete:
    """Tests for Persona deletion - R3.5"""

    async def test_should_delete_persona_without_agent_links(
        self, persona_service, sample_persona_data
    ):
        """Should delete persona without agent links"""
        create_result = await persona_service.create(sample_persona_data)
        persona_id = create_result.value.id

        result = await persona_service.delete(persona_id)

        assert result.is_success
        assert result.value is True

        get_result = await persona_service.get_by_id(persona_id)
        assert not get_result.is_success

    async def test_should_return_error_when_not_found(self, persona_service):
        """Should return error for non-existent persona"""
        result = await persona_service.delete("non-existent-id")

        assert not result.is_success
        assert result.fallback == "[PERSONA_NOT_FOUND]"

    async def test_should_fail_when_linked_to_agent(
        self, persona_service, sample_persona_data, db_session
    ):
        """Should fail to delete persona linked to agent"""
        create_result = await persona_service.create(sample_persona_data)
        persona_id = create_result.value.id

        agent = Agent(
            name="Test Agent",
            category="sales",
            status="draft"
        )
        db_session.add(agent)
        await db_session.flush()

        link = AgentPersona(
            agent_id=agent.id,
            persona_id=persona_id,
            display_order=0
        )
        db_session.add(link)
        await db_session.flush()

        result = await persona_service.delete(persona_id)

        assert not result.is_success
        assert result.fallback == "[PERSONA_IN_USE]"


class TestPersonaServiceDuplicate:
    """Tests for Persona duplication - R3.6"""

    async def test_should_duplicate_persona_with_suffix(
        self, persona_service, sample_persona_data
    ):
        """Should duplicate persona with (副本) suffix"""
        create_result = await persona_service.create(sample_persona_data)
        persona_id = create_result.value.id

        result = await persona_service.duplicate(persona_id, user_id="user-002")

        assert result.is_success
        new_persona = result.value
        assert new_persona.name == "怀疑型客户 (副本)"
        assert new_persona.id != persona_id
        assert new_persona.created_by == "user-002"
        assert new_persona.category == "customer"
        assert new_persona.system_prompt == "你是一个非常怀疑的客户..."

    async def test_should_return_error_when_original_not_found(self, persona_service):
        """Should return error when original persona not found"""
        result = await persona_service.duplicate("non-existent-id")

        assert not result.is_success
        assert result.fallback == "[PERSONA_NOT_FOUND]"


class TestPersonaPolicyHealthAudit:
    """Tests for persona policy health audit."""

    async def test_should_report_missing_policy_issue(self, persona_service, db_session):
        legacy_persona = Persona(
            name="Legacy Persona",
            category="customer",
            difficulty="medium",
            status="active",
            system_prompt="legacy prompt",
            persona_policy=None,
            knowledge_base_ids=[],
        )
        db_session.add(legacy_persona)
        await db_session.flush()

        report = await persona_service.audit_policy_health(sample_limit=10)

        assert report["summary"]["total"] >= 1
        assert report["issue_type_counts"]["missing_policy"] >= 1
        assert any(
            issue["persona_id"] == legacy_persona.id
            and "missing_policy" in issue["issue_types"]
            for issue in report["sample_issues"]
        )

    async def test_should_report_kb_lock_unbound_issue(self, persona_service):
        create_result = await persona_service.create(
            CreatePersonaRequest(
                name="KB Lock Persona",
                category="customer",
                system_prompt="policy prompt",
                persona_policy={
                    "system_prompt": "policy prompt",
                    "knowledge_base_ids": [],
                    "tool_policy": {"require_kb_grounding": True},
                },
            )
        )
        assert create_result.is_success

        report = await persona_service.audit_policy_health(sample_limit=10)
        assert report["issue_type_counts"]["kb_lock_unbound"] >= 1
        assert any(
            issue["persona_id"] == create_result.value.id
            and "kb_lock_unbound" in issue["issue_types"]
            for issue in report["sample_issues"]
        )
