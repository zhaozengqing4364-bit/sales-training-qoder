"""OpenTelemetry initialization with graceful degradation."""

from __future__ import annotations

import importlib
import os
from typing import Any

from fastapi import FastAPI

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def _is_enabled() -> bool:
    value = os.getenv("OTEL_ENABLED", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def initialize_otel(app: FastAPI | None = None) -> bool:
    """Initialize backend OTel tracing when dependencies are available.

    Returns `True` when instrumentation is active. Missing dependencies or any
    startup error are downgraded to warnings so local development remains
    functional.
    """

    if not _is_enabled():
        logger.info("OpenTelemetry disabled")
        return False

    try:
        trace_api = importlib.import_module("opentelemetry.trace")
        resources_module = importlib.import_module("opentelemetry.sdk.resources")
        trace_sdk_module = importlib.import_module("opentelemetry.sdk.trace")
        trace_export_module = importlib.import_module(
            "opentelemetry.sdk.trace.export"
        )
        otlp_module = importlib.import_module(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter"
        )
        fastapi_instrumentation_module = importlib.import_module(
            "opentelemetry.instrumentation.fastapi"
        )
    except ModuleNotFoundError as exc:
        logger.warning(
            "OpenTelemetry dependencies missing; tracing disabled",
            missing_dependency=str(exc),
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "OpenTelemetry import failed; tracing disabled",
            error=str(exc),
        )
        return False

    try:
        resource = resources_module.Resource.create(
            {
                "service.name": os.getenv(
                    "OTEL_SERVICE_NAME", "ai-practice-backend"
                ),
                "service.version": os.getenv("APP_VERSION", "unknown"),
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            }
        )
        provider = trace_sdk_module.TracerProvider(resource=resource)
        exporter_kwargs: dict[str, Any] = {}
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        if endpoint:
            exporter_kwargs["endpoint"] = endpoint
        exporter = otlp_module.OTLPSpanExporter(**exporter_kwargs)
        processor = trace_export_module.BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace_api.set_tracer_provider(provider)

        if app is not None:
            if getattr(app.state, "otel_instrumented", False):
                return True
            fastapi_instrumentation_module.FastAPIInstrumentor.instrument_app(app)
            app.state.otel_instrumented = True

        logger.info("OpenTelemetry initialized")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "OpenTelemetry initialization failed; tracing disabled",
            error=str(exc),
        )
        return False
