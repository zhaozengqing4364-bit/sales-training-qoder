"""Sensitive-log inventory for M016/S03.

The goal is to keep one code-owned list of sinks that can expose token/password/
cookie/email fields, plus one known-good masked example for future fixes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SurfaceRisk = Literal["high", "medium", "baseline"]
RedactionState = Literal["missing", "partial", "present"]
PriorityClass = Literal["fix-first", "watch", "baseline"]


@dataclass(frozen=True)
class SensitiveLogSurface:
    """One logging or audit surface that touches sensitive auth/user fields."""

    surface: str
    file_path: str
    sink: str
    sensitive_fields: tuple[str, ...]
    redaction_state: RedactionState
    risk: SurfaceRisk
    priority: PriorityClass
    current_evidence: tuple[str, ...]
    rationale: str


SENSITIVE_LOG_SURFACES: tuple[SensitiveLogSurface, ...] = (
    SensitiveLogSurface(
        surface="common.monitoring.logger.StructuredLogger",
        file_path="backend/src/common/monitoring/logger.py",
        sink="StructuredLogger.info/warning/error/debug -> structlog.get_logger(...).*(**kwargs)",
        sensitive_fields=("token", "password", "cookie", "email"),
        redaction_state="missing",
        risk="high",
        priority="fix-first",
        current_evidence=(
            "StructuredLogger forwards caller kwargs directly without a shared sanitizer",
            "All application code that passes structured fields inherits this sink",
        ),
        rationale="This is the shared logging boundary. If redaction is added only at call sites, drift is inevitable.",
    ),
    SensitiveLogSurface(
        surface="common.monitoring.latency_tracker.record_stage",
        file_path="backend/src/common/monitoring/latency_tracker.py",
        sink="logger.info(..., **metadata)",
        sensitive_fields=("token", "password", "cookie", "email"),
        redaction_state="missing",
        risk="high",
        priority="fix-first",
        current_evidence=(
            "record_stage() forwards arbitrary metadata into the shared logger",
            "No field allowlist or redaction boundary exists before emission",
        ),
        rationale="Latency metadata is caller-defined, so one mistaken auth payload can leak directly into logs.",
    ),
    SensitiveLogSurface(
        surface="common.auth.api.logout",
        file_path="backend/src/common/auth/api.py",
        sink='logger.info(f"User logged out: {current_user.email}")',
        sensitive_fields=("email",),
        redaction_state="missing",
        risk="high",
        priority="fix-first",
        current_evidence=(
            "Logout success path logs the raw user email today",
            "No masking helper is applied on this auth boundary",
        ),
        rationale="This is a deterministic raw-email emission on a user-visible auth path.",
    ),
    SensitiveLogSurface(
        surface="common.auth.api.login/forgot/reset failure branches",
        file_path="backend/src/common/auth/api.py",
        sink='logger.error(f"... {str(e)}")',
        sensitive_fields=("email", "password", "token"),
        redaction_state="partial",
        risk="high",
        priority="fix-first",
        current_evidence=(
            "Auth request bodies carry email/password/reset-token fields",
            "Failure logs stringify exceptions instead of applying a field-safe envelope",
        ),
        rationale="Even when the current exceptions are usually generic, the sink is still coupled to credential-bearing request paths.",
    ),
    SensitiveLogSurface(
        surface="common.auth.service.verify_token",
        file_path="backend/src/common/auth/service.py",
        sink='logger.warning(f"Token verification failed: {str(e)}")',
        sensitive_fields=("token",),
        redaction_state="partial",
        risk="medium",
        priority="watch",
        current_evidence=(
            "Current JWT errors normally omit token bytes",
            "The warning still stringifies auth exceptions on the token-verification boundary",
        ),
        rationale="Lower risk than the shared sink, but still worth aligning once shared redaction lands.",
    ),
    SensitiveLogSurface(
        surface="admin.api.users._queue_user_audit_log",
        file_path="backend/src/admin/api/users.py",
        sink="SystemLog.details JSON + operator_email_masked field",
        sensitive_fields=("email",),
        redaction_state="present",
        risk="baseline",
        priority="baseline",
        current_evidence=(
            "_mask_email() redacts the local-part before persistence",
            "backend/tests/unit/admin/test_admin_users_api_models.py::test_user_audit_snapshot_masks_sensitive_email",
            "backend/tests/integration/test_admin_users_api.py::test_admin_user_lifecycle_and_audit_log_fields",
        ),
        rationale="This is the current positive-control pattern for logging user-affecting admin actions without exposing raw email.",
    ),
)


FIX_FIRST_SENSITIVE_LOG_SURFACES: tuple[str, ...] = tuple(
    surface.surface
    for surface in SENSITIVE_LOG_SURFACES
    if surface.priority == "fix-first"
)


SENSITIVE_LOG_POSITIVE_CONTROL: str = "admin.api.users._queue_user_audit_log"


__all__ = [
    "SensitiveLogSurface",
    "FIX_FIRST_SENSITIVE_LOG_SURFACES",
    "SENSITIVE_LOG_POSITIVE_CONTROL",
    "SENSITIVE_LOG_SURFACES",
]
