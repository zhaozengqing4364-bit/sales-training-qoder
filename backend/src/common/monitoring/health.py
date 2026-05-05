from __future__ import annotations

from datetime import UTC, datetime


def build_health_payload(
    *,
    observed_at: datetime | None = None,
    checks: dict[str, str] | None = None,
) -> dict[str, object]:
    timestamp = observed_at or datetime.now(UTC)
    resolved_checks = {"http": "ok"} | (checks or {})
    ready = all(status == "ok" for status in resolved_checks.values())

    return {
        "service": "sales-training-backend",
        "status": "healthy" if ready else "unhealthy",
        "ready": ready,
        "readiness": "ready" if ready else "not_ready",
        "api_base_path": "/api/v1",
        "checks": resolved_checks,
        "timestamp": timestamp.isoformat(),
        "version": "1.0.0",
    }
