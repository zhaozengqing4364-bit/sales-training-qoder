"""Shared StepFun realtime transport helpers."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets
from websockets.exceptions import InvalidStatus

from common.monitoring.logger import get_logger

logger = get_logger(__name__)

STEPFUN_DEFAULT_SESSION_MODALITIES = ("text", "audio")
STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES = 512 * 1024
STEPFUN_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "key",
        "secret",
        "sig",
        "signature",
        "token",
    }
)


@dataclass(frozen=True, slots=True)
class StepFunSessionConfig:
    """Runtime-only data needed to initialize a StepFun realtime session."""

    voice: str
    temperature: float
    input_audio_format: str
    output_audio_format: str
    modalities: tuple[str, ...] = STEPFUN_DEFAULT_SESSION_MODALITIES
    turn_detection: dict[str, Any] | None = None
    input_transcription_enabled: bool = False
    input_transcription_language: str = ""
    input_transcription_model: str = ""
    instructions: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)


class StepFunSendStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StepFunSendResult:
    status: StepFunSendStatus
    error_type: str = ""


class StepFunHealthStatus(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class StepFunHealthResult:
    status: StepFunHealthStatus
    error_type: str = ""


class StepFunBackpressureStatus(StrEnum):
    ALLOW = "allow"
    DROP = "drop"


@dataclass(frozen=True, slots=True)
class StepFunBackpressurePolicy:
    high_watermark_bytes: int


@dataclass(frozen=True, slots=True)
class StepFunBackpressureResult:
    status: StepFunBackpressureStatus


def build_stepfun_session_update_payload(
    config: StepFunSessionConfig,
) -> dict[str, Any]:
    """Build the StepFun ``session.update`` payload from transport config."""

    session: dict[str, Any] = {
        "modalities": list(config.modalities),
        "voice": config.voice,
        "temperature": config.temperature,
        "input_audio_format": config.input_audio_format,
        "output_audio_format": config.output_audio_format,
        "turn_detection": config.turn_detection,
    }

    if config.input_transcription_enabled:
        input_audio_transcription: dict[str, Any] = {}
        if config.input_transcription_language:
            input_audio_transcription["language"] = config.input_transcription_language
        if config.input_transcription_model:
            input_audio_transcription["model"] = config.input_transcription_model
        if input_audio_transcription:
            session["input_audio_transcription"] = input_audio_transcription

    if config.instructions:
        session["instructions"] = config.instructions
    if config.tools:
        session["tools"] = config.tools

    return {"type": "session.update", "session": session}


def build_stepfun_realtime_endpoint(url: str, *, model: str) -> str:
    """Attach or replace the StepFun realtime model query parameter."""

    parsed = urlsplit(url)
    if parsed.username or parsed.password:
        raise ValueError("stepfun_realtime_url_must_not_include_userinfo")

    query_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key == "model":
            continue
        if normalized_key in STEPFUN_SENSITIVE_QUERY_KEYS:
            raise ValueError("stepfun_realtime_url_must_not_include_sensitive_query")
        query_pairs.append((key, value))
    query_pairs.append(("model", model))
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_pairs),
            parsed.fragment,
        )
    )


class StepFunUpstreamConnectError(RuntimeError):
    """Raised when StepFun realtime handshake is rejected."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


def resolve_stepfun_upstream_status_message(status_code: int) -> str:
    """Map StepFun HTTP status codes to operator-facing guidance."""

    messages = {
        401: (
            "StepFun API 密钥无效或未授权（HTTP 401），"
            "请检查 backend/.env 中的 STEPFUN_API_KEY。"
        ),
        402: (
            "StepFun 账户余额不足或需充值（HTTP 402），"
            "请到 StepFun 控制台核对计费与额度。"
        ),
        403: "StepFun API 访问被拒绝（HTTP 403）。",
        429: "StepFun 请求过于频繁（HTTP 429），请稍后再试。",
    }
    return messages.get(
        status_code,
        f"StepFun 实时语音上游拒绝连接（HTTP {status_code}）。",
    )


class StepFunTransport:
    """Deep module for StepFun upstream connect/close mechanics."""

    def __init__(
        self,
        *,
        local_provider_enabled: Callable[[], bool] | None = None,
        local_provider_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._local_provider_enabled = local_provider_enabled
        self._local_provider_factory = local_provider_factory

    async def connect(self, *, api_key: str, url: str, model: str) -> Any:
        """Connect to StepFun or the local provider, returning a WebSocket-like object."""

        if (
            self._local_provider_enabled is not None
            and self._local_provider_factory is not None
            and self._local_provider_enabled()
        ):
            return self._local_provider_factory()

        endpoint = build_stepfun_realtime_endpoint(url, model=model)
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            return await websockets.connect(endpoint, additional_headers=headers)
        except InvalidStatus as exc:
            status_code = exc.response.status_code
            raise StepFunUpstreamConnectError(
                status_code,
                resolve_stepfun_upstream_status_message(status_code),
            ) from exc

    async def close(self, upstream_ws: Any) -> None:
        """Close a WebSocket-like upstream safely."""

        if upstream_ws is None:
            return
        close = getattr(upstream_ws, "close", None)
        if not callable(close):
            return
        try:
            result = close()
            if inspect.isawaitable(result):
                await result
        except (RuntimeError, ValueError, OSError):
            pass

    async def send_json(
        self, upstream_ws: Any, payload: dict[str, Any]
    ) -> StepFunSendResult:
        """Send one JSON payload through a WebSocket-like upstream."""

        event_type = str(payload.get("type") or "")
        try:
            send_json = getattr(upstream_ws, "send_json", None)
            if callable(send_json):
                result = send_json(payload)
                transport_method = "send_json"
            else:
                send = getattr(upstream_ws, "send", None)
                if not callable(send):
                    logger.error(
                        "stepfun_upstream_send_unsupported",
                        event_type=event_type,
                        upstream_type=type(upstream_ws).__name__,
                        error_category="disconnected",
                        error_reason="connection_closed",
                        error_type="AttributeError",
                    )
                    return StepFunSendResult(
                        status=StepFunSendStatus.FAILED,
                        error_type="AttributeError",
                    )
                message = json.dumps(payload, ensure_ascii=False)
                result = send(message)
                transport_method = "send"
            if inspect.isawaitable(result):
                await result
        except (AttributeError, RuntimeError, TypeError, ValueError, OSError) as exc:
            logger.error(
                "stepfun_upstream_send_failed",
                event_type=event_type,
                upstream_type=type(upstream_ws).__name__,
                error_category="disconnected",
                error_reason="connection_closed",
                error_type=type(exc).__name__,
            )
            return StepFunSendResult(
                status=StepFunSendStatus.FAILED,
                error_type=type(exc).__name__,
            )
        logger.debug(
            "stepfun_upstream_send_ok",
            event_type=event_type,
            transport_method=transport_method,
            upstream_type=type(upstream_ws).__name__,
        )
        return StepFunSendResult(status=StepFunSendStatus.SENT)

    async def check_health(
        self,
        upstream_ws: Any,
        *,
        timeout_seconds: float | None = None,
    ) -> StepFunHealthResult:
        """Check upstream keepalive with a WebSocket-like ping/pong."""

        try:
            ping = getattr(upstream_ws, "ping")
            result = ping()
            if inspect.isawaitable(result):
                if timeout_seconds is None:
                    await result
                else:
                    await asyncio.wait_for(result, timeout=timeout_seconds)
        except TimeoutError as exc:
            return StepFunHealthResult(
                status=StepFunHealthStatus.UNHEALTHY,
                error_type=type(exc).__name__,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            return StepFunHealthResult(
                status=StepFunHealthStatus.UNHEALTHY,
                error_type=type(exc).__name__,
            )
        return StepFunHealthResult(status=StepFunHealthStatus.HEALTHY)

    def decide_backpressure(
        self,
        payload: dict[str, Any],
        *,
        pending_bytes: int,
        policy: StepFunBackpressurePolicy,
    ) -> StepFunBackpressureResult:
        """Decide whether an upstream event should pass under current pressure."""

        if (
            payload.get("type") == "input_audio_buffer.append"
            and pending_bytes > policy.high_watermark_bytes
        ):
            return StepFunBackpressureResult(status=StepFunBackpressureStatus.DROP)
        return StepFunBackpressureResult(status=StepFunBackpressureStatus.ALLOW)
