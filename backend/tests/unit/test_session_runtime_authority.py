from __future__ import annotations

from unittest.mock import Mock

import pytest

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


@pytest.mark.asyncio
async def test_session_manager_stats_expose_process_local_connection_authority() -> None:
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
async def test_session_state_service_stats_expose_snapshot_authority_and_operation_metrics() -> None:
    service = SessionStateService(state_ttl=600, cleanup_interval=30, key_prefix="ws:test:")
    service._redis = _FakeRedis()
    service._running = True

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
    }
    assert stats["last_saved_session_id"] == "session-snapshot-001"
    assert stats["last_loaded_session_id"] == "session-snapshot-001"
    assert stats["last_deleted_session_id"] == "session-snapshot-001"
    assert stats["last_error"] is None
