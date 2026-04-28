"""
Unit tests for admin users API request models and audit helpers.
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql, sqlite

from admin.api.users import (
    CreateUserRequest,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    _active_admin_recount_statement,
    _assert_role_transition_allowed,
    _dialect_supports_row_locks,
    _mask_email,
    _user_audit_snapshot,
)
from common.db.models import User
from common.monitoring.log_safety_inventory import (
    FIX_FIRST_SENSITIVE_LOG_SURFACES,
    SENSITIVE_LOG_POSITIVE_CONTROL,
    SENSITIVE_LOG_SURFACES,
)
from common.monitoring.logger import (
    REDACTED_VALUE,
    StructuredLogger,
    sanitize_log_kwargs,
    set_trace_id,
)

WATCH_SENSITIVE_LOG_SURFACES = {
    "common.monitoring.logger.StructuredLogger",
    "common.monitoring.latency_tracker.record_stage",
    "common.auth.api.logout",
    "common.auth.api.login/forgot/reset failure branches",
    "common.auth.service.verify_token",
}


def test_create_user_request_rejects_invalid_role() -> None:
    """Create request should reject unsupported role values."""
    try:
        CreateUserRequest(
            username="tester",
            email="tester@example.com",
            password="Password123",
            role="super-admin",
        )
    except ValidationError as exc:
        assert "角色仅支持 user、support 或 admin" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for invalid role")


def test_create_user_request_rejects_too_long_audit_reason() -> None:
    """Create request should reject overly long audit reason."""
    long_reason = "a" * 501
    try:
        CreateUserRequest(
            username="tester",
            email="tester@example.com",
            password="Password123",
            role="user",
            audit_reason=long_reason,
        )
    except ValidationError as exc:
        assert "审计原因不能超过500个字符" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for too long audit_reason")


def test_update_user_request_accepts_valid_role_and_reason() -> None:
    """Update request should accept supported role and trimmed reason."""
    request = UpdateUserRequest(role="admin", audit_reason="  role escalation approved  ")

    assert request.role == "admin"
    assert request.audit_reason == "role escalation approved"


def test_create_user_request_accepts_support_role() -> None:
    """Create request should accept support role."""
    request = CreateUserRequest(
        username="support_tester",
        email="support.tester@example.com",
        password="Password123",
        role="support",
    )

    assert request.role == "support"


def test_update_user_request_accepts_support_role() -> None:
    """Update request should accept support role."""
    request = UpdateUserRequest(role="support")

    assert request.role == "support"


def test_update_user_role_request_normalizes_role_and_reason() -> None:
    """Role update request should normalize role and trim reason."""
    request = UpdateUserRoleRequest(
        role="  ADMIN  ",
        audit_reason="  emergency access granted  ",
    )

    assert request.role == "admin"
    assert request.audit_reason == "emergency access granted"


def test_update_user_role_request_rejects_blank_role() -> None:
    """Role update request should reject blank role values."""
    try:
        UpdateUserRoleRequest(role="   ")
    except ValidationError as exc:
        assert "角色不能为空" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for blank role")


def test_mask_email_masks_local_part() -> None:
    """Email masking should keep domain while hiding local-part details."""
    masked = _mask_email("abcdef@example.com")

    assert masked == "ab***@example.com"


def test_user_audit_snapshot_masks_sensitive_email() -> None:
    """Audit snapshot should include masked email and core user fields."""
    user = User(
        user_id="test-user-id",
        wechat_user_id="wechat_test_user",
        name="Tester",
        department="QA",
        email="sensitive@example.com",
        role="user",
        is_active=True,
    )

    snapshot = _user_audit_snapshot(user)

    assert snapshot["user_id"] == "test-user-id"
    assert snapshot["email"] == "se***@example.com"
    assert snapshot["role"] == "user"
    assert snapshot["is_active"] is True


def test_role_transition_guard_rejects_removing_last_active_admin() -> None:
    """Static guardrail should reject self downgrade before recounting admins."""
    with pytest.raises(HTTPException) as exc_info:
        _assert_role_transition_allowed(
            is_self=True,
            current_role="admin",
            new_role="user",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "[CANNOT_DOWNGRADE_SELF]"


def test_active_admin_recount_statement_requests_row_lock_for_supported_dialects() -> None:
    """Transaction-local recount should request row locks when SQL supports them."""
    statement = _active_admin_recount_statement(lock_rows=True)

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert _dialect_supports_row_locks("postgresql")
    assert "FOR UPDATE" in compiled


def test_active_admin_recount_statement_documents_sqlite_row_lock_limitation() -> None:
    """SQLite cannot serialize the recount with SELECT FOR UPDATE."""
    statement = _active_admin_recount_statement(lock_rows=False)

    compiled = str(statement.compile(dialect=sqlite.dialect()))

    assert not _dialect_supports_row_locks("sqlite")
    assert "FOR UPDATE" not in compiled


class _RecordingBoundLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def info(self, msg: str, **kwargs: object) -> None:
        self.calls.append((msg, kwargs))


def test_structured_logger_masks_sensitive_fields_before_sink_emission() -> None:
    """Shared logger should redact secrets at the sink boundary, not only in helper tests."""
    recorder = _RecordingBoundLogger()
    logger = StructuredLogger.__new__(StructuredLogger)
    logger.logger = recorder

    try:
        set_trace_id("trace-security-baseline")
        logger.info(
            "auth_event",
            user_email="sensitive@example.com",
            access_token="secret-token",
            safe_value="kept",
            extra={
                "reset_token": "abc123",
                "request_cookie": "session=1",
                "notes": "keep me",
            },
        )
    finally:
        set_trace_id("")

    assert recorder.calls == [
        (
            "auth_event",
            {
                "trace_id": "trace-security-baseline",
                "user_email": "se***@example.com",
                "access_token": REDACTED_VALUE,
                "safe_value": "kept",
                "extra": {
                    "reset_token": REDACTED_VALUE,
                    "request_cookie": REDACTED_VALUE,
                    "notes": "keep me",
                },
            },
        )
    ]


def test_sensitive_log_security_baseline_inventory_is_closed_and_scoped() -> None:
    """Security baseline inventory should show the fixed scope and the deferred watch list."""
    watch_surfaces = {
        surface.surface
        for surface in SENSITIVE_LOG_SURFACES
        if surface.priority == "watch"
    }
    baseline_surfaces = {
        surface.surface
        for surface in SENSITIVE_LOG_SURFACES
        if surface.priority == "baseline"
    }

    assert FIX_FIRST_SENSITIVE_LOG_SURFACES == ()
    assert watch_surfaces == WATCH_SENSITIVE_LOG_SURFACES
    assert baseline_surfaces == {SENSITIVE_LOG_POSITIVE_CONTROL}
    assert watch_surfaces.isdisjoint(baseline_surfaces)
    assert all(surface.redaction_state == "present" for surface in SENSITIVE_LOG_SURFACES)
    assert all(surface.sensitive_fields for surface in SENSITIVE_LOG_SURFACES)


def test_sanitize_log_kwargs_redacts_sensitive_top_level_fields() -> None:
    """Shared logger should redact token/password/cookie/email keys."""
    sanitized = sanitize_log_kwargs(
        {
            "user_email": "sensitive@example.com",
            "access_token": "secret-token",
            "session_cookie": "session=abc",
            "password": "Password123",
            "safe_value": "kept",
        }
    )

    assert sanitized["user_email"] == "se***@example.com"
    assert sanitized["access_token"] == REDACTED_VALUE
    assert sanitized["session_cookie"] == REDACTED_VALUE
    assert sanitized["password"] == REDACTED_VALUE
    assert sanitized["safe_value"] == "kept"


def test_sanitize_log_kwargs_redacts_nested_extra_metadata() -> None:
    """Shared logger should sanitize nested extra payloads before emission."""
    sanitized = sanitize_log_kwargs(
        {
            "extra": {
                "operator_email": "operator@example.com",
                "request": {
                    "reset_token": "abc123",
                    "notes": "keep me",
                },
                "events": [
                    {"cookie_value": "session=1"},
                    {"password_hint": "do not leak"},
                    {"non_sensitive": "visible"},
                ],
            }
        }
    )

    assert sanitized["extra"]["operator_email"] == "op***@example.com"
    assert sanitized["extra"]["request"]["reset_token"] == REDACTED_VALUE
    assert sanitized["extra"]["request"]["notes"] == "keep me"
    assert sanitized["extra"]["events"][0]["cookie_value"] == REDACTED_VALUE
    assert sanitized["extra"]["events"][1]["password_hint"] == REDACTED_VALUE
    assert sanitized["extra"]["events"][2]["non_sensitive"] == "visible"
