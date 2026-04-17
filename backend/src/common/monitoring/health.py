from __future__ import annotations

from datetime import UTC, datetime


def build_health_payload(*, observed_at: datetime | None = None) -> dict[str, object]:
    timestamp = observed_at or datetime.now(UTC)

    return {
        "service": "sales-training-backend",
        "status": "healthy",
        "ready": True,
        "readiness": "ready",
        "api_base_path": "/api/v1",
        "checks": {"http": "ok"},
        "timestamp": timestamp.isoformat(),
        "version": "1.0.0",
    }
