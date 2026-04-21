"""
Integration Tests for Replay API

Tests for conversation replay endpoints.

References:
- Requirements: R10 (Conversation replay API)
- Design: Section 12 (Replay Service)
- API Contract: docs/api-contract/replay.md
"""
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.conversation.models import ConversationMessage

# Import all models to ensure they're registered with Base.metadata
from common.db.models import Base, PracticeSession, Scenario, SessionStatus, User
from common.db.session import get_db
from common.error_handling.result import Result
from evaluation.services.report_generation_trigger import ReportGenerationTrigger
from main import app

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _without_replay_anchor(value: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key != "replay_anchor"}


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
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC)
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
        start_time=datetime.now(UTC)
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
            timestamp=datetime.now(UTC),
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
    async def test_should_return_learning_evidence_contract_on_replay_and_highlights(
        self,
        async_client,
        auth_headers,
        completed_session,
        db_session,
    ):
        """Replay and highlight payloads should expose the same structured learning evidence line."""
        completed_session.logic_score = 74.0
        completed_session.accuracy_score = 71.0
        completed_session.completeness_score = 69.0
        completed_session.effectiveness_snapshot = {
            "pass_flags": {
                "pass_3min_flow": False,
                "pass_5turn_defense": False,
                "pass_4step_structure": False,
            },
            "main_capability_passed": False,
            "overall_result": "fail",
            "main_issue": {
                "issue_type": "evidence_gap",
                "issue_text": "ROI 证据还没有落到真实案例。",
                "recovery_rule": "下一轮先补 ROI 案例或量化回收，再推进下一步。",
            },
            "next_goal": {
                "goal_type": "evidence_backing",
                "goal_text": "下一轮优先补 ROI 证据。",
                "rule": "至少补一个真实案例或量化回报。",
            },
            "metrics": {
                "continuous_speech_seconds": 180.0,
                "filler_rate_per_100_words": 2.0,
                "offtopic_turn_count": 0.0,
                "offtopic_max_streak": 0.0,
                "structure_coverage": 0.7,
            },
            "version": "rule_v1",
            "evaluable": True,
            "not_evaluable_reason": None,
        }
        db_session.add(completed_session)

        prev_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=1,
            role="assistant",
            content="您现在最需要什么类型的 ROI 证明？",
            timestamp=datetime.now(UTC),
            duration_ms=1800,
            sales_stage="discovery",
            is_highlight=False,
        )
        highlight_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=2,
            role="user",
            content="我们内部还是想先看同行案例和回收周期。",
            timestamp=datetime.now(UTC),
            duration_ms=2400,
            sales_stage="objection",
            fuzzy_words=[
                {
                    "category": "uncertain",
                    "matched": ["差不多"],
                    "suggestion": "直接补同行案例和 ROI 数字",
                    "severity": "high",
                }
            ],
            transcript_metadata={
                "objection_ledger": {
                    "objection_family": "roi_proof",
                    "closure_state": "open",
                    "promised_proof": "补同行 ROI 案例",
                    "next_expected_evidence": "给出回收周期区间",
                }
            },
            ai_feedback="先确认对方需要案例，再补 ROI 和回收周期。",
            is_highlight=True,
            highlight_type="bad",
            highlight_reason="客户已经明确要证据，但这轮还没给出任何案例或数字。",
        )
        next_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=3,
            role="assistant",
            content="我下一轮先给您一个 3 个月回本的同行案例。",
            timestamp=datetime.now(UTC),
            duration_ms=2600,
            sales_stage="objection",
            is_highlight=False,
        )
        db_session.add_all([prev_message, highlight_message, next_message])
        await db_session.commit()
        for message in (prev_message, highlight_message, next_message):
            await db_session.refresh(message)

        replay_response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/replay",
            headers=auth_headers,
        )
        assert replay_response.status_code == 200
        replay_body = replay_response.json()
        assert replay_body["success"] is True
        replay_highlight = next(
            message
            for message in replay_body["data"]["messages"]
            if message["id"] == highlight_message.id
        )
        replay_learning_evidence = replay_highlight["learning_evidence"]
        assert replay_learning_evidence["issue_family"] == "evidence_gap"
        assert replay_learning_evidence["objection_family"] == "roi_proof"
        assert replay_learning_evidence["stage"] == {
            "key": "objection",
            "name": "异议处理",
        }
        assert replay_learning_evidence["linked_issue"]["issue_type"] == "evidence_gap"
        assert replay_learning_evidence["linked_goal"]["goal_type"] == "evidence_backing"
        assert replay_learning_evidence["nearby_context"]["prev_message"]["id"] == prev_message.id
        assert replay_learning_evidence["nearby_context"]["next_message"]["id"] == next_message.id
        assert replay_learning_evidence["suggested_response"] == "建议改进: 直接补同行案例和 ROI 数字"

        highlights_response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/highlights",
            headers=auth_headers,
        )
        assert highlights_response.status_code == 200
        highlights_body = highlights_response.json()
        assert highlights_body["success"] is True
        highlight = highlights_body["data"]["highlights"][0]
        assert highlight["sales_stage"] == "objection"
        assert highlight["stage_name"] == "异议处理"
        assert highlight["context"]["prev_message"]["id"] == prev_message.id
        assert highlight["context"]["next_message"]["id"] == next_message.id
        assert highlight["learning_evidence"]["issue_family"] == "evidence_gap"
        assert highlight["learning_evidence"]["objection_family"] == "roi_proof"
        assert highlight["learning_evidence"]["nearby_context"] == highlight["context"]

    @pytest.mark.asyncio
    async def test_should_return_resolved_replay_anchor_contract_for_issue_and_goal(
        self,
        async_client,
        auth_headers,
        completed_session,
        db_session,
    ):
        """Replay should expose stable issue/goal anchors pointing at the matched highlight marker."""
        completed_session.logic_score = 74.0
        completed_session.accuracy_score = 71.0
        completed_session.completeness_score = 69.0
        completed_session.effectiveness_snapshot = {
            "pass_flags": {
                "pass_3min_flow": False,
                "pass_5turn_defense": False,
                "pass_4step_structure": False,
            },
            "main_capability_passed": False,
            "overall_result": "fail",
            "main_issue": {
                "issue_type": "evidence_gap",
                "issue_text": "ROI 证据还没有落到真实案例。",
                "recovery_rule": "下一轮先补 ROI 案例或量化回收，再推进下一步。",
            },
            "next_goal": {
                "goal_type": "evidence_backing",
                "goal_text": "下一轮优先补 ROI 证据。",
                "rule": "至少补一个真实案例或量化回报。",
            },
            "metrics": {
                "continuous_speech_seconds": 180.0,
                "filler_rate_per_100_words": 2.0,
                "offtopic_turn_count": 0.0,
                "offtopic_max_streak": 0.0,
                "structure_coverage": 0.7,
            },
            "version": "rule_v1",
            "evaluable": True,
            "not_evaluable_reason": None,
        }
        db_session.add(completed_session)

        discovery_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=1,
            role="assistant",
            content="您现在最需要什么类型的 ROI 证明？",
            timestamp=datetime.now(UTC),
            duration_ms=1800,
            sales_stage="discovery",
            is_highlight=False,
        )
        highlight_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=2,
            role="user",
            content="我们内部还是想先看同行案例和回收周期。",
            timestamp=datetime.now(UTC),
            duration_ms=2400,
            sales_stage="objection",
            ai_feedback="先确认对方需要案例，再补 ROI 和回收周期。",
            is_highlight=True,
            highlight_type="bad",
            highlight_reason="客户已经明确要证据，但这轮还没给出任何案例或数字。",
        )
        db_session.add_all([discovery_message, highlight_message])
        await db_session.commit()
        for message in (discovery_message, highlight_message):
            await db_session.refresh(message)

        replay_response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/replay",
            headers=auth_headers,
        )
        assert replay_response.status_code == 200
        body = replay_response.json()
        assert body["success"] is True

        issue_anchor = body["data"]["main_issue"]["replay_anchor"]
        goal_anchor = body["data"]["next_goal"]["replay_anchor"]

        assert issue_anchor["status"] == "resolved"
        assert issue_anchor["message_id"] == highlight_message.id
        assert issue_anchor["turn_number"] == 2
        assert issue_anchor["marker"] == {
            "type": "highlight",
            "timestamp_ms": 1800,
            "label": "客户已经明确要证据，但这轮还没给出任何案例或数字。",
        }
        assert issue_anchor["degraded_reason"] is None

        assert goal_anchor["status"] == "resolved"
        assert goal_anchor["message_id"] == highlight_message.id
        assert goal_anchor["turn_number"] == 2
        assert goal_anchor["marker"]["type"] == "highlight"
        assert goal_anchor["degraded_reason"] is None

    @pytest.mark.asyncio
    async def test_should_surface_degraded_replay_anchor_when_no_highlight_matches(
        self,
        async_client,
        auth_headers,
        completed_session,
        db_session,
    ):
        """Replay should keep the degraded anchor reason visible instead of silently dropping stage fallback."""
        completed_session.logic_score = 68.0
        completed_session.accuracy_score = 66.0
        completed_session.completeness_score = 64.0
        completed_session.effectiveness_snapshot = {
            "pass_flags": {
                "pass_3min_flow": False,
                "pass_5turn_defense": False,
                "pass_4step_structure": False,
            },
            "main_capability_passed": False,
            "overall_result": "fail",
            "main_issue": {
                "issue_type": "objection_handling_gap",
                "issue_text": "价格顾虑已经出现，但还没给出报价逻辑。",
                "recovery_rule": "下一轮先承接价格顾虑，再解释报价依据。",
            },
            "next_goal": {
                "goal_type": "objection_reframe",
                "goal_text": "下一轮先解释报价逻辑，再推进低风险下一步。",
                "rule": "至少先承接价格顾虑，再说明报价或 ROI 逻辑。",
            },
            "metrics": {
                "continuous_speech_seconds": 120.0,
                "filler_rate_per_100_words": 3.0,
                "offtopic_turn_count": 0.0,
                "offtopic_max_streak": 0.0,
                "structure_coverage": 0.5,
            },
            "version": "rule_v1",
            "evaluable": True,
            "not_evaluable_reason": None,
        }
        db_session.add(completed_session)

        discovery_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=1,
            role="assistant",
            content="您目前更担心预算还是上线周期？",
            timestamp=datetime.now(UTC),
            duration_ms=1800,
            sales_stage="discovery",
            is_highlight=False,
        )
        objection_message = ConversationMessage(
            session_id=completed_session.session_id,
            turn_number=2,
            role="user",
            content="最大的顾虑还是价格，你们为什么比别人贵？",
            timestamp=datetime.now(UTC),
            duration_ms=2400,
            sales_stage="objection",
            is_highlight=False,
        )
        db_session.add_all([discovery_message, objection_message])
        await db_session.commit()
        for message in (discovery_message, objection_message):
            await db_session.refresh(message)

        replay_response = await async_client.get(
            f"/api/v1/sessions/{completed_session.session_id}/replay",
            headers=auth_headers,
        )
        assert replay_response.status_code == 200
        body = replay_response.json()
        assert body["success"] is True

        issue_anchor = body["data"]["main_issue"]["replay_anchor"]
        goal_anchor = body["data"]["next_goal"]["replay_anchor"]

        assert issue_anchor["status"] == "degraded"
        assert issue_anchor["message_id"] == objection_message.id
        assert issue_anchor["turn_number"] == 2
        assert issue_anchor["marker"] == {
            "type": "stage_change",
            "timestamp_ms": 1800,
            "label": "异议处理",
        }
        assert issue_anchor["degraded_reason"] == "no_matching_highlight"

        assert goal_anchor["status"] == "degraded"
        assert goal_anchor["message_id"] == objection_message.id
        assert goal_anchor["turn_number"] == 2
        assert goal_anchor["marker"]["type"] == "stage_change"
        assert goal_anchor["degraded_reason"] == "no_matching_highlight"

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
            timestamp=datetime.now(UTC),
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

    @pytest.mark.asyncio
    async def test_sales_session_replay_unlocks_after_background_finalization(
        self,
        async_client,
        auth_headers,
        db_session,
        test_user,
    ):
        """A scoring sales session should unlock replay/highlights only after background finalization promotes it."""
        scenario = Scenario(
            name="Sales Finalization",
            description="Replay unlock after background finalization",
            scenario_type="sales",
        )
        db_session.add(scenario)
        await db_session.flush()

        session = PracticeSession(
            user_id=test_user.user_id,
            scenario_id=scenario.scenario_id,
            status=SessionStatus.SCORING.value,
            report_status="processing",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            logic_score=84.0,
            accuracy_score=82.0,
            completeness_score=80.0,
            effectiveness_snapshot={
                "pass_flags": {
                    "pass_3min_flow": True,
                    "pass_5turn_defense": True,
                    "pass_4step_structure": False,
                },
                "main_capability_passed": False,
                "overall_result": "fail",
                "main_issue": {
                    "issue_type": "evidence_gap",
                    "issue_text": "客户已经追问 ROI 案例，但这一轮还没给出证据。",
                    "recovery_rule": "下一轮先补案例和 ROI 数字。",
                },
                "next_goal": {
                    "goal_type": "evidence_backing",
                    "goal_text": "下一轮优先补一条 ROI 证据。",
                    "rule": "至少补一个案例或量化收益。",
                },
                "evaluable": True,
                "not_evaluable_reason": None,
            },
        )
        db_session.add(session)
        await db_session.flush()

        db_session.add_all(
            [
                ConversationMessage(
                    session_id=session.session_id,
                    turn_number=1,
                    role="assistant",
                    content="您现在最想先看哪类 ROI 证明？",
                    timestamp=datetime.now(UTC),
                    duration_ms=1600,
                    sales_stage="discovery",
                    score_snapshot={"overall_score": 82},
                    is_highlight=False,
                ),
                ConversationMessage(
                    session_id=session.session_id,
                    turn_number=2,
                    role="user",
                    content="我们还是想先看同行案例和回收周期。",
                    timestamp=datetime.now(UTC),
                    duration_ms=2200,
                    sales_stage="objection",
                    score_snapshot={"overall_score": 81},
                    is_highlight=True,
                    highlight_type="bad",
                    highlight_reason="客户已经追问 ROI 证据。",
                ),
            ]
        )
        await db_session.commit()
        await db_session.refresh(session)

        report_before = await async_client.get(
            f"/api/v1/practice/sessions/{session.session_id}/report",
            headers=auth_headers,
        )
        replay_before = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/replay",
            headers=auth_headers,
        )
        highlights_before = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/highlights",
            headers=auth_headers,
        )
        assert report_before.status_code == 200
        assert replay_before.status_code == 400
        assert replay_before.json()["error"] == "[SESSION_NOT_COMPLETED]"
        assert highlights_before.status_code == 400
        assert highlights_before.json()["error"] == "[SESSION_NOT_COMPLETED]"

        mock_report_service = AsyncMock()
        mock_report_service.generate_report = AsyncMock(
            return_value=Result.fail("[ENHANCED_REPORT_FAILED]")
        )
        await ReportGenerationTrigger(db_session, mock_report_service).trigger_on_session_end(
            str(session.session_id),
            "sales",
        )
        await db_session.commit()
        await db_session.refresh(session)

        assert session.report_status == "failed"
        assert session.status == SessionStatus.COMPLETED.value

        report_after = await async_client.get(
            f"/api/v1/practice/sessions/{session.session_id}/report",
            headers=auth_headers,
        )
        replay_after = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/replay",
            headers=auth_headers,
        )
        highlights_after = await async_client.get(
            f"/api/v1/sessions/{session.session_id}/highlights",
            headers=auth_headers,
        )
        assert report_after.status_code == 200
        assert replay_after.status_code == 200
        assert replay_after.json()["success"] is True
        assert highlights_after.status_code == 200
        assert highlights_after.json()["success"] is True

        report_after_data = report_after.json()["data"]
        replay_after_data = replay_after.json()["data"]
        assert report_after_data["evidence_completeness"] == replay_after_data["evidence_completeness"]
        assert _without_replay_anchor(report_after_data["main_issue"]) == _without_replay_anchor(
            replay_after_data["main_issue"]
        )
        assert _without_replay_anchor(report_after_data["next_goal"]) == _without_replay_anchor(
            replay_after_data["next_goal"]
        )

    @pytest.mark.asyncio
    async def test_should_keep_highlights_locked_for_true_in_progress_session(
        self,
        async_client,
        auth_headers,
        in_progress_session,
    ):
        """True in-progress sessions should still fail the completion gate."""
        response = await async_client.get(
            f"/api/v1/sessions/{in_progress_session.session_id}/highlights",
            headers=auth_headers,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "[SESSION_NOT_COMPLETED]"

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
            timestamp=datetime.now(UTC),
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
