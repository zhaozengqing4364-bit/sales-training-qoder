"""Unit tests for audio segment API endpoints.

Covers: generate upload URL, register segment, list segments, error cases.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Register all models with Base.metadata — some models (Agent, Persona,
# VoiceRuntimeProfile) are in separate modules and only register their
# tables when imported.
import agent.models  # noqa: F401 — registers Agent, Persona, VoiceRuntimeProfile
from common.db.models import Base, PracticeSession, Scenario, SessionAudioSegment, User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_OSS_ENV = {
    "ALI_OSS_ACCESS_KEY_ID": "test-ak",
    "ALI_OSS_ACCESS_KEY_SECRET": "test-sk",
    "ALI_OSS_BUCKET": "test-bucket",
    "ALI_OSS_ENDPOINT": "oss-cn-hangzhou.aliyuncs.com",
}


@pytest_asyncio.fixture
async def _db():
    """Isolated in-memory DB with tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as sess:
        yield sess
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def _client(_db: AsyncSession):
    """Async HTTP test client wired to the isolated DB."""
    from common.db.session import get_db
    from main import app

    async def _override():
        yield _db

    app.dependency_overrides[get_db] = _override

    # Ensure dev-login works
    os.environ.setdefault("ENVIRONMENT", "development")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def _auth(_client: AsyncClient):
    """Auth headers from dev-login."""
    resp = await _client.post("/api/v1/auth/dev-login")
    assert resp.status_code == 200
    payload = resp.json()
    token = payload.get("access_token") or (payload.get("data") or {}).get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def _user(_db: AsyncSession):
    """Return the dev user (created by dev-login or manually)."""
    from common.auth.service import get_dev_user
    return await get_dev_user(_db)


@pytest_asyncio.fixture
async def _session_id(_db: AsyncSession, _user: User):
    """Create a minimal PracticeSession and return its ID."""
    # Ensure a scenario exists
    result = await _db.execute(select(Scenario))
    scenario = result.scalar_one_or_none()
    if not scenario:
        scenario = Scenario(
            scenario_id=str(uuid.uuid4()),
            scenario_type="sales",
            name="Test Sales",
            description="test",
        )
        _db.add(scenario)
        await _db.commit()
        await _db.refresh(scenario)

    session = PracticeSession(
        session_id=str(uuid.uuid4()),
        user_id=_user.user_id,
        scenario_id=scenario.scenario_id,
        status="in_progress",
    )
    _db.add(session)
    await _db.commit()
    await _db.refresh(session)
    return session.session_id


# ---------------------------------------------------------------------------
# POST /audio-upload-urls
# ---------------------------------------------------------------------------


class TestGenerateUploadUrl:
    @pytest.mark.asyncio
    async def test_success(self, _client, _auth, _session_id):
        with patch.dict(os.environ, _TEST_OSS_ENV, clear=False):
            import common.oss.signing as mod
            mod._instance = None  # reset singleton

            mock_bucket = MagicMock()
            mock_bucket.sign_url.return_value = "https://oss.example.com/signed"

            with patch.object(mod, "oss2") as m_oss2:
                m_oss2.Auth.return_value = MagicMock()
                m_oss2.Bucket.return_value = mock_bucket

                resp = await _client.post(
                    f"/api/v1/practice/sessions/{_session_id}/audio-upload-urls",
                    json={"segment_sequence": 0, "content_type": "audio/webm"},
                    headers=_auth,
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["object_key"] == f"audio/{_session_id}/seg_0000.webm"
                assert data["url"] == "https://oss.example.com/signed"
                assert "expires_at" in data

            mod._instance = None

    @pytest.mark.asyncio
    async def test_session_not_found(self, _client, _auth):
        fake_id = str(uuid.uuid4())
        resp = await _client.post(
            f"/api/v1/practice/sessions/{fake_id}/audio-upload-urls",
            json={"segment_sequence": 0},
            headers=_auth,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_negative_sequence(self, _client, _auth, _session_id):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-upload-urls",
            json={"segment_sequence": -1},
            headers=_auth,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_sequence(self, _client, _auth, _session_id):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-upload-urls",
            json={"content_type": "audio/webm"},
            headers=_auth,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_oss_not_configured(self, _client, _auth, _session_id):
        """When ALI_OSS_* vars are missing → 503."""
        import common.oss.signing as mod
        mod._instance = None

        with patch.dict(os.environ, {}, clear=True):
            # Remove all env vars
            for k in list(os.environ):
                if k.startswith("ALI_OSS_"):
                    del os.environ[k]

            resp = await _client.post(
                f"/api/v1/practice/sessions/{_session_id}/audio-upload-urls",
                json={"segment_sequence": 0},
                headers=_auth,
            )
            assert resp.status_code == 503
            assert "OSS" in resp.json().get("message", "") or "not configured" in resp.json().get("message", "").lower()

        mod._instance = None


# ---------------------------------------------------------------------------
# POST /audio-segments (register)
# ---------------------------------------------------------------------------


class TestRegisterAudioSegment:
    @pytest.mark.asyncio
    async def test_register_new_segment(self, _client, _auth, _session_id, _db):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            json={
                "segment_sequence": 0,
                "object_key": f"audio/{_session_id}/seg_0000.webm",
                "size_bytes": 12345,
                "duration_ms": 5000,
            },
            headers=_auth,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["upload_status"] == "uploaded"
        assert data["segment_sequence"] == 0
        assert data["size_bytes"] == 12345

        # Verify DB row
        result = await _db.execute(
            select(SessionAudioSegment).where(
                SessionAudioSegment.session_id == _session_id,
                SessionAudioSegment.segment_sequence == 0,
            )
        )
        row = result.scalar_one()
        assert row.object_key == f"audio/{_session_id}/seg_0000.webm"

    @pytest.mark.asyncio
    async def test_register_updates_existing(self, _client, _auth, _session_id, _db):
        # First registration
        await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            json={
                "segment_sequence": 1,
                "object_key": f"audio/{_session_id}/seg_0001.webm",
                "size_bytes": 100,
            },
            headers=_auth,
        )
        # Second registration (update)
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            json={
                "segment_sequence": 1,
                "object_key": f"audio/{_session_id}/seg_0001.webm",
                "size_bytes": 200,
                "duration_ms": 3000,
            },
            headers=_auth,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["size_bytes"] == 200
        assert data["duration_ms"] == 3000

    @pytest.mark.asyncio
    async def test_session_audio_url_set(self, _client, _auth, _session_id, _db):
        """First segment registration sets PracticeSession.audio_url."""
        await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            json={
                "segment_sequence": 0,
                "object_key": f"audio/{_session_id}/seg_0000.webm",
            },
            headers=_auth,
        )
        result = await _db.execute(
            select(PracticeSession).where(PracticeSession.session_id == _session_id)
        )
        session = result.scalar_one()
        assert session.audio_url == f"audio/{_session_id}/"

    @pytest.mark.asyncio
    async def test_missing_object_key(self, _client, _auth, _session_id):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            json={"segment_sequence": 0},
            headers=_auth,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_session_not_found(self, _client, _auth):
        fake_id = str(uuid.uuid4())
        resp = await _client.post(
            f"/api/v1/practice/sessions/{fake_id}/audio-segments",
            json={"segment_sequence": 0, "object_key": "audio/x/seg_0000.webm"},
            headers=_auth,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /audio-segments (list)
# ---------------------------------------------------------------------------


class TestListAudioSegments:
    @pytest.mark.asyncio
    async def test_empty_list(self, _client, _auth, _session_id):
        resp = await _client.get(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            headers=_auth,
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_returns_ordered_segments(self, _client, _auth, _session_id):
        # Register two segments
        for seq in [2, 0, 1]:
            await _client.post(
                f"/api/v1/practice/sessions/{_session_id}/audio-segments",
                json={
                    "segment_sequence": seq,
                    "object_key": f"audio/{_session_id}/seg_{seq:04d}.webm",
                },
                headers=_auth,
            )

        resp = await _client.get(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            headers=_auth,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        assert [s["segment_sequence"] for s in data] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_session_not_found(self, _client, _auth):
        fake_id = str(uuid.uuid4())
        resp = await _client.get(
            f"/api/v1/practice/sessions/{fake_id}/audio-segments",
            headers=_auth,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /audio-segments/failure (failure registration)
# ---------------------------------------------------------------------------


class TestRegisterAudioSegmentFailure:
    @pytest.mark.asyncio
    async def test_register_failure_creates_failed_row(self, _client, _auth, _session_id, _db):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={
                "segment_sequence": 0,
                "error_token": "oss_put_failed",
            },
            headers=_auth,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["upload_status"] == "failed"
        assert data["error_message"] == "oss_put_failed"
        assert data["segment_sequence"] == 0

        # Verify DB row
        result = await _db.execute(
            select(SessionAudioSegment).where(
                SessionAudioSegment.session_id == _session_id,
                SessionAudioSegment.segment_sequence == 0,
            )
        )
        row = result.scalar_one()
        assert row.upload_status == "failed"
        assert row.error_message == "oss_put_failed"

    @pytest.mark.asyncio
    async def test_failure_updates_voice_policy_snapshot(self, _client, _auth, _session_id, _db):
        await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "signing_failed"},
            headers=_auth,
        )

        result = await _db.execute(
            select(PracticeSession).where(PracticeSession.session_id == _session_id)
        )
        session = result.scalar_one()
        snapshot = session.voice_policy_snapshot or {}
        audio_audit = snapshot.get("runtime_metrics", {}).get("audio_audit", {})
        assert audio_audit["failed_segment_count"] == 1
        assert audio_audit["last_failure_reason"] == "signing_failed"

    @pytest.mark.asyncio
    async def test_failure_does_not_overwrite_uploaded_segment(self, _client, _auth, _session_id, _db):
        # Register a successful upload first
        await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments",
            json={
                "segment_sequence": 0,
                "object_key": f"audio/{_session_id}/seg_0000.webm",
                "size_bytes": 5000,
            },
            headers=_auth,
        )
        # Try to register failure for the same segment
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "network_error"},
            headers=_auth,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Should remain as uploaded, not overwritten
        assert data["upload_status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_failure_upserts_existing_pending_segment(self, _client, _auth, _session_id, _db):
        # Register failure for segment 0
        await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "network_error"},
            headers=_auth,
        )
        # Register failure again (upsert)
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "oss_put_failed"},
            headers=_auth,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["upload_status"] == "failed"
        assert data["error_message"] == "oss_put_failed"

    @pytest.mark.asyncio
    async def test_invalid_error_token(self, _client, _auth, _session_id):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "bogus_error"},
            headers=_auth,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_error_token(self, _client, _auth, _session_id):
        resp = await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0},
            headers=_auth,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_session_not_found(self, _client, _auth):
        fake_id = str(uuid.uuid4())
        resp = await _client.post(
            f"/api/v1/practice/sessions/{fake_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "unknown"},
            headers=_auth,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_audio_url_set_on_first_failure(self, _client, _auth, _session_id, _db):
        await _client.post(
            f"/api/v1/practice/sessions/{_session_id}/audio-segments/failure",
            json={"segment_sequence": 0, "error_token": "unknown"},
            headers=_auth,
        )
        result = await _db.execute(
            select(PracticeSession).where(PracticeSession.session_id == _session_id)
        )
        session = result.scalar_one()
        assert session.audio_url == f"audio/{_session_id}/"
