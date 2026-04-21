from __future__ import annotations

from datetime import UTC, datetime

from common.monitoring.health import build_health_payload


def test_build_health_payload_exposes_machine_readable_readiness_contract() -> None:
    observed_at = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)

    payload = build_health_payload(observed_at=observed_at)

    assert payload == {
        "service": "sales-training-backend",
        "status": "healthy",
        "ready": True,
        "readiness": "ready",
        "api_base_path": "/api/v1",
        "checks": {"http": "ok"},
        "timestamp": observed_at.isoformat(),
        "version": "1.0.0",
    }


def test_build_health_payload_marks_database_failure_not_ready() -> None:
    observed_at = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)

    payload = build_health_payload(
        observed_at=observed_at,
        checks={"database": "error"},
    )

    assert payload["status"] == "degraded"
    assert payload["ready"] is False
    assert payload["readiness"] == "not_ready"
    assert payload["checks"] == {"http": "ok", "database": "error"}


def test_build_health_payload_keeps_optional_dependency_degraded_but_ready() -> None:
    observed_at = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)

    payload = build_health_payload(
        observed_at=observed_at,
        checks={"redis": "error"},
        critical_checks=("database",),
    )

    assert payload["status"] == "healthy"
    assert payload["ready"] is True
    assert payload["readiness"] == "ready"
    assert payload["checks"] == {"http": "ok", "redis": "error"}
