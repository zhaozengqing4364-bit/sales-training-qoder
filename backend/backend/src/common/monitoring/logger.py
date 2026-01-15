"""
Structured Logging Configuration
Provides structured logging with trace_id support for distributed tracing
"""
import logging
import os
import sys
from contextvars import ContextVar

# Context variable for trace_id (Constitution Principle VII)
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Ensure log directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Simple formatter for development
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(trace_id)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(f"{log_dir}/app.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.FileHandler(f"{log_dir}/error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_trace_id(trace_id: str) -> None:
    """
    Set trace_id in context for the current request

    Args:
        trace_id: Unique trace identifier
    """
    trace_id_ctx.set(trace_id)


def get_trace_id() -> str:
    """
    Get the current trace_id from context

    Returns:
        Current trace_id or empty string if not set
    """
    return trace_id_ctx.get()
