from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI

import common.websocket.session_state_service as session_state_module
from common.error_handling.result import Result
from common.websocket.session_manager import SessionManager
from common.websocket.session_state_service import (
    SessionStateService,
    SessionStateSnapshot,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def ping(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


class _FailingRedis(_FakeRedis):
    async def ping(self) -> None:
        raise OSError("redis unavailable")


class _FakeRedisModule:
    def __init__(self, client: _FakeRedis) -> None:
        self.client = client

    def from_url(self, *_args: object, **_kwargs: object) -> _FakeRedis:
        return self.client


@pytest.mark.asyncio
async def test_session_manager_stats_expose_process_local_connection_authority() -> (
    None
):
    manager = SessionManager(timeout_seconds=120, heartbeat_interval=15)

    await manager.register_session("session-a", Mock(), user_id="user-a")

    stats = manager.get_stats()

    assert stats["total_sessions"] == 1
    assert stats["authority"] == {
        "connection_registry": {
            "owner": "session_manager.sessions",
            "storage": "process_memory",
            "shared_across_instances": False,
            "survives_restart": False,
            "inspection_surface": "SessionManager.get_stats()",
        },
        "session_snapshot": {
            "owner": "session_state_service",
            "storage": "redis_snapshot",
            "shared_across_instances": True,
            "survives_restart": True,
        },
    }
    assert len(stats["tracked_sessions"]) == 1
    tracked = stats["tracked_sessions"][0]
    assert tracked["session_id"] == "session-a"
    assert tracked["user_id"] == "user-a"
    assert tracked["connected_at"] >= 0
    assert tracked["last_activity_at"] >= 0
    assert tracked["session_age_seconds"] >= 0
    assert tracked["inactive_seconds"] >= 0


@pytest.mark.asyncio
async def test_session_state_service_stats_expose_snapshot_authority_and_operation_metrics() -> (
    None
):
    service = SessionStateService(
        state_ttl=600, cleanup_interval=30, key_prefix="ws:test:"
    )
    service._redis = _FakeRedis()
    service._running = True
    service._health_status = "ok"

    snapshot = SessionStateSnapshot(
        session_id="session-snapshot-001",
        scenario="sales",
        turn_count=2,
        session_status="in_progress",
        ai_state="listening",
        runtime_state={"current_request_id": 2},
        user_id="user-123",
    )

    save_result = await service.save_state(snapshot)
    get_result = await service.get_state("session-snapshot-001")
    missing_result = await service.get_state("missing-session")
    delete_result = await service.delete_state("session-snapshot-001")

    assert save_result == Result.ok(None)
    assert get_result.is_success and get_result.value is not None
    assert missing_result.is_success and missing_result.value is None
    assert delete_result == Result.ok(None)

    stats = service.get_stats()

    assert stats["authority"] == {
        "session_snapshot": {
            "owner": "session_state_service",
            "storage": "redis_snapshot",
            "shared_across_instances": True,
            "survives_restart": True,
            "ttl_seconds": 600,
            "inspection_surface": "SessionStateService.get_stats()",
        },
        "runtime_connections": {
            "owner": "session_manager.sessions",
            "storage": "process_memory",
            "shared_across_instances": False,
            "survives_restart": False,
        },
    }
    assert stats["metrics"] == {
        "save_calls": 1,
        "get_calls": 2,
        "get_misses": 1,
        "delete_calls": 1,
        "save_failures": 0,
        "get_failures": 0,
        "delete_failures": 0,
        "healthcheck_failures": 0,
        "disabled_operations": 0,
    }
    assert stats["last_saved_session_id"] == "session-snapshot-001"
    assert stats["last_loaded_session_id"] == "session-snapshot-001"
    assert stats["last_deleted_session_id"] == "session-snapshot-001"
    assert stats["last_error"] is None
    assert stats["health"] == {
        "status": "ok",
        "ready": True,
        "startup_policy": "required",
        "snapshot_enabled": True,
        "redis_connected": True,
        "disabled_reason": None,
        "startup_error": None,
    }


@pytest.mark.asyncio
async def test_session_state_service_required_policy_fails_fast_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SessionStateService(startup_policy="required")
    monkeypatch.setattr(
        session_state_module,
        "_load_redis_module",
        lambda: _FakeRedisModule(_FailingRedis()),
    )

    with pytest.raises(RuntimeError, match="Failed to connect Redis"):
        await service.start()

    health = service.get_health()
    assert health["status"] == "error"
    assert health["ready"] is False
    assert health["snapshot_enabled"] is False
    assert health["startup_error"]["reason"] == "redis_unavailable"


@pytest.mark.asyncio
async def test_session_state_service_optional_policy_degrades_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SessionStateService(startup_policy="optional")
    monkeypatch.setattr(
        session_state_module,
        "_load_redis_module",
        lambda: _FakeRedisModule(_FailingRedis()),
    )

    await service.start()
    result = await service.get_state("session-optional")

    assert result.is_success is False
    assert result.fallback == "[SESSION_STATE_SNAPSHOT_DISABLED]"
    health = service.get_health()
    assert health["status"] == "degraded"
    assert health["ready"] is True
    assert health["snapshot_enabled"] is False
    assert health["disabled_reason"] == "redis_unavailable"
    assert service.get_stats()["metrics"]["disabled_operations"] == 1


@pytest.mark.asyncio
async def test_session_state_service_disabled_policy_skips_redis_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SessionStateService(startup_policy="disabled")
    monkeypatch.setattr(
        session_state_module,
        "_load_redis_module",
        lambda: pytest.fail("disabled policy must not import redis"),
    )

    await service.start()
    result = await service.save_state(
        SessionStateSnapshot(session_id="session-disabled", scenario="sales")
    )

    assert result.is_success is False
    assert result.fallback == "[SESSION_STATE_SNAPSHOT_DISABLED]"
    assert service.get_health() == {
        "status": "disabled",
        "ready": True,
        "startup_policy": "disabled",
        "snapshot_enabled": False,
        "redis_connected": False,
        "disabled_reason": "startup_policy_disabled",
        "startup_error": None,
    }


def test_session_state_service_env_can_disable_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_STATE_SNAPSHOT_ENABLED", "false")

    service = SessionStateService()

    assert service.startup_policy == "disabled"


@pytest.mark.asyncio
async def test_lifespan_exposes_session_state_health_when_snapshots_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app_lifespan as app_lifespan_module
    import common.ai.config_manager as config_manager
    import common.jobs.audio_archival as audio_archival
    import common.websocket.session_manager as session_manager_module
    import common.websocket.session_state_service as session_state_service_module
    from common.config import settings

    class _DisabledSessionStateService:
        snapshot_enabled = False

        def get_health(self) -> dict[str, object]:
            return {
                "status": "disabled",
                "ready": True,
                "startup_policy": "disabled",
                "snapshot_enabled": False,
                "redis_connected": False,
                "disabled_reason": "startup_policy_disabled",
                "startup_error": None,
            }

    async def noop() -> None:
        return None

    async def init_session_state_service() -> _DisabledSessionStateService:
        return _DisabledSessionStateService()

    async def init_audio_archival_scheduler(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "PRELOAD_SERVICES", False)
    monkeypatch.setattr(app_lifespan_module, "initialize_otel", lambda _app: None)
    monkeypatch.setattr(app_lifespan_module, "init_db", noop)
    monkeypatch.setattr(config_manager, "initialize_config_manager", noop)
    monkeypatch.setattr(
        app_lifespan_module,
        "get_auth_config_diagnostics",
        lambda: {
            "credentials_ready": False,
            "user_overrides_valid": True,
            "shared_password_configured": False,
            "user_override_count": 0,
        },
    )
    monkeypatch.setattr(
        app_lifespan_module,
        "get_wecom_provider_diagnostics",
        lambda: {
            "configured": False,
            "corp_id_configured": False,
            "agent_id_configured": False,
        },
    )
    monkeypatch.setattr(session_manager_module, "init_session_manager", noop)
    monkeypatch.setattr(session_manager_module, "shutdown_session_manager", noop)
    monkeypatch.setattr(
        session_state_service_module,
        "init_session_state_service",
        init_session_state_service,
    )
    monkeypatch.setattr(
        session_state_service_module, "shutdown_session_state_service", noop
    )
    monkeypatch.setattr(
        audio_archival,
        "init_audio_archival_scheduler",
        init_audio_archival_scheduler,
    )
    monkeypatch.setattr(audio_archival, "shutdown_audio_archival_scheduler", noop)

    app = FastAPI()
    async with app_lifespan_module.lifespan(app):
        assert app.state.session_state_service_health == {
            "status": "disabled",
            "ready": True,
            "startup_policy": "disabled",
            "snapshot_enabled": False,
            "redis_connected": False,
            "disabled_reason": "startup_policy_disabled",
            "startup_error": None,
        }
