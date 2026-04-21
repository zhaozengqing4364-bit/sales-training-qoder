from __future__ import annotations

from datetime import UTC, datetime


def build_health_payload(
    *,
    observed_at: datetime | None = None,
    checks: dict[str, str] | None = None,
    critical_checks: tuple[str, ...] = ("database",),
) -> dict[str, object]:
    timestamp = observed_at or datetime.now(UTC)
    normalized_checks = {"http": "ok", **(checks or {})}
    failed_critical_checks = [
        check_name
        for check_name in critical_checks
        if normalized_checks.get(check_name) not in {None, "ok"}
    ]
    ready = not failed_critical_checks

    return {
        "service": "sales-training-backend",
        "status": "healthy" if ready else "degraded",
        "ready": ready,
        "readiness": "ready" if ready else "not_ready",
        "api_base_path": "/api/v1",
        "checks": normalized_checks,
        "timestamp": timestamp.isoformat(),
        "version": "1.0.0",
    }
