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

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import all models to ensure they're registered with Base.metadata
from common.db.models import Base, User, Scenario, PracticeSession, Presentation
from agent.models import Agent, AgentPersona, Persona
from common.knowledge.models import KnowledgeBase, KnowledgeDocument
from common.conversation.models import ConversationMessage

from main import app
from common.db.session import get_db


async def _get_auth_user_id(headers: dict[str, str]) -> str:
    """Extract authenticated user id from test auth header token."""
    from common.auth.service import verify_token

    auth = headers.get("Authorization", "")
    token = auth.replace("Bearer ", "", 1)
    payload = verify_token(token)
    return payload["sub"]


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
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user"""
    user = User(
        wechat_user_id="test_wechat_id",
        name="Test User",
        email="test@example.com",
        role="admin",
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
async def auth_headers(test_user):
    """Get authentication headers for fixture user."""
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(test_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


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
            "sales_stage": {"enabled": True},
        },
        status="published",
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
        status="active",
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
        is_default=True,
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
        linked_agent_persona,
    ):
        """Should create session with agent_id and persona_id - R12.1"""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": active_persona.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data["data"]

    async def test_create_presentation_session_auto_creates_default_scenario(
        self,
        async_client,
        auth_headers,
        db_session,
    ):
        """Should create presentation session even when no presentation scenario exists."""
        auth_user_id = await _get_auth_user_id(auth_headers)

        presentation = Presentation(
            presentation_id=str(uuid.uuid4()),
            title="Session Flow Presentation",
            file_url="/tmp/session-flow.pptx",
            status="ready",
            uploaded_by_admin_id=auth_user_id,
            total_pages=3,
        )
        db_session.add(presentation)
        await db_session.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "presentation",
                "presentation_id": presentation.presentation_id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        session_id = body["data"]["session_id"]

        from sqlalchemy import select

        scenario_result = await db_session.execute(
            select(Scenario).where(
                Scenario.scenario_type == "presentation",
                Scenario.is_active.is_(True),
            )
        )
        scenario = scenario_result.scalar_one_or_none()
        assert scenario is not None

        session_result = await db_session.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        session = session_result.scalar_one_or_none()
        assert session is not None
        assert session.scenario_id == scenario.scenario_id
        assert session.presentation_id == presentation.presentation_id

    async def test_create_session_applies_agent_persona_override_config(
        self,
        async_client,
        auth_headers,
        published_agent,
        active_persona,
        db_session,
    ):
        """Should include Agent-Persona override config in session policy snapshot."""
        override_config = {
            "response_length": "short",
            "challenge_frequency": 0.7,
            "custom_tag": "story-1-8",
        }
        link = AgentPersona(
            agent_id=published_agent.id,
            persona_id=active_persona.id,
            display_order=0,
            is_default=True,
            override_config=override_config,
        )
        db_session.add(link)
        await db_session.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": active_persona.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        snapshot = body["data"]["voice_policy_snapshot"]
        assert isinstance(snapshot, dict)
        assert snapshot.get("agent_persona_override_config") == override_config

    async def test_create_session_validates_persona_linked_to_agent(
        self, async_client, auth_headers, published_agent, db_session
    ):
        """Should reject if persona not linked to agent - R12.2"""
        # Create unlinked persona
        unlinked_persona = Persona(
            name="Unlinked Persona",
            description="Not linked to any agent",
            category="customer",
            difficulty="easy",
            system_prompt="...",
            status="active",
        )
        db_session.add(unlinked_persona)
        await db_session.commit()
        await db_session.refresh(unlinked_persona)

        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": unlinked_persona.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "PERSONA_NOT_LINKED_TO_AGENT" in response.text

    async def test_create_session_validates_agent_published(
        self, async_client, auth_headers, active_persona, db_session
    ):
        """Should reject if agent not published"""
        # Create draft agent
        draft_agent = Agent(
            name="Draft Agent",
            description="Not published",
            category="sales",
            status="draft",
        )
        db_session.add(draft_agent)
        await db_session.commit()
        await db_session.refresh(draft_agent)

        # Link persona to draft agent
        link = AgentPersona(agent_id=draft_agent.id, persona_id=active_persona.id)
        db_session.add(link)
        await db_session.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": draft_agent.id,
                "persona_id": active_persona.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "AGENT_NOT_PUBLISHED" in response.text

    async def test_create_session_rejects_archived_agent(
        self,
        async_client,
        auth_headers,
        active_persona,
        db_session,
    ):
        """Should reject creating session when agent is archived."""
        archived_agent = Agent(
            name="Archived Agent",
            description="Archived scenario",
            category="sales",
            status="archived",
        )
        db_session.add(archived_agent)
        await db_session.commit()
        await db_session.refresh(archived_agent)

        link = AgentPersona(
            agent_id=archived_agent.id,
            persona_id=active_persona.id,
        )
        db_session.add(link)
        await db_session.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": archived_agent.id,
                "persona_id": active_persona.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[AGENT_ARCHIVED]"
        assert body["message"] == "[AGENT_ARCHIVED]"
        assert "trace_id" in body

    async def test_create_session_requires_agent_and_persona_as_pair(
        self,
        async_client,
        auth_headers,
        published_agent,
    ):
        """Should reject requests that provide only one of agent_id/persona_id."""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[AGENT_PERSONA_PAIR_REQUIRED]"
        assert body["message"] == "[AGENT_PERSONA_PAIR_REQUIRED]"
        assert "trace_id" in body

    async def test_create_session_rejects_inactive_persona(
        self,
        async_client,
        auth_headers,
        published_agent,
        db_session,
    ):
        """Should reject creating session when persona is inactive."""
        inactive_persona = Persona(
            name="Inactive Persona",
            description="inactive persona for session guard",
            category="customer",
            difficulty="easy",
            system_prompt="inactive",
            status="inactive",
        )
        db_session.add(inactive_persona)
        await db_session.commit()
        await db_session.refresh(inactive_persona)

        link = AgentPersona(
            agent_id=published_agent.id,
            persona_id=inactive_persona.id,
            is_default=True,
        )
        db_session.add(link)
        await db_session.commit()

        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": inactive_persona.id,
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[PERSONA_INACTIVE]"
        assert body["message"] == "[PERSONA_INACTIVE]"
        assert "trace_id" in body

    async def test_create_session_legacy_mode_is_rejected(
        self, async_client, auth_headers
    ):
        """Should reject legacy sales_persona mode in persona-centered runtime."""
        response = await async_client.post(
            "/api/v1/practice/sessions",
            json={"scenario_type": "sales", "sales_persona": "impatient_ceo"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[FIELD_DEPRECATED_PERSONA_CENTERED]"
        assert "sales_persona" in body["message"]


class TestSessionStats:
    """Tests for session statistics - R12.4"""

    async def test_get_session_stats_empty(self, async_client, auth_headers):
        """Should return zero stats for new user"""
        response = await async_client.get(
            "/api/v1/sessions/stats", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_sessions"] == 0
        assert data["weekly_sessions"] == 0
        assert data["average_score"] == 0.0
        assert data["completed_sessions"] == 0

    async def test_get_session_stats_with_sessions(
        self, async_client, auth_headers, db_session
    ):
        """Should return correct stats with sessions"""
        from datetime import datetime, timedelta, timezone

        # Use authenticated fixture user from JWT auth_headers
        auth_user_id = await _get_auth_user_id(auth_headers)

        # Create a scenario first
        scenario = Scenario(scenario_type="sales", name="test_scenario", is_active=True)
        db_session.add(scenario)
        await db_session.flush()

        # Create some sessions for the dev user
        session1 = PracticeSession(
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            status="completed",
            logic_score=80,
            accuracy_score=75,
            completeness_score=85,
            total_duration_seconds=600,
            start_time=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session2 = PracticeSession(
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            status="completed",
            logic_score=90,
            accuracy_score=85,
            completeness_score=80,
            total_duration_seconds=900,
            start_time=datetime.now(timezone.utc) - timedelta(days=2),
        )
        session3 = PracticeSession(
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            status="in_progress",
            start_time=datetime.now(timezone.utc)
            - timedelta(days=10),  # Outside weekly
        )

        db_session.add_all([session1, session2, session3])
        await db_session.commit()

        response = await async_client.get(
            "/api/v1/sessions/stats", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_sessions"] == 3
        assert data["weekly_sessions"] == 2  # Only sessions in last 7 days
        assert data["completed_sessions"] == 2
        assert data["total_practice_minutes"] == 25  # (600 + 900) / 60


class TestEnhancedSessionReport:
    """Tests for enhanced session reports - R12.3"""

    async def test_get_enhanced_report_requires_completed_session(
        self, async_client, auth_headers, db_session
    ):
        """Should reject if session not completed"""
        # Use authenticated fixture user from JWT auth_headers
        auth_user_id = await _get_auth_user_id(auth_headers)

        # Create a scenario first
        scenario = Scenario(scenario_type="sales", name="test_scenario", is_active=True)
        db_session.add(scenario)
        await db_session.flush()

        # Create in-progress session for the dev user
        session = PracticeSession(
            user_id=auth_user_id, scenario_id=scenario.scenario_id, status="in_progress"
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/enhanced-report",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "SESSION_NOT_COMPLETED" in response.text

    async def test_get_enhanced_report_with_scores(
        self, async_client, auth_headers, db_session, published_agent, active_persona
    ):
        """Should return enhanced report with dimension scores"""
        from datetime import datetime, timedelta, timezone

        # Use authenticated fixture user from JWT auth_headers
        auth_user_id = await _get_auth_user_id(auth_headers)

        # Create a scenario first
        scenario = Scenario(scenario_type="sales", name="test_scenario", is_active=True)
        db_session.add(scenario)
        await db_session.flush()

        # Create completed session with agent/persona for the dev user
        session = PracticeSession(
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            agent_id=published_agent.id,
            persona_id=active_persona.id,
            status="completed",
            logic_score=85,
            accuracy_score=78,
            completeness_score=90,
            start_time=datetime.now(timezone.utc) - timedelta(minutes=30),
            end_time=datetime.now(timezone.utc),
            total_duration_seconds=1800,
        )
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        response = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/enhanced-report",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]

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
        db_session,
    ):
        """Test complete flow: create -> (practice) -> end -> report"""
        # 1. Create session with agent/persona
        create_response = await async_client.post(
            "/api/v1/practice/sessions",
            json={
                "scenario_type": "sales",
                "agent_id": published_agent.id,
                "persona_id": active_persona.id,
            },
            headers=auth_headers,
        )

        assert create_response.status_code == 201
        session_data = create_response.json()["data"]
        session_id = session_data["session_id"]

        # 2. Get session details
        get_response = await async_client.get(
            f"/api/v1/practice/sessions/{session_id}", headers=auth_headers
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
            f"/api/v1/sessions/{session_id}/enhanced-report", headers=auth_headers
        )

        assert report_response.status_code == 200
        report = report_response.json()["data"]
        assert report["overall_score"] > 0
        assert report["agent_name"] == published_agent.name
        assert report["persona_name"] == active_persona.name


class TestSessionLifecycleTransitions:
    """Integration tests for explicit lifecycle status transitions."""

    async def test_sales_lifecycle_state_transition_sequence(
        self,
        async_client,
        auth_headers,
        db_session,
    ):
        auth_user_id = await _get_auth_user_id(auth_headers)
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="integration_lifecycle_sales",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            status="preparing",
            voice_mode="legacy",
        )
        db_session.add_all([scenario, session])
        await db_session.commit()
        await db_session.refresh(session)

        transitions = [
            ("start", "preparing", "in_progress"),
            ("pause", "in_progress", "paused"),
            ("resume", "paused", "in_progress"),
            ("end", "in_progress", "scoring"),
        ]

        for action, previous_status, target_status in transitions:
            response = await async_client.post(
                f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
                json={"action": action},
                headers=auth_headers,
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert "trace_id" in body
            assert body["data"]["previous_status"] == previous_status
            assert body["data"]["status"] == target_status
            assert body["data"]["scenario_type"] == "sales"

        from sqlalchemy import select

        persisted = await db_session.execute(
            select(PracticeSession).where(
                PracticeSession.session_id == session.session_id
            )
        )
        updated_session = persisted.scalar_one()
        assert updated_session.status == "scoring"
        assert updated_session.end_time is not None
        assert updated_session.total_duration_seconds is not None
        assert updated_session.total_duration_seconds >= 0

    async def test_presentation_end_transition_sets_completed(
        self,
        async_client,
        auth_headers,
        db_session,
    ):
        auth_user_id = await _get_auth_user_id(auth_headers)
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="presentation",
            name="integration_lifecycle_presentation",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            status="in_progress",
            voice_mode="legacy",
        )
        db_session.add_all([scenario, session])
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session.session_id}/lifecycle",
            json={"action": "end"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "completed"
        assert body["data"]["scenario_type"] == "presentation"

    async def test_lifecycle_invalid_transition_keeps_state_unchanged(
        self,
        async_client,
        auth_headers,
        db_session,
    ):
        auth_user_id = await _get_auth_user_id(auth_headers)
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="integration_lifecycle_invalid",
            is_active=True,
        )
        session = PracticeSession(
            session_id=str(uuid.uuid4()),
            user_id=auth_user_id,
            scenario_id=scenario.scenario_id,
            status="preparing",
            voice_mode="legacy",
        )
        session_id = str(session.session_id)
        db_session.add_all([scenario, session])
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/practice/sessions/{session_id}/lifecycle",
            json={"action": "resume"},
            headers=auth_headers,
        )

        assert response.status_code == 409
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[INVALID_SESSION_TRANSITION]"
        assert body["details"]["current_status"] == "preparing"
        assert body["details"]["requested_action"] == "resume"
        assert "trace_id" in body

        from sqlalchemy import select

        await db_session.rollback()
        persisted = await db_session.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        updated_session = persisted.scalar_one()
        assert updated_session.status == "preparing"
