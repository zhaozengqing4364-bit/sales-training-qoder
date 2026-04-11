"""
Structured JSON logging with trace_id
Constitution Principle VII: Observability
"""
import logging
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import structlog

from common.monitoring.trace_context import generate_trace_id

# Context variable for trace_id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

REDACTED_VALUE = "[REDACTED]"
SENSITIVE_LOG_FIELD_MARKERS = ("token", "password", "cookie", "email")


def get_trace_id() -> str:
    """Get current trace_id from context"""
    tid = trace_id_var.get()
    if not tid:
        tid = generate_trace_id()
        trace_id_var.set(tid)
    return tid


def set_trace_id(trace_id: str) -> None:
    """Set trace_id in context"""
    trace_id_var.set(trace_id)


def _normalize_log_key(field_name: str) -> str:
    return field_name.strip().replace("-", "_").lower()


def is_sensitive_log_key(field_name: str | None) -> bool:
    """Return whether a log field should be redacted."""
    if not field_name:
        return False

    normalized = _normalize_log_key(field_name)
    return any(marker in normalized for marker in SENSITIVE_LOG_FIELD_MARKERS)


def mask_email_for_logs(value: Any) -> str:
    """Mask email local-part while preserving the domain for diagnostics."""
    if not isinstance(value, str):
        return REDACTED_VALUE

    cleaned = value.strip()
    if "@" not in cleaned:
        return REDACTED_VALUE

    local_part, domain_part = cleaned.split("@", 1)
    if not local_part:
        return f"***@{domain_part}"

    visible_prefix = local_part[: min(2, len(local_part))]
    return f"{visible_prefix}***@{domain_part}"


def sanitize_log_value(value: Any, *, field_name: str | None = None) -> Any:
    """Recursively sanitize one log value based on its field name."""
    normalized_field = _normalize_log_key(field_name) if field_name else ""
    if field_name and is_sensitive_log_key(field_name):
        if "email" in normalized_field:
            return mask_email_for_logs(value)
        return REDACTED_VALUE

    if isinstance(value, dict):
        return {
            key: sanitize_log_value(item, field_name=str(key))
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [sanitize_log_value(item, field_name=field_name) for item in value]

    if isinstance(value, tuple):
        return tuple(sanitize_log_value(item, field_name=field_name) for item in value)

    if isinstance(value, set):
        return {sanitize_log_value(item, field_name=field_name) for item in value}

    return value


def sanitize_log_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Sanitize structured log kwargs before they reach the shared sink."""
    return {
        key: sanitize_log_value(value, field_name=key)
        for key, value in kwargs.items()
    }


class StructuredLogger:
    """Structured logger with trace_id support"""

    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg, trace_id=get_trace_id(), **sanitize_log_kwargs(kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg, trace_id=get_trace_id(), **sanitize_log_kwargs(kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(msg, trace_id=get_trace_id(), **sanitize_log_kwargs(kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg, trace_id=get_trace_id(), **sanitize_log_kwargs(kwargs))


# Configure structlog
def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application"""
    log_level = log_level.upper()
    log_path = Path("logs/app.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer() if log_level == "DEBUG" else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)
