"""
Prometheus Metrics Collection
Tracks system performance and business metrics
"""
import asyncio
import time
from functools import wraps

from prometheus_client import Counter, Gauge, Histogram, Info

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"]
)

# WebSocket metrics
websocket_connections_active = Gauge(
    "websocket_connections_active",
    "Active WebSocket connections",
    ["scenario_type"]
)

websocket_messages_total = Counter(
    "websocket_messages_total",
    "Total WebSocket messages",
    ["scenario_type", "message_type", "direction"]
)

websocket_message_duration_seconds = Histogram(
    "websocket_message_duration_seconds",
    "WebSocket message processing latency",
    ["scenario_type", "message_type"]
)

# ASR metrics
asr_requests_total = Counter(
    "asr_requests_total",
    "Total ASR requests",
    ["provider", "status"]
)

asr_duration_seconds = Histogram(
    "asr_duration_seconds",
    "ASR processing latency",
    ["provider"]
)

asr_audio_duration_seconds = Histogram(
    "asr_audio_duration_seconds",
    "Audio duration processed by ASR",
    ["provider"]
)

# TTS metrics
tts_requests_total = Counter(
    "tts_requests_total",
    "Total TTS requests",
    ["provider", "status"]
)

tts_duration_seconds = Histogram(
    "tts_duration_seconds",
    "TTS generation latency",
    ["provider"]
)

# LLM metrics
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["model", "operation"]
)

llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "Total LLM tokens consumed",
    ["model", "token_type"]
)

llm_duration_seconds = Histogram(
    "llm_duration_seconds",
    "LLM response latency",
    ["model", "operation"]
)

# Business metrics
practice_sessions_total = Counter(
    "practice_sessions_total",
    "Total practice sessions",
    ["scenario_type", "status"]
)

practice_session_duration_seconds = Histogram(
    "practice_session_duration_seconds",
    "Practice session duration",
    ["scenario_type"]
)

interruptions_total = Counter(
    "interruptions_total",
    "Total interruptions detected",
    ["interruption_type", "was_effective"]
)

# Cost tracking
session_cost_yuan = Histogram(
    "session_cost_yuan",
    "Cost per practice session in Yuan",
    ["scenario_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0]
)

# System info
app_info = Info(
    "app",
    "Application information"
)


def track_time(histogram: Histogram, *labels):
    """Decorator to track function execution time"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    histogram.labels(*labels).observe(duration)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    histogram.labels(*labels).observe(duration)
            return sync_wrapper
    return decorator
