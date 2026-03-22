"""
Integration Tests for Replay API

Tests for conversation replay endpoints.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
- API Contract: docs/api-contract/replay.md
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import all models to ensure they're registered with Base.metadata
from common.db.models import Base, User, Scenario, PracticeSession, SessionStatus
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
async def completed_session(db_session, test_user):
    """Create a completed practice session"""
    # Create scenario first
    scenario = Scenario(
        name="Sales Practice",
        description="Sales practice scenario",
        scenario_type="sales"
    )
    db_session.add(scenario)
    await db_session.flush()
    
    session = PracticeSession(
        user_id=test_user.user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.COMPLETED.value,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc)
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def other_user(db_session):
    """Create a second user for access-control tests."""
    user = User(
        wechat_user_id="other_wechat_id",
        name="Other User",
        email="other@example.com"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user_headers(db_session, other_user):
    """JWT auth header for other user."""
    from common.auth.service import create_access_token

    token = create_access_token(data={"sub": str(other_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def in_progress_session(db_session, test_user):
    """Create an in-progress practice session"""
    scenario = Scenario(
        name="Sales Practice 2",
        description="Sales practice scenario",
        scenario_type="sales"
    )
    db_session.add(scenario)
    await db_session.flush()
    
    session = PracticeSession(
        user_id=test_user.user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.IN_PROGRESS.value,
        start_time=datetime.now(timezone.utc)
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def sample_messages(db_session, completed_session):
    """Create sample messages for a session"""
    messages = []
    for i in range(3):
        msg = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=i + 1,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Test message {i + 1}",
            audio_url=f"https://storage.example.com/audio/msg-{i + 1}.mp3" if i == 0 else None,
            timestamp=datetime.now(timezone.utc),
            duration_ms=3000 + i * 500,
            sales_stage="opening" if i < 2 else "discovery",
            is_highlight=i == 1,
            highlight_type="good" if i == 1 else None,
            highlight_reason="Good response" if i == 1 else None
        )
        db_session.add(msg)
        messages.append(msg)
    
    await db_session.commit()
    for msg in messages:
        await db_session.refresh(msg)
    return messages


class TestReplayAPI:
    """Integration tests for Replay API"""

    # ========== GET /sessions/{session_id}/messages tests ==========

    @pytest.mark.asyncio
    async def test_should_return_messages_when_session_completed(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should return messages when session is completed"""
        # Arrange - fixtures provide completed session with messages
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/messages",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["messages"]) == 3
        assert data["data"]["total"] == 3

    @pytest.mark.asyncio
    async def test_should_return_400_when_session_not_completed(
        self,
        async_client,
        auth_headers,
        in_progress_session
    ):
        """Should return 400 when session is not completed"""
        # Arrange - fixture provides in-progress session
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{in_progress_session.session_id}/messages",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[SESSION_NOT_COMPLETED]"
        assert body.get("trace_id")
        assert "detail" not in body

    @pytest.mark.asyncio
    async def test_should_return_404_when_session_not_found(
        self,
        async_client,
        auth_headers
    ):
        """Should return 404 when session does not exist"""
        # Arrange
        fake_session_id = str(uuid.uuid4())
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{fake_session_id}/messages",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_should_paginate_messages_when_page_params_provided(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should paginate messages when page parameters are provided"""
        # Arrange - fixtures provide 3 messages
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/messages",
            params={"page": 1, "page_size": 2},
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["messages"]) == 2
        assert data["data"]["total"] == 3

    # ========== GET /sessions/{session_id}/messages/{message_id} tests ==========

    @pytest.mark.asyncio
    async def test_should_return_message_detail_when_message_exists(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should return message detail when message exists"""
        # Arrange
        message = sample_messages[0]
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/messages/{message.id}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == message.id
        assert data["data"]["content"] == "Test message 1"

    @pytest.mark.asyncio
    async def test_should_return_404_when_message_not_found(
        self,
        async_client,
        auth_headers,
        completed_session
    ):
        """Should return 404 when message does not exist"""
        # Arrange
        fake_message_id = str(uuid.uuid4())
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/messages/{fake_message_id}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 404

    # ========== GET /sessions/{session_id}/replay tests ==========

    @pytest.mark.asyncio
    async def test_should_return_replay_data_when_session_completed(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should return replay data when session is completed"""
        # Arrange - fixtures provide completed session with messages
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/replay",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["session_id"] == completed_session.session_id
        assert "messages" in data["data"]
        assert "timeline_markers" in data["data"]

    @pytest.mark.asyncio
    async def test_should_normalize_legacy_zero_turn_number_for_messages_and_replay(
        self,
        async_client,
        auth_headers,
        completed_session,
        db_session
    ):
        """Legacy records with turn_number=0 should be normalized to 1+ in API responses."""
        legacy_msg = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=0,
            role="user",
            content="legacy turn zero",
            timestamp=datetime.now(timezone.utc),
            is_highlight=False,
        )
        db_session.add(legacy_msg)
        await db_session.commit()

        messages_resp = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/messages",
            headers=auth_headers,
        )
        assert messages_resp.status_code == 200
        messages_body = messages_resp.json()
        assert messages_body["success"] is True
        assert messages_body["data"]["messages"][0]["turn_number"] >= 1

        replay_resp = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/replay",
            headers=auth_headers,
        )
        assert replay_resp.status_code == 200
        replay_body = replay_resp.json()
        assert replay_body["success"] is True
        assert replay_body["data"]["messages"][0]["turn_number"] >= 1

    @pytest.mark.asyncio
    async def test_should_return_400_for_replay_when_session_not_completed(
        self,
        async_client,
        auth_headers,
        in_progress_session
    ):
        """Should return 400 for replay when session is not completed"""
        # Arrange - fixture provides in-progress session
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{in_progress_session.session_id}/replay",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 400

    # ========== GET /sessions/{session_id}/highlights tests ==========

    @pytest.mark.asyncio
    async def test_should_return_highlights_when_session_completed(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should return highlights when session is completed"""
        # Arrange - fixtures provide 1 highlight in sample_messages
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/highlights",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["highlights"]) == 1
        assert data["data"]["highlights"][0]["highlight_type"] == "good"
        assert data["data"]["total_good"] == 1
        assert data["data"]["total_bad"] == 0

    @pytest.mark.asyncio
    async def test_should_return_empty_highlights_when_none_exist(
        self,
        async_client,
        auth_headers,
        completed_session,
        db_session
    ):
        """Should return empty highlights when none exist"""
        # Arrange - create message without highlight
        msg = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=1,
            role="user",
            content="No highlight message",
            timestamp=datetime.now(timezone.utc),
            is_highlight=False
        )
        db_session.add(msg)
        await db_session.commit()
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/highlights",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["highlights"]) == 0
        assert data["data"]["total_good"] == 0
        assert data["data"]["total_bad"] == 0

    # ========== GET /sessions/{session_id}/audio/{message_id} tests ==========

    @pytest.mark.asyncio
    async def test_should_redirect_to_audio_url_when_audio_exists(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should redirect to audio URL when audio exists"""
        # Arrange - first message has audio_url
        message = sample_messages[0]
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/audio/{message.id}",
            headers=auth_headers,
            follow_redirects=False
        )
        
        # Assert
        assert response.status_code == 307
        assert response.headers["location"] == message.audio_url

    @pytest.mark.asyncio
    async def test_should_return_404_when_audio_not_available(
        self,
        async_client,
        auth_headers,
        completed_session,
        sample_messages
    ):
        """Should return 404 when audio is not available"""
        # Arrange - second message has no audio_url
        message = sample_messages[1]
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/audio/{message.id}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_should_return_404_for_audio_when_message_not_found(
        self,
        async_client,
        auth_headers,
        completed_session
    ):
        """Should return 404 for audio when message does not exist"""
        # Arrange
        fake_message_id = str(uuid.uuid4())
        
        # Act
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/audio/{fake_message_id}",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_should_return_403_for_messages_of_other_user_session(
        self,
        async_client,
        other_user_headers,
        completed_session,
    ):
        """Should deny access to another user's replay messages."""
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/messages",
            headers=other_user_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[ACCESS_DENIED]"
        assert body.get("trace_id")
        assert "detail" not in body

    @pytest.mark.asyncio
    async def test_should_return_403_for_replay_of_other_user_session(
        self,
        async_client,
        other_user_headers,
        completed_session,
    ):
        """Should deny access to another user's replay data."""
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/replay",
            headers=other_user_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[ACCESS_DENIED]"
        assert body.get("trace_id")
        assert "detail" not in body

    @pytest.mark.asyncio
    async def test_should_return_403_for_highlights_of_other_user_session(
        self,
        async_client,
        other_user_headers,
        completed_session,
    ):
        """Should deny access to another user's highlights."""
        response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/highlights",
            headers=other_user_headers,
        )

        assert response.status_code == 403
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[ACCESS_DENIED]"
        assert body.get("trace_id")
        assert "detail" not in body
