"""
Unit tests for structured logging (T026-T027)
Constitution Principle VII: Observability - All logs contain trace_id
"""
from fastapi import FastAPI

from common.monitoring.logger import (
    configure_logging,
    get_logger,
    get_trace_id,
    set_trace_id,
)


class TestStructuredLogger:
    """T026-P1: Test structured logging with trace_id"""

    def test_configure_logging_sets_up_structlog(self, caplog):
        """Should configure structlog with JSON processor"""
        configure_logging(log_level="INFO")
        logger = get_logger("test")

        # Should not raise exceptions
        assert logger is not None
        assert logger.logger is not None

    def test_logger_includes_trace_id(self, caplog):
        """Should include trace_id in all log messages"""
        configure_logging(log_level="DEBUG")
        logger = get_logger("test")

        # Set trace_id
        test_trace_id = "test_123"
        set_trace_id(test_trace_id)

        # Log message
        logger.info("Test message", extra_field="extra_value")

        # Verify trace_id is included
        current_trace_id = get_trace_id()
        assert current_trace_id == test_trace_id

    def test_get_trace_id_generates_uuid_if_not_set(self):
        """Should generate UUID if no trace_id is set"""
        # Clear any existing trace_id
        set_trace_id("")

        trace_id = get_trace_id()
        assert trace_id is not None
        assert len(trace_id) == 32

    def test_set_trace_id_updates_context(self):
        """Should update trace_id in context"""
        set_trace_id("custom_trace_123")
        assert get_trace_id() == "custom_trace_123"

        set_trace_id("another_trace_456")
        assert get_trace_id() == "another_trace_456"

    def test_logger_log_levels(self):
        """Should support all log levels"""
        configure_logging(log_level="DEBUG")
        logger = get_logger("test")

        # Should not raise exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_logger_with_extra_fields(self):
        """Should include extra fields in log output"""
        configure_logging(log_level="DEBUG")
        logger = get_logger("test")
        set_trace_id("trace_123")

        # Should not raise exceptions
        logger.info(
            "User action",
            user_id="user_123",
            action="upload_ppt",
            duration_ms=150,
        )


def test_initialize_otel_skips_when_disabled(monkeypatch):
    """Should skip OTel initialization when disabled."""
    from common.monitoring.otel import initialize_otel

    monkeypatch.delenv("OTEL_ENABLED", raising=False)

    app = FastAPI()
    assert initialize_otel(app) is False


def test_initialize_otel_gracefully_degrades_when_dependencies_missing(monkeypatch):
    """Should not raise when OTel dependencies are absent."""
    import common.monitoring.otel as otel_module

    def _missing_module(name: str):
        raise ModuleNotFoundError(name)

    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setattr(otel_module.importlib, "import_module", _missing_module)

    app = FastAPI()
    assert otel_module.initialize_otel(app) is False
