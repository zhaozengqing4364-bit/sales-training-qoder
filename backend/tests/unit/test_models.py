"""
Unit tests for database models (T020-T022)
Tests for User, Scenario, and PracticeSession models
"""
from uuid import uuid4

import pytest
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.db.models import (
    Base,
    InterruptionEvent,
    PracticeSession,
    Scenario,
    ScenarioType,
    SessionStatus,
    User,
)


# Test database setup with UUID support
@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing"""
    # Use SQLite with TEXT type for UUID compatibility
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Override UUID type for SQLite testing
    import uuid

    from sqlalchemy import TypeDecorator
    from sqlalchemy.dialects.postgresql import UUID

    class UUIDType(TypeDecorator):
        """Platform-independent UUID type for SQLite testing"""

        impl = String(32)
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return str(value)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            return uuid.UUID(value)

    # Replace UUID with String for testing
    original_uuid_type = UUID

    def create_tables():
        # Create all tables with String instead of UUID for SQLite
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if isinstance(column.type, original_uuid_type):
                    column.type = UUIDType()
        Base.metadata.create_all(bind=engine)

    create_tables()
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine) -> Session:
    """Create database session for testing"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestUserModel:
    """T020-P1: Test User model"""

    def test_create_user(self, db_session: Session):
        """Should create user with required fields"""
        user = User(
            wechat_user_id="wechat_123",
            name="Test User",
            department="Sales",
            email="test@example.com",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.user_id is not None
        assert user.wechat_user_id == "wechat_123"
        assert user.name == "Test User"
        assert user.department == "Sales"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.created_at is not None

    def test_user_unique_wechat_id(self, db_session: Session):
        """Should enforce unique wechat_user_id"""
        user1 = User(wechat_user_id="wechat_123", name="User 1")
        user2 = User(wechat_user_id="wechat_123", name="User 2")
        db_session.add(user1)
        db_session.add(user2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_user_relationships(self, db_session: Session):
        """Should create relationships with sessions and leaderboard"""
        user = User(wechat_user_id="wechat_123", name="Test User")
        db_session.add(user)
        db_session.flush()

        # Create practice session
        session = PracticeSession(
            user_id=user.user_id,
            scenario_id=str(uuid4()),
            status=SessionStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.commit()

        assert len(user.practice_sessions) == 1


class TestScenarioModel:
    """T021-P1: Test Scenario model"""

    def test_create_scenario(self, db_session: Session):
        """Should create scenario with required fields"""
        scenario = Scenario(
            scenario_type=ScenarioType.PRESENTATION,
            name="PPT Practice",
            description="Practice presentation skills",
            is_active=True,
        )
        db_session.add(scenario)
        db_session.commit()
        db_session.refresh(scenario)

        assert scenario.scenario_id is not None
        assert scenario.scenario_type == ScenarioType.PRESENTATION
        assert scenario.name == "PPT Practice"
        assert scenario.is_active is True

    def test_scenario_type_validation(self, db_session: Session):
        """Should validate scenario_type enum"""
        scenario = Scenario(
            scenario_type=ScenarioType.SALES,
            name="Sales Bot",
            persona_prompt="You are a difficult customer",
        )
        db_session.add(scenario)
        db_session.commit()

        assert scenario.scenario_type == ScenarioType.SALES
        assert scenario.persona_prompt == "You are a difficult customer"


class TestPracticeSessionModel:
    """T022-P1: Test PracticeSession model"""

    def test_create_practice_session(self, db_session: Session):
        """Should create practice session with required fields"""
        # Create user and scenario first
        user = User(wechat_user_id="wechat_123", name="Test User")
        scenario = Scenario(
            scenario_type=ScenarioType.PRESENTATION,
            name="PPT Practice",
        )
        db_session.add(user)
        db_session.add(scenario)
        db_session.flush()

        session = PracticeSession(
            user_id=user.user_id,
            scenario_id=scenario.scenario_id,
            status=SessionStatus.PREPARING,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.session_id is not None
        assert session.user_id == user.user_id
        assert session.scenario_id == scenario.scenario_id
        assert session.status == SessionStatus.PREPARING
        assert session.start_time is not None

    def test_session_score_validation(self, db_session: Session):
        """Should validate score ranges (0-100)"""
        user = User(wechat_user_id="wechat_123", name="Test User")
        scenario = Scenario(scenario_type=ScenarioType.PRESENTATION, name="PPT Practice")
        db_session.add(user)
        db_session.add(scenario)
        db_session.flush()

        session = PracticeSession(
            user_id=user.user_id,
            scenario_id=scenario.scenario_id,
            status=SessionStatus.COMPLETED,
            logic_score=85.5,
            accuracy_score=92.0,
            completeness_score=88.3,
        )
        db_session.add(session)
        db_session.commit()

        assert session.logic_score == 85.5
        assert session.accuracy_score == 92.0
        assert session.completeness_score == 88.3

    def test_session_invalid_score_raises_error(self, db_session: Session):
        """Should reject scores outside 0-100 range"""
        user = User(wechat_user_id="wechat_123", name="Test User")
        scenario = Scenario(scenario_type=ScenarioType.PRESENTATION, name="PPT Practice")
        db_session.add(user)
        db_session.add(scenario)
        db_session.flush()

        session = PracticeSession(
            user_id=user.user_id,
            scenario_id=scenario.scenario_id,
            status=SessionStatus.COMPLETED,
            logic_score=150.0,  # Invalid: > 100
        )
        db_session.add(session)
        with pytest.raises(Exception):  # CheckConstraint violation
            db_session.commit()

    def test_session_relationships(self, db_session: Session):
        """Should create relationship with interruption events"""
        user = User(wechat_user_id="wechat_123", name="Test User")
        scenario = Scenario(scenario_type=ScenarioType.PRESENTATION, name="PPT Practice")
        db_session.add(user)
        db_session.add(scenario)
        db_session.flush()

        session = PracticeSession(
            user_id=user.user_id,
            scenario_id=scenario.scenario_id,
            status=SessionStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.flush()

        # Create interruption event
        interruption = InterruptionEvent(
            session_id=session.session_id,
            interruption_type="forbidden_word",
            trigger_content="um",
            ai_response="Try to avoid saying um",
            detection_latency_ms=50,
        )
        db_session.add(interruption)
        db_session.commit()

        assert len(session.interruption_events) == 1
        assert session.interruption_events[0].interruption_type == "forbidden_word"
