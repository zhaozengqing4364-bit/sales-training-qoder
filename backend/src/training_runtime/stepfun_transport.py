"""Shared StepFun realtime transport helpers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
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
