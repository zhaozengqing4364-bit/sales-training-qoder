"""
Prometheus Metrics Exporter - Exposes application metrics for monitoring

Implements Constitution Principles:
- VII. Observability - All key metrics tracked
"""

import logging
import time

from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_client.exposition import generate_latest

logger = logging.getLogger(__name__)


# Metrics
# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# WebSocket metrics
websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections',
    ['scenario_type']
)

websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total WebSocket messages',
    ['scenario_type', 'direction']
)

websocket_message_duration_seconds = Histogram(
    'websocket_message_duration_seconds',
    'WebSocket message processing latency',
    ['scenario_type', 'message_type']
)

# Business metrics
practice_sessions_total = Counter(
    'practice_sessions_total',
    'Total practice sessions',
    ['scenario_type', 'status']
)

practice_session_duration_seconds = Histogram(
    'practice_session_duration_seconds',
    'Practice session duration',
    ['scenario_type'],
    buckets=[60, 120, 300, 600, 900, 1200, 1800, 2700, 3600]
)

practice_scores = Histogram(
    'practice_scores',
    'Practice session scores',
    ['scenario_type', 'score_type'],
    buckets=[20, 40, 50, 60, 70, 80, 85, 90, 95, 100]
)

# AI service metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['service', 'status']
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request latency',
    ['service'],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60]
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total LLM tokens consumed',
    ['service', 'token_type']
)

asr_requests_total = Counter(
    'asr_requests_total',
    'Total ASR requests',
    ['status']
)

asr_request_duration_seconds = Histogram(
    'asr_request_duration_seconds',
    'ASR request latency',
    buckets=[0.1, 0.2, 0.5, 1, 2, 5]
)

tts_requests_total = Counter(
    'tts_requests_total',
    'Total TTS requests',
    ['status']
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['service', 'error_type']
)

# System metrics
application_info = Info(
    'application',
    'Application information'
)


class MetricsMiddleware:
    """
    FastAPI middleware to track HTTP metrics
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        # Start timer
        start_time = time.time()

        # Process request
        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message['status']
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Record metrics
            duration = time.time() - start_time
            method = scope['method']
            path = scope['path']

            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=path
            ).observe(duration)


def track_practice_session(scenario_type: str, status: str, duration: float, scores: dict):
    """Track practice session metrics"""
    practice_sessions_total.labels(
        scenario_type=scenario_type,
        status=status
    ).inc()

    practice_session_duration_seconds.labels(
        scenario_type=scenario_type
    ).observe(duration)

    # Track individual scores
    for score_type, score_value in scores.items():
        if score_value is not None:
            practice_scores.labels(
                scenario_type=scenario_type,
                score_type=score_type
            ).observe(score_value)


def track_llm_request(service: str, status: str, duration: float, tokens: dict):
    """Track LLM request metrics"""
    llm_requests_total.labels(
        service=service,
        status=status
    ).inc()

    llm_request_duration_seconds.labels(
        service=service
    ).observe(duration)

    for token_type, token_count in tokens.items():
        llm_tokens_total.labels(
            service=service,
            token_type=token_type
        ).inc(token_count)


def track_asr_request(status: str, duration: float):
    """Track ASR request metrics"""
    asr_requests_total.labels(status=status).inc()
    asr_request_duration_seconds.observe(duration)


def track_websocket_connection(scenario_type: str, delta: int):
    """Track active WebSocket connections"""
    websocket_connections_active.labels(scenario_type=scenario_type).inc(delta)


def track_websocket_message(scenario_type: str, direction: str, duration: float, message_type: str):
    """Track WebSocket message metrics"""
    websocket_messages_total.labels(
        scenario_type=scenario_type,
        direction=direction
    ).inc()

    websocket_message_duration_seconds.labels(
        scenario_type=scenario_type,
        message_type=message_type
    ).observe(duration)


def track_error(service: str, error_type: str):
    """Track error metrics"""
    errors_total.labels(
        service=service,
        error_type=error_type
    ).inc()


def get_metrics() -> bytes:
    """Get Prometheus metrics export"""
    return generate_latest()


def initialize_metrics(version: str, environment: str):
    """Initialize application info"""
    application_info.info({
        'version': version,
        'environment': environment,
    })
