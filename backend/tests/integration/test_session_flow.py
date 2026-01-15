"""
Integration Tests for Session Flow with Agent Platform

Tests the complete session flow including:
- Session creation with agent_id and persona_id
- Agent-Persona validation
- Enhanced session reports
- Session statistics

References:
- Requirements: R12 (Session Management Enhancement)
- Design: Section 19 (PracticeSession Extension)
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import all models to ensure they're registered with Base.metadata
from common.db.models import Base, User, Scenario, PracticeSession
from agent.models import Agent, AgentPersona, Persona
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.conversation.models import ConversationMessage

from main import app
from common.db.session import get_db


# Test database URL
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
async def test_user(db_session):
    """Create a test user"""
    user = User(
        wechat_user_id="test_wechat_id",
        name="Test User",
        email="test@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def async_client(db_session, test_user):
    """Create async HTTP client for testing"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(async_client):
    """Get authentication headers"""
    try:
        response = await async_client.post("/api/v1/auth/dev-login")
        if response.status_code == 200:
            data = response.json()
            token = data.get("data", {}).get("access_token")
            if token:
                return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass
    return {"Authorization": "Bearer dev_test_token"}


@pytest_asyncio.fixture
async def published_agent(db_session):
    """Create a published agent for testing"""
    agent = Agent(
        name="Test Sales Coach",
        description="Test agent for sales practice",
        icon="🎯",
        category="sales",
        system_prompt="You are a sales coach...",
        welcome_message="Welcome to sales practice!",
        capabilities_config={
            "fuzzy_detection": {"enabled": True},
            "sales_stage": {"enabled": True}
        },
        status="published"
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def active_persona(db_session):
    """Create an active persona for testing"""
    persona = Persona(
        name="Test Customer",
        description="A test customer persona",
        icon="👤",
        category="customer",
        difficulty="medium",
        system_prompt="You are a customer...",
        status="active"
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return persona


@pytest_asyncio.fixture
async def linked_agent_persona(db_session, published_agent, active_persona):
    """Create an agent-persona link"""
    link = AgentPersona(
        agent_id=published_agent.id,
        persona_id=active_persona.id,
        display_order=0,
        is_default=True
    )
    db_session.add(link)
    await db_session.commit()
    return link


class TestSessionCreationWithAgentPlatform:
    """Tests for session creation with Agent Platform - R12.1, R12.2"""
    
    async def test_create_session_with_agent_and_persona(
        self, 
        async_client, 
        auth_headers, 
        published_agent, 
        active_persona,
        linked_agent_persona
    ):
        """Should create session with agent_id and persona_id - R12.1"""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": active_persona.id
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
    
    async def test_create_session_validates_persona_linked_to_agent(
        self, 
        async_client, 
        auth_headers, 
        published_agent, 
        db_session
    ):
        """Should reject if persona not linked to agent - R12.2"""
        # Create unlinked persona
        unlinked_persona = Persona(
            name="Unlinked Persona",
            description="Not linked to any agent",
            category="customer",
            difficulty="easy",
            system_prompt="...",
            status="active"
        )
        db_session.add(unlinked_persona)
        await db_session.commit()
        await db_session.refresh(unlinked_persona)
        
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": unlinked_persona.id
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "PERSONA_NOT_LINKED_TO_AGENT" in response.text
    
    async def test_create_session_validates_agent_published(
        self, 
        async_client, 
        auth_headers, 
        active_persona,
        db_session
    ):
        """Should reject if agent not published"""
        # Create draft agent
        draft_agent = Agent(
            name="Draft Agent",
            description="Not published",
            category="sales",
            status="draft"
        )
        db_session.add(draft_agent)
        await db_session.commit()
        await db_session.refresh(draft_agent)
        
        # Link persona to draft agent
        link = AgentPersona(
            agent_id=draft_agent.id,
            persona_id=active_persona.id
        )
        db_session.add(link)
        await db_session.commit()
        
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": draft_agent.id,
                "persona_id": active_persona.id
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "AGENT_NOT_PUBLISHED" in response.text
    
    async def test_create_session_legacy_mode_still_works(
        self, 
        async_client, 
        auth_headers
    ):
        """Should still support legacy sales_persona mode"""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "sales_persona": "impatient_ceo"
            },
            headers=auth_headers
        )
        
        # May fail due to bot service not being available in test
        # but should not fail due to validation
        assert response.status_code in [200, 500]


class TestSessionStats:
    """Tests for session statistics - R12.4"""
    
    async def test_get_session_stats_empty(
        self, 
        async_client, 
        auth_headers
    ):
        """Should return zero stats for new user"""
        response = await async_client.get(
            "/api/v1/sessions/stats",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 0
        assert data["weekly_sessions"] == 0
        assert data["average_score"] == 0.0
        assert data["completed_sessions"] == 0
    
    async def test_get_session_stats_with_sessions(
        self, 
        async_client, 
        auth_headers,
        db_session
    ):
        """Should return correct stats with sessions"""
        from datetime import datetime, timedelta
        from common.auth.service import get_dev_user
        
        # Get the dev user that was created by auth
        dev_user = await get_dev_user(db_session)
        
        # Create a scenario first
        scenario = Scenario(
            scenario_type="sales",
            name="test_scenario",
            is_active=True
        )
        db_session.add(scenario)
        await db_session.flush()
        
        # Create some sessions for the dev user
        session1 = PracticeSession(
            user_id=dev_user.user_id,
            scenario_id=scenario.scenario_id,
            status="completed",
            logic_score=80,
            accuracy_score=75,
            completeness_score=85,
            total_duration_seconds=600,
            start_time=datetime.utcnow() - timedelta(days=1)
        )
        session2 = PracticeSession(
            user_id=dev_user.user_id,
            scenario_id=scenario.scenario_id,
            status="completed",
            logic_score=90,
            accuracy_score=85,
            completeness_score=80,
            total_duration_seconds=900,
            start_time=datetime.utcnow() - timedelta(days=2)
        )
        session3 = PracticeSession(
            user_id=dev_user.user_id,
            scenario_id=scenario.scenario_id,
            status="in_progress",
            start_time=datetime.utcnow() - timedelta(days=10)  # Outside weekly
        )
        
        db_session.add_all([session1, session2, session3])
        await db_session.commit()
        
        response = await async_client.get(
            "/api/v1/sessions/stats",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] == 3
        assert data["weekly_sessions"] == 2  # Only sessions in last 7 days
        assert data["completed_sessions"] == 2
        assert data["total_practice_minutes"] == 25  # (600 + 900) / 60


class TestEnhancedSessionReport:
    """Tests for enhanced session reports - R12.3"""
    
    async def test_get_enhanced_report_requires_completed_session(
        self, 
        async_client, 
        auth_headers,
        db_session
    ):
        """Should reject if session not completed"""
        from common.auth.service import get_dev_user
        
        # Get the dev user that was created by auth
        dev_user = await get_dev_user(db_session)
        
        # Create a scenario first
        scenario = Scenario(
            scenario_type="sales",
            name="test_scenario",
            is_active=True
        )
        db_session.add(scenario)
        await db_session.flush()
        
        # Create in-progress session for the dev user
        session = PracticeSession(
            user_id=dev_user.user_id,
            scenario_id=scenario.scenario_id,
            status="in_progress"
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)
        
        response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/enhanced-report",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "SESSION_NOT_COMPLETED" in response.text
    
    async def test_get_enhanced_report_with_scores(
        self, 
        async_client, 
        auth_headers,
        db_session,
        published_agent,
        active_persona
    ):
        """Should return enhanced report with dimension scores"""
        from datetime import datetime, timedelta
        from common.auth.service import get_dev_user
        
        # Get the dev user that was created by auth
        dev_user = await get_dev_user(db_session)
        
        # Create a scenario first
        scenario = Scenario(
            scenario_type="sales",
            name="test_scenario",
            is_active=True
        )
        db_session.add(scenario)
        await db_session.flush()
        
        # Create completed session with agent/persona for the dev user
        session = PracticeSession(
            user_id=dev_user.user_id,
            scenario_id=scenario.scenario_id,
            agent_id=published_agent.id,
            persona_id=active_persona.id,
            status="completed",
            logic_score=85,
            accuracy_score=78,
            completeness_score=90,
            start_time=datetime.utcnow() - timedelta(minutes=30),
            end_time=datetime.utcnow(),
            total_duration_seconds=1800
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)
        
        response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/enhanced-report",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "overall_score" in data
        assert "dimension_scores" in data
        assert "strengths" in data
        assert "improvements" in data
        assert "suggestions" in data
        assert data["agent_name"] == "Test Sales Coach"
        assert data["persona_name"] == "Test Customer"
        assert data["duration_seconds"] == 1800


class TestFullSessionFlow:
    """Tests for complete session flow"""
    
    async def test_complete_session_flow_with_agent_platform(
        self, 
        async_client, 
        auth_headers,
        published_agent,
        active_persona,
        linked_agent_persona,
        db_session
    ):
        """Test complete flow: create -> (practice) -> end -> report"""
        # 1. Create session with agent/persona
        create_response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": active_persona.id
            },
            headers=auth_headers
        )
        
        assert create_response.status_code == 200
        session_data = create_response.json()
        session_id = session_data["session_id"]
        
        # 2. Get session details
        get_response = await async_client.get(
            f"/api/v1/practice/sessions/{session_id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 200
        
        # 3. Update session status to completed (simulating end of practice)
        # In real scenario, this would happen through WebSocket
        from sqlalchemy import select
        stmt = select(PracticeSession).where(PracticeSession.session_id == session_id)
        result = await db_session.execute(stmt)
        session = result.scalar_one()
        session.status = "completed"
        session.logic_score = 80
        session.accuracy_score = 75
        session.completeness_score = 85
        await db_session.commit()
        
        # 4. Get enhanced report
        report_response = await async_client.get(
            f"/api/v1/sessions/{session_id}/enhanced-report",
            headers=auth_headers
        )
        
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["overall_score"] > 0
        assert report["agent_name"] == published_agent.name
        assert report["persona_name"] == active_persona.name
