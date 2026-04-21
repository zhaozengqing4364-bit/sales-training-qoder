from __future__ import annotations

import json
from datetime import UTC, datetime

from admin.api.system_logs import log_to_response
from common.db.models import SystemLog


def test_log_to_response_applies_admin_support_exposure_policy() -> None:
    log = SystemLog(
        log_id="log-1",
        action="admin.user.updated",
        user_identifier="sensitive.user@example.com",
        ip_address="203.0.113.42",
        status="failed",
        details=json.dumps(
            {
                "trace_id": "trace-123",
                "error_code": "USER_UPDATE_FAILED",
                "phase": "persist",
                "session_id": "session-123",
                "target_user_id": "user-456",
                "password": "Password123",
                "reset_token": "secret-reset-token",
                "operator_email": "admin@example.com",
                "ip_address": "203.0.113.42",
            }
        ),
        created_at=datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    )

    response = log_to_response(log)

    assert response.user_identifier == "se***@example.com"
    assert response.ip_address == "203.0.*.*"
    assert response.trace_id == "trace-123"
    assert response.error_code == "USER_UPDATE_FAILED"
    assert response.phase == "persist"
    assert response.session_id == "session-123"
    assert [(item.key, item.value) for item in response.diagnostics] == [
        ("error_code", "USER_UPDATE_FAILED"),
        ("phase", "persist"),
        ("session_id", "session-123"),
        ("target_user_id", "user-456"),
        ("trace_id", "trace-123"),
    ]
    assert response.details == "error_code=USER_UPDATE_FAILED · phase=persist · session_id=session-123 · target_user_id=user-456 · trace_id=trace-123"
    assert "Password123" not in (response.details or "")
    assert "secret-reset-token" not in (response.details or "")
    assert "admin@example.com" not in (response.details or "")
