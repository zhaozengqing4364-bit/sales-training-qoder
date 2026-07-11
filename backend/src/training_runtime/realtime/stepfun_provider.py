"""StepFun implementation of the neutral realtime Provider Port."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import cast

from training_runtime.stepfun_transport import (
    STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES,
    StepFunBackpressurePolicy,
    StepFunBackpressureStatus,
    StepFunHealthStatus,
    StepFunSendStatus,
    StepFunSessionConfig,
    StepFunTransport,
    StepFunUpstreamConnectError,
    build_stepfun_session_update_payload,
)

from .provider import (
    JsonValue,
    ProviderBackpressureResult,
    ProviderCapability,
    ProviderCommand,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderEvent,
    ProviderHealthResult,
    ProviderSendResult,
    RealtimeProviderCapabilities,
    RealtimeProviderError,
    RealtimeProviderSessionConfig,
    validate_provider_capabilities,
)
from .stepfun_codec import StepFunEventCodec

_STEPFUN_CAPABILITIES = RealtimeProviderCapabilities(
    supported=frozenset(ProviderCapability),
    input_audio_formats=None,
    output_audio_formats=None,
)


class StepFunRealtimeProvider:
    """Compose ``StepFunTransport`` without exposing its raw connection or JSON."""

    __slots__ = (
        "_api_key",
        "_backpressure_policy",
        "_codec",
        "_connection",
        "_transport",
        "_url",
    )

    def __init__(
        self,
        *,
        api_key: str,
        url: str,
        transport: StepFunTransport | None = None,
        codec: StepFunEventCodec | None = None,
    ) -> None:
        if type(api_key) is not str or not api_key.strip():
            raise ValueError("stepfun_api_key_must_be_non_empty")
        if type(url) is not str or not url.strip():
            raise ValueError("stepfun_url_must_be_non_empty")
        self._api_key = api_key
        self._url = url
        self._transport = StepFunTransport() if transport is None else transport
        self._codec = StepFunEventCodec() if codec is None else codec
        self._connection: object | None = None
        self._backpressure_policy = StepFunBackpressurePolicy(
            high_watermark_bytes=STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES
        )

    @property
    def capabilities(self) -> RealtimeProviderCapabilities:
        return _STEPFUN_CAPABILITIES

    async def connect(self, config: RealtimeProviderSessionConfig) -> None:
        if self._connection is not None:
            raise RealtimeProviderError(
                category=ProviderErrorCategory.PROTOCOL,
                reason=ProviderErrorReason.INVALID_EVENT,
                retryable=False,
            )
        validate_provider_capabilities(capabilities=self.capabilities, config=config)
        try:
            connection = await self._transport.connect(
                api_key=self._api_key,
                url=self._url,
                model=config.model,
            )
        except StepFunUpstreamConnectError as exc:
            raise _connect_error(exc.status_code) from exc
        except (RuntimeError, ValueError, OSError) as exc:
            raise RealtimeProviderError(
                category=ProviderErrorCategory.UNAVAILABLE,
                reason=ProviderErrorReason.UPSTREAM_UNAVAILABLE,
                retryable=True,
            ) from exc

        payload = build_stepfun_session_update_payload(_session_config(config))
        send_result = await self._transport.send_json(connection, payload)
        if send_result.status is not StepFunSendStatus.SENT:
            await self._transport.close(connection)
            raise RealtimeProviderError(
                category=ProviderErrorCategory.DISCONNECTED,
                reason=ProviderErrorReason.CONNECTION_CLOSED,
                retryable=True,
            )
        self._connection = connection

    async def send(self, command: ProviderCommand) -> ProviderSendResult:
        connection = self._connection
        if connection is None:
            return ProviderSendResult(
                accepted=False,
                error_category=ProviderErrorCategory.DISCONNECTED,
                error_reason=ProviderErrorReason.CONNECTION_CLOSED,
            )
        payload = self._codec.encode_command(command)
        result = await self._transport.send_json(connection, payload)
        if result.status is StepFunSendStatus.SENT:
            return ProviderSendResult(accepted=True)
        return ProviderSendResult(
            accepted=False,
            error_category=ProviderErrorCategory.DISCONNECTED,
            error_reason=ProviderErrorReason.CONNECTION_CLOSED,
        )

    async def receive(self, *, connection_epoch: int) -> ProviderEvent:
        connection = self._connection
        if connection is None:
            raise RealtimeProviderError(
                category=ProviderErrorCategory.DISCONNECTED,
                reason=ProviderErrorReason.CONNECTION_CLOSED,
                retryable=True,
            )
        recv = getattr(connection, "recv", None)
        if not callable(recv):
            raise RealtimeProviderError(
                category=ProviderErrorCategory.PROTOCOL,
                reason=ProviderErrorReason.INVALID_EVENT,
                retryable=False,
            )
        try:
            raw = await cast(Callable[[], Awaitable[object]], recv)()
        except (RuntimeError, ValueError, OSError) as exc:
            raise RealtimeProviderError(
                category=ProviderErrorCategory.DISCONNECTED,
                reason=ProviderErrorReason.CONNECTION_CLOSED,
                retryable=True,
            ) from exc
        if type(raw) not in {str, bytes}:
            return self._codec.decode_event("", connection_epoch=connection_epoch)
        return self._codec.decode_event(
            cast(str | bytes, raw),
            connection_epoch=connection_epoch,
        )

    async def check_health(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> ProviderHealthResult:
        connection = self._connection
        if connection is None:
            return ProviderHealthResult(
                healthy=False,
                error_category=ProviderErrorCategory.DISCONNECTED,
                error_reason=ProviderErrorReason.CONNECTION_CLOSED,
            )
        result = await self._transport.check_health(
            connection,
            timeout_seconds=timeout_seconds,
        )
        if result.status is StepFunHealthStatus.HEALTHY:
            return ProviderHealthResult(healthy=True)
        if result.error_type == "TimeoutError":
            return ProviderHealthResult(
                healthy=False,
                error_category=ProviderErrorCategory.TIMEOUT,
                error_reason=ProviderErrorReason.IDLE_TIMEOUT,
            )
        return ProviderHealthResult(
            healthy=False,
            error_category=ProviderErrorCategory.DISCONNECTED,
            error_reason=ProviderErrorReason.CONNECTION_CLOSED,
        )

    def decide_backpressure(
        self,
        command: ProviderCommand,
        *,
        pending_bytes: int,
    ) -> ProviderBackpressureResult:
        result = self._transport.decide_backpressure(
            self._codec.encode_command(command),
            pending_bytes=pending_bytes,
            policy=self._backpressure_policy,
        )
        if result.status is StepFunBackpressureStatus.ALLOW:
            return ProviderBackpressureResult(accepted=True)
        return ProviderBackpressureResult(
            accepted=False,
            error_reason=ProviderErrorReason.BACKPRESSURE_LIMIT,
        )

    async def close(self) -> None:
        connection = self._connection
        if connection is None:
            return
        self._connection = None
        await self._transport.close(connection)

    def __repr__(self) -> str:
        return (
            "StepFunRealtimeProvider("
            "api_key='<redacted>', url='<redacted>', "
            f"connected={self._connection is not None!r}"
            ")"
        )


def _session_config(config: RealtimeProviderSessionConfig) -> StepFunSessionConfig:
    turn_detection = (
        _plain_mapping(config.turn_detection)
        if config.turn_detection is not None
        else None
    )
    return StepFunSessionConfig(
        voice=config.voice,
        temperature=config.temperature,
        input_audio_format=config.input_audio_format,
        output_audio_format=config.output_audio_format,
        modalities=config.modalities,
        turn_detection=turn_detection,
        input_transcription_enabled=config.input_transcription_enabled,
        input_transcription_language=config.input_transcription_language,
        input_transcription_model=config.input_transcription_model,
        instructions=config.instructions,
        tools=[_plain_mapping(tool) for tool in config.tools],
    )


def _plain_mapping(value: Mapping[str, JsonValue]) -> dict[str, object]:
    return {key: _plain_value(item) for key, item in value.items()}


def _plain_value(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return _plain_mapping(value)
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    return value


def _connect_error(status_code: int) -> RealtimeProviderError:
    if status_code == 401:
        return RealtimeProviderError(
            category=ProviderErrorCategory.AUTHENTICATION,
            reason=ProviderErrorReason.INVALID_CREDENTIALS,
            retryable=False,
        )
    if status_code == 402:
        return RealtimeProviderError(
            category=ProviderErrorCategory.QUOTA,
            reason=ProviderErrorReason.QUOTA_EXHAUSTED,
            retryable=False,
        )
    if status_code == 403:
        return RealtimeProviderError(
            category=ProviderErrorCategory.AUTHENTICATION,
            reason=ProviderErrorReason.FORBIDDEN,
            retryable=False,
        )
    if status_code == 429:
        return RealtimeProviderError(
            category=ProviderErrorCategory.RATE_LIMIT,
            reason=ProviderErrorReason.RATE_LIMITED,
            retryable=True,
        )
    return RealtimeProviderError(
        category=ProviderErrorCategory.UNAVAILABLE,
        reason=ProviderErrorReason.UPSTREAM_UNAVAILABLE,
        retryable=True,
    )


__all__ = ["StepFunRealtimeProvider"]
