"""
Pytest Configuration and Fixtures
Shared fixtures for all tests
"""

import asyncio
import os
import sys
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.db.models import Base

# Test database URL (SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def test_feature_flags(monkeypatch):
    """Keep compatibility for legacy presentation test fixtures."""
    monkeypatch.setenv("PRESENTATION_REQUIRE_AGENT_PERSONA", "false")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine):
    """Create test database session"""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(test_db):
    """Create async HTTP client for testing"""
    from common.db.session import get_db
    from main import app

    # Override database dependency
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession):
    """Create or return canonical development test user."""
    from common.auth.service import get_dev_user

    os.environ.setdefault("ENVIRONMENT", "development")
    return await get_dev_user(test_db)


@pytest_asyncio.fixture
async def another_user(test_db: AsyncSession):
    """Create a second user for duplicate-email tests."""
    from common.db.models import User

    user = User(
        user_id=str(uuid.uuid4()),
        wechat_user_id=f"another_{uuid.uuid4().hex[:8]}",
        name="Another User",
        department="QA",
        email=f"another_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(async_client):
    """Return authentication headers for testing with valid JWT token"""
    try:
        # Call dev login endpoint to get valid JWT token
        response = await async_client.post("/api/v1/auth/dev-login")
        if response.status_code == 200:
            payload = response.json()
            token = (
                payload.get("access_token")
                or payload.get("token")
                or (payload.get("data") or {}).get("access_token")
            )
            if token:
                return {"Authorization": f"Bearer {token}"}
    except Exception:
        pass
    # Fallback for when dev endpoint is disabled or fails
    return {"Authorization": "Bearer dev_test_token"}


@pytest.fixture
def test_presentation_id():
    """Return a test presentation ID"""
    return str(uuid.uuid4())


@pytest.fixture
def test_session_id():
    """Return a test session ID"""
    return str(uuid.uuid4())


@pytest.fixture
def test_user_id():
    """Return a test user ID"""
    return str(uuid.uuid4())


@pytest.fixture
def test_page_id():
    """Return a test page ID"""
    return str(uuid.uuid4())


@pytest.fixture
def test_file_path(tmp_path):
    """Create a temporary test file for upload tests"""
    test_file = tmp_path / "test.pdf"
    # Create a minimal PDF-like content (just for testing)
    test_file.write_bytes(b"%PDF-1.4\n%test content\n%%EOF")
    return str(test_file)


@pytest.fixture
def test_pdf_file(test_file_path):
    """Backward-compatible alias for integration tests expecting test_pdf_file."""
    return test_file_path
