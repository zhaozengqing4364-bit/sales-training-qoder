"""Shared StepFun realtime transport helpers."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode

import websockets


@dataclass(frozen=True, slots=True)
class StepFunSessionConfig:
    """Runtime-only data needed to initialize a StepFun realtime session."""

    voice: str
    temperature: float
    input_audio_format: str
    output_audio_format: str
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

        query = urlencode({"model": model})
        endpoint = f"{url}?{query}"
        headers = {"Authorization": f"Bearer {api_key}"}
        return await websockets.connect(endpoint, additional_headers=headers)

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

    async def send_json(self, upstream_ws: Any, payload: dict[str, Any]) -> StepFunSendResult:
        """Send one JSON payload through a WebSocket-like upstream."""

        try:
            send_json = getattr(upstream_ws, "send_json")
            result = send_json(payload)
            if inspect.isawaitable(result):
                await result
        except (RuntimeError, ValueError, OSError) as exc:
            return StepFunSendResult(
                status=StepFunSendStatus.FAILED,
                error_type=type(exc).__name__,
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
