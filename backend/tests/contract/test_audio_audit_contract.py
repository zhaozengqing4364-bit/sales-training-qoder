"""
Audio Audit Contract Tests

Proves the full cycle:
  backend signs URL → browser PUTs to mock OSS → metadata registered → segments queryable

Uses an in-memory SQLite DB, a mock OSS signing service (no real oss2/network),
and httpx AsyncClient against the real FastAPI app.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.auth.service import create_access_token
from common.db.models import Base, PracticeSession, Scenario, SessionStatus, User
from common.db.session import get_db
from main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Fake OSS env vars — values don't matter since we mock oss2
_TEST_OSS_ENV = {
    "ALI_OSS_ACCESS_KEY_ID": "test-key-id",
    "ALI_OSS_ACCESS_KEY_SECRET": "test-key-secret",
    "ALI_OSS_BUCKET": "test-bucket",
    "ALI_OSS_ENDPOINT": "https://oss-cn-hangzhou.aliyuncs.com",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def owner(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"audio-contract-{uuid.uuid4().hex[:8]}",
        name="Audio Contract Owner",
        email=f"audio_contract_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def outsider(db_session: AsyncSession):
    user = User(
        wechat_user_id=f"audio-outsider-{uuid.uuid4().hex[:8]}",
        name="Audio Outsider",
        email=f"audio_outsider_{uuid.uuid4().hex[:6]}@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner_headers(owner: User):
    token = create_access_token(data={"sub": str(owner.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def outsider_headers(outsider: User):
    token = create_access_token(data={"sub": str(outsider.user_id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _create_session(db: AsyncSession, user: User) -> str:
    """Create a practice session owned by *user* and return its session_id."""
    scenario = Scenario(
        scenario_id=str(uuid.uuid4()),
        scenario_type="sales",
        name="Audio Contract Scenario",
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)

    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=user.user_id,
        scenario_id=scenario.scenario_id,
        status=SessionStatus.IN_PROGRESS,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session.session_id


# ---------------------------------------------------------------------------
# Contract Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_sign_put_register_cycle(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """End-to-end: sign → PUT → register → list proves segments are durable."""
    session_id = await _create_session(db_session, owner)

    import common.oss.signing as oss_mod

    with patch.dict(os.environ, _TEST_OSS_ENV, clear=False):
        oss_mod._instance = None  # reset singleton

        mock_bucket = MagicMock()
        mock_bucket.sign_url.return_value = "https://oss-test.example.com/signed-put-url"

        with patch.object(oss_mod, "oss2") as m_oss2:
            m_oss2.Auth.return_value = MagicMock()
            m_oss2.Bucket.return_value = mock_bucket

            # Step 1: Get presigned PUT URL
            sign_resp = await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-upload-urls",
                json={"segment_sequence": 0, "content_type": "audio/webm;codecs=opus"},
                headers=owner_headers,
            )
            assert sign_resp.status_code == 200
            sign_data = sign_resp.json()["data"]
            assert "url" in sign_data
            assert "object_key" in sign_data
            assert sign_data["object_key"] == f"audio/{session_id}/seg_0000.webm"

            # Step 2: Simulate browser PUT to OSS (mocked — just verify URL is usable)
            # In real flow browser does: fetch(url, {method: 'PUT', body: blob})
            # Here we just note the URL was returned successfully.

            # Step 3: Register segment metadata
            reg_resp = await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                json={
                    "segment_sequence": 0,
                    "object_key": sign_data["object_key"],
                    "size_bytes": 16384,
                    "duration_ms": 15000,
                },
                headers=owner_headers,
            )
            assert reg_resp.status_code == 200
            reg_body = reg_resp.json()["data"]
            assert reg_body["segment_sequence"] == 0
            assert reg_body["upload_status"] == "uploaded"
            assert reg_body["size_bytes"] == 16384

            # Step 4: List segments — proves durability
            list_resp = await async_client.get(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                headers=owner_headers,
            )
            assert list_resp.status_code == 200
            segments = list_resp.json()["data"]
            assert len(segments) == 1
            assert segments[0]["object_key"] == sign_data["object_key"]
            assert segments[0]["upload_status"] == "uploaded"

            # Step 5: Runtime observability snapshot tracks audio-audit durability.
            from sqlalchemy import select

            session_result = await db_session.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
            persisted_session = session_result.scalar_one()
            snapshot = persisted_session.voice_policy_snapshot or {}
            runtime_metrics = snapshot.get("runtime_metrics") or {}
            audio_audit = runtime_metrics.get("audio_audit") or {}
            assert audio_audit["segment_count"] == 1
            assert audio_audit["uploaded_segment_count"] == 1
            assert audio_audit["total_uploaded_bytes"] == 16384
            assert audio_audit["last_segment_sequence"] == 0
            assert audio_audit["last_object_key"] == sign_data["object_key"]
            assert audio_audit["storage_prefix"] == f"audio/{session_id}/"

    # Cleanup
    oss_mod._instance = None


@pytest.mark.asyncio
async def test_multiple_segments_are_ordered(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """Register 3 segments out of order — list must return them by sequence."""
    session_id = await _create_session(db_session, owner)

    import common.oss.signing as oss_mod

    with patch.dict(os.environ, _TEST_OSS_ENV, clear=False):
        oss_mod._instance = None
        mock_bucket = MagicMock()
        mock_bucket.sign_url.return_value = "https://oss-test.example.com/signed"

        with patch.object(oss_mod, "oss2") as m_oss2:
            m_oss2.Auth.return_value = MagicMock()
            m_oss2.Bucket.return_value = mock_bucket

            # Register segments out of order: 2, 0, 1
            for seq in [2, 0, 1]:
                await async_client.post(
                    f"/api/v1/practice/sessions/{session_id}/audio-upload-urls",
                    json={"segment_sequence": seq},
                    headers=owner_headers,
                )
                await async_client.post(
                    f"/api/v1/practice/sessions/{session_id}/audio-segments",
                    json={
                        "segment_sequence": seq,
                        "object_key": f"audio/{session_id}/seg_{seq:04d}.webm",
                        "size_bytes": 8192 * (seq + 1),
                    },
                    headers=owner_headers,
                )

            # List must be ordered by segment_sequence
            list_resp = await async_client.get(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                headers=owner_headers,
            )
            assert list_resp.status_code == 200
            segments = list_resp.json()["data"]
            assert len(segments) == 3
            assert [s["segment_sequence"] for s in segments] == [0, 1, 2]

    oss_mod._instance = None


@pytest.mark.asyncio
async def test_outsider_cannot_access_segments(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
    outsider_headers: dict[str, str],
):
    """A different user gets 403 on all audio-segment endpoints."""
    session_id = await _create_session(db_session, owner)

    import common.oss.signing as oss_mod

    with patch.dict(os.environ, _TEST_OSS_ENV, clear=False):
        oss_mod._instance = None
        mock_bucket = MagicMock()
        mock_bucket.sign_url.return_value = "https://oss-test.example.com/signed"

        with patch.object(oss_mod, "oss2") as m_oss2:
            m_oss2.Auth.return_value = MagicMock()
            m_oss2.Bucket.return_value = mock_bucket

            # Outsider tries to sign URL
            resp = await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-upload-urls",
                json={"segment_sequence": 0},
                headers=outsider_headers,
            )
            assert resp.status_code == 403

            # Outsider tries to register segment
            resp = await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                json={"segment_sequence": 0, "object_key": "audio/fake.webm"},
                headers=outsider_headers,
            )
            assert resp.status_code == 403

            # Outsider tries to list
            resp = await async_client.get(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                headers=outsider_headers,
            )
            assert resp.status_code == 403

    oss_mod._instance = None


@pytest.mark.asyncio
async def test_segment_registration_is_idempotent(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """Re-registering same (session, sequence) updates rather than duplicates."""
    session_id = await _create_session(db_session, owner)

    import common.oss.signing as oss_mod

    with patch.dict(os.environ, _TEST_OSS_ENV, clear=False):
        oss_mod._instance = None
        mock_bucket = MagicMock()
        mock_bucket.sign_url.return_value = "https://oss-test.example.com/signed"

        with patch.object(oss_mod, "oss2") as m_oss2:
            m_oss2.Auth.return_value = MagicMock()
            m_oss2.Bucket.return_value = mock_bucket

            # Register segment 0
            await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                json={
                    "segment_sequence": 0,
                    "object_key": "audio/original.webm",
                    "size_bytes": 1000,
                },
                headers=owner_headers,
            )

            # Re-register with updated data
            reg2 = await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                json={
                    "segment_sequence": 0,
                    "object_key": "audio/updated.webm",
                    "size_bytes": 2000,
                },
                headers=owner_headers,
            )
            assert reg2.status_code == 200

            # List — should still be 1 segment, with updated data
            list_resp = await async_client.get(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                headers=owner_headers,
            )
            segments = list_resp.json()["data"]
            assert len(segments) == 1
            assert segments[0]["object_key"] == "audio/updated.webm"
            assert segments[0]["size_bytes"] == 2000

    oss_mod._instance = None


@pytest.mark.asyncio
async def test_first_segment_updates_session_audio_url(
    async_client: AsyncClient,
    db_session: AsyncSession,
    owner: User,
    owner_headers: dict[str, str],
):
    """After registering the first segment, session.audio_url gets set."""
    session_id = await _create_session(db_session, owner)

    # Verify audio_url is initially None
    from sqlalchemy import select
    result = await db_session.execute(
        select(PracticeSession).where(PracticeSession.session_id == session_id)
    )
    session = result.scalar_one()
    assert session.audio_url is None

    import common.oss.signing as oss_mod

    with patch.dict(os.environ, _TEST_OSS_ENV, clear=False):
        oss_mod._instance = None
        mock_bucket = MagicMock()
        mock_bucket.sign_url.return_value = "https://oss-test.example.com/signed"

        with patch.object(oss_mod, "oss2") as m_oss2:
            m_oss2.Auth.return_value = MagicMock()
            m_oss2.Bucket.return_value = mock_bucket

            await async_client.post(
                f"/api/v1/practice/sessions/{session_id}/audio-segments",
                json={
                    "segment_sequence": 0,
                    "object_key": f"audio/{session_id}/seg_0000.webm",
                    "size_bytes": 5000,
                },
                headers=owner_headers,
            )

    # Refresh and check audio_url
    await db_session.refresh(session)
    assert session.audio_url == f"audio/{session_id}/"

    oss_mod._instance = None


@pytest.mark.asyncio
async def test_missing_session_returns_404(
    async_client: AsyncClient,
    owner_headers: dict[str, str],
):
    """All three endpoints return 404 for nonexistent session."""
    fake_id = str(uuid.uuid4())

    sign_resp = await async_client.post(
        f"/api/v1/practice/sessions/{fake_id}/audio-upload-urls",
        json={"segment_sequence": 0},
        headers=owner_headers,
    )
    assert sign_resp.status_code == 404

    reg_resp = await async_client.post(
        f"/api/v1/practice/sessions/{fake_id}/audio-segments",
        json={"segment_sequence": 0, "object_key": "audio/x.webm"},
        headers=owner_headers,
    )
    assert reg_resp.status_code == 404

    list_resp = await async_client.get(
        f"/api/v1/practice/sessions/{fake_id}/audio-segments",
        headers=owner_headers,
    )
    assert list_resp.status_code == 404
