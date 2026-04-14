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
import agent.models  # noqa: F401  # Register agent/voice-runtime tables on shared Base metadata.

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
    """Create async HTTP client for testing."""
    import common.auth.service as auth_service
    import main as main_module
    from common.db.session import get_db as current_get_db

    app = main_module.app

    async def override_get_db():
        yield test_db

    # Some tests intentionally reload common.db.session. Routes and auth dependencies
    # mounted before the reload still hold the original get_db callable, so keep both
    # the current module export and the app/auth imported callables overridden.
    override_targets = {
        current_get_db,
        getattr(main_module, "get_db", current_get_db),
        getattr(auth_service, "get_db", current_get_db),
    }
    for target in override_targets:
        app.dependency_overrides[target] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession):
    """Create or return canonical development test user."""
    from common.auth.service import get_dev_user

    os.environ["ENVIRONMENT"] = "development"
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
async def auth_headers(async_client, test_user):
    """Return authentication headers for testing with valid JWT token."""
    from common.auth.service import create_access_token

    os.environ["ENVIRONMENT"] = "development"

    try:
        # Prefer the live dev-login path when it is available so cookie/session
        # transport keeps exercising the mounted auth surface.
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

    token = create_access_token(data={"sub": str(test_user.user_id)})
    return {"Authorization": f"Bearer {token}"}


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
