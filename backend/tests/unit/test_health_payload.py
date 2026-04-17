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
