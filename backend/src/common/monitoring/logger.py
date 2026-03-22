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


class StructuredLogger:
    """Structured logger with trace_id support"""

    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg, trace_id=get_trace_id(), **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg, trace_id=get_trace_id(), **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(msg, trace_id=get_trace_id(), **kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg, trace_id=get_trace_id(), **kwargs)


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
