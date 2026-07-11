"""StepFun implementation of the neutral realtime Provider Port."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from typing import TypeAlias, TypeVar, cast
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from training_runtime.stepfun_transport import (
    STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES,
    STEPFUN_SENSITIVE_QUERY_KEYS,
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
    ProviderCommandKind,
    ProviderErrorCategory,
    ProviderErrorReason,
    ProviderEvent,
    ProviderEventKind,
    ProviderHealthResult,
    ProviderSendResult,
    RealtimeProviderCapabilities,
    RealtimeProviderError,
    RealtimeProviderSessionConfig,
    validate_provider_capabilities,
)
from .stepfun_codec import StepFunEventCodec

_CloseCleanupResult: TypeAlias = tuple[
    tuple[object, ...],
    BaseException | None,
]
_T = TypeVar("_T")

_STEPFUN_CAPABILITIES = RealtimeProviderCapabilities(
    supported=frozenset(ProviderCapability),
    input_audio_formats=None,
    output_audio_formats=None,
)


@dataclass(frozen=True, slots=True)
class _ResponseAuthority:
    generation: int
    request_id: int
    stream_id: str
    response_id: str | None = None


@dataclass(frozen=True, slots=True)
class _ResponseSendTransaction:
    authority: _ResponseAuthority
    completion: asyncio.Future[bool]


_CORRELATABLE_RESPONSE_EVENT_KINDS = frozenset(
    {
        ProviderEventKind.RESPONSE_CREATED,
        ProviderEventKind.RESPONSE_TEXT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_DELTA,
        ProviderEventKind.RESPONSE_TRANSCRIPT_FINAL,
        ProviderEventKind.RESPONSE_AUDIO_DELTA,
        ProviderEventKind.THINKING_DELTA,
        ProviderEventKind.THINKING_DONE,
        ProviderEventKind.RESPONSE_DONE,
    }
)


class StepFunRealtimeProvider:
    """Compose ``StepFunTransport`` without exposing its raw connection or JSON."""

    __slots__ = (
        "_api_key",
        "_backpressure_policy",
        "_codec",
        "_close_cleanup_task",
        "_close_retry_connections",
        "_call_authorities",
        "_connection",
        "_connecting",
        "_create_requires_reconnect",
        "_current_response_id",
        "_lifecycle_generation",
        "_lifecycle_lock",
        "_pending_connection",
        "_pending_generation",
        "_pending_response_authority",
        "_response_authorities",
        "_response_send_transaction",
        "_sensitive_identifier_fragments",
        "_sensitive_query_values",
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
        self._close_cleanup_task: asyncio.Task[_CloseCleanupResult] | None = None
        self._close_retry_connections: tuple[object, ...] = ()
        self._call_authorities: dict[str, _ResponseAuthority] = {}
        self._connection: object | None = None
        self._connecting = False
        self._create_requires_reconnect = False
        self._current_response_id: str | None = None
        self._lifecycle_generation = 0
        self._lifecycle_lock = asyncio.Lock()
        self._pending_connection: object | None = None
        self._pending_generation: int | None = None
        self._pending_response_authority: _ResponseAuthority | None = None
        self._response_authorities: dict[str, _ResponseAuthority] = {}
        self._response_send_transaction: _ResponseSendTransaction | None = None
        self._sensitive_query_values = _sensitive_query_values(url)
        self._sensitive_identifier_fragments = _sensitive_identifier_fragments(
            api_key,
            url,
            self._sensitive_query_values,
        )
        self._backpressure_policy = StepFunBackpressurePolicy(
            high_watermark_bytes=STEPFUN_DEFAULT_BACKPRESSURE_HIGH_WATERMARK_BYTES
        )

    @property
    def capabilities(self) -> RealtimeProviderCapabilities:
        return _STEPFUN_CAPABILITIES

    async def connect(self, config: RealtimeProviderSessionConfig) -> None:
        validate_provider_capabilities(capabilities=self.capabilities, config=config)
        generation = await self._begin_connect_attempt()
        connection: object | None = None
        pending_registered = False
        published = False
        try:
            try:
                connection = await self._transport.connect(
                    api_key=self._api_key,
                    url=self._url,
                    model=config.model,
                )
            except StepFunUpstreamConnectError as exc:
                raise _connect_error(exc.status_code) from None
            except Exception:
                raise _unavailable_error() from None

            registration_task = asyncio.create_task(
                self._register_pending_connection(generation, connection)
            )
            (
                pending_registered,
                registration_cancellation,
            ) = await _wait_task_preserving_cancellation(registration_task, None)
            if registration_cancellation is not None:
                raise registration_cancellation
            if not pending_registered:
                raise _disconnected_error()

            payload = build_stepfun_session_update_payload(_session_config(config))
            try:
                send_result = await self._transport.send_json(connection, payload)
            except Exception:
                raise _disconnected_error() from None
            if send_result.status is not StepFunSendStatus.SENT:
                raise _disconnected_error()
            published = await self._publish_connection(generation, connection)
            if not published:
                raise _disconnected_error()
        except BaseException as primary_error:
            cancellation = (
                primary_error
                if isinstance(primary_error, asyncio.CancelledError)
                else None
            )
            cleanup_error: BaseException | None = None
            try:
                if connection is not None:
                    retirement_task = asyncio.create_task(
                        self._retire_connect_connection(
                            generation,
                            connection,
                            pending_registered=pending_registered,
                        )
                    )
                    (
                        cleanup_task,
                        cancellation,
                    ) = await _wait_task_preserving_cancellation(
                        retirement_task,
                        cancellation,
                    )
                    if cleanup_task is not None:
                        cleanup_result, cancellation = await self._wait_close_cleanup(
                            cleanup_task,
                            cancellation,
                        )
                        _failed_connections, cleanup_error = cleanup_result
            except BaseException as error:
                cleanup_error = error
            finally:
                finish_task = asyncio.create_task(
                    self._finish_connect_attempt(generation)
                )
                _, cancellation = await _wait_task_preserving_cancellation(
                    finish_task,
                    cancellation,
                )
            if isinstance(primary_error, asyncio.CancelledError):
                raise
            if cancellation is not None:
                raise cancellation
            if cleanup_error is not None and isinstance(primary_error, Exception):
                raise cleanup_error
            raise

    async def send(self, command: ProviderCommand) -> ProviderSendResult:
        current = await self._current_connection()
        if current is None:
            return _disconnected_send_result()
        connection, generation = current
        payload = self._codec.encode_command(command)
        transaction: _ResponseSendTransaction | None = None
        if command.kind is ProviderCommandKind.CREATE_RESPONSE:
            allowed, transaction = await self._begin_response_send(
                connection,
                generation,
                command,
            )
            if not allowed:
                return _disconnected_send_result()
        try:
            result = await self._transport.send_json(connection, payload)
            if result.status is StepFunSendStatus.SENT:
                if await self._accept_sent_command(
                    connection,
                    generation,
                    command,
                    transaction=transaction,
                ):
                    return ProviderSendResult(accepted=True)
                return _disconnected_send_result()
        except asyncio.CancelledError as cancellation:
            retirement_task = asyncio.create_task(
                self._fail_send_and_invalidate(
                    connection,
                    generation,
                    transaction,
                )
            )
            try:
                await _wait_task_preserving_cancellation(
                    retirement_task,
                    cancellation,
                )
            except BaseException:
                cancellation.add_note(
                    "StepFun send retirement cleanup failed; provider close retry required."
                )
            raise
        except Exception:
            pass
        await self._fail_response_send(connection, generation, transaction)
        await self._invalidate_current_connection(connection, generation)
        return _disconnected_send_result()

    async def receive(self, *, connection_epoch: int) -> ProviderEvent:
        current = await self._current_connection()
        if current is None:
            raise _disconnected_error()
        connection, generation = current
        try:
            recv = getattr(connection, "recv", None)
        except Exception:
            await self._invalidate_current_connection(connection, generation)
            raise _disconnected_error() from None
        if not callable(recv):
            if not await self._connection_is_current(connection, generation):
                raise _disconnected_error()
            raise RealtimeProviderError(
                category=ProviderErrorCategory.PROTOCOL,
                reason=ProviderErrorReason.INVALID_EVENT,
                retryable=False,
            )
        try:
            raw = await cast(Callable[[], Awaitable[object]], recv)()
        except Exception:
            await self._invalidate_current_connection(connection, generation)
            raise _disconnected_error() from None
        normalized_raw = cast(str | bytes, raw) if type(raw) in {str, bytes} else ""
        try:
            event = self._codec.decode_event(
                normalized_raw,
                connection_epoch=connection_epoch,
            )
        except Exception:
            await self._invalidate_current_connection(connection, generation)
            raise _disconnected_error() from None
        if _event_contains_sensitive_value(
            event,
            sensitive_identifier_fragments=self._sensitive_identifier_fragments,
            api_key=self._api_key,
            sensitive_query_values=self._sensitive_query_values,
        ):
            event = _sensitive_event_error(connection_epoch)
        correlated_event = await self._correlate_received_event(
            connection,
            generation,
            event,
        )
        if correlated_event is None:
            raise _disconnected_error()
        return correlated_event

    async def check_health(
        self,
        *,
        timeout_seconds: float | None = None,
    ) -> ProviderHealthResult:
        current = await self._current_connection()
        if current is None:
            return _disconnected_health_result()
        connection, generation = current
        try:
            result = await self._transport.check_health(
                connection,
                timeout_seconds=timeout_seconds,
            )
            if result.status is StepFunHealthStatus.HEALTHY:
                if await self._connection_is_current(connection, generation):
                    return ProviderHealthResult(healthy=True)
                return _disconnected_health_result()
            if result.error_type == "TimeoutError":
                if await self._connection_is_current(connection, generation):
                    return ProviderHealthResult(
                        healthy=False,
                        error_category=ProviderErrorCategory.TIMEOUT,
                        error_reason=ProviderErrorReason.IDLE_TIMEOUT,
                    )
                return _disconnected_health_result()
        except Exception:
            pass
        await self._invalidate_current_connection(connection, generation)
        return _disconnected_health_result()

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
        cancellation: asyncio.CancelledError | None = None
        cleanup_task, cancellation = await self._schedule_public_close_cleanup(
            cancellation
        )
        while cleanup_task is not None:
            result, cancellation = await self._wait_close_cleanup(
                cleanup_task,
                cancellation,
            )
            failed_connections, cleanup_base_error = result
            if cleanup_base_error is not None:
                if cancellation is not None:
                    raise cancellation
                raise cleanup_base_error
            if failed_connections:
                if cancellation is not None:
                    raise cancellation
                raise _disconnected_error() from None
            cleanup_task, cancellation = await self._schedule_public_close_cleanup(
                cancellation
            )
        if cancellation is not None:
            raise cancellation

    async def _begin_connect_attempt(self) -> int:
        async with self._lifecycle_lock:
            if self._close_cleanup_task is not None or self._close_retry_connections:
                raise _disconnected_error()
            if self._connection is not None or self._connecting:
                raise RealtimeProviderError(
                    category=ProviderErrorCategory.PROTOCOL,
                    reason=ProviderErrorReason.INVALID_EVENT,
                    retryable=False,
                )
            self._lifecycle_generation += 1
            self._clear_correlations_locked()
            self._connecting = True
            return self._lifecycle_generation

    async def _register_pending_connection(
        self,
        generation: int,
        connection: object,
    ) -> bool:
        async with self._lifecycle_lock:
            if not self._connecting or self._lifecycle_generation != generation:
                return False
            self._pending_connection = connection
            self._pending_generation = generation
            return True

    async def _finalize_close_cleanup(
        self,
        cleanup_task: asyncio.Task[_CloseCleanupResult],
        result: _CloseCleanupResult,
    ) -> None:
        failed_connections, _cleanup_base_error = result
        async with self._lifecycle_lock:
            if self._close_cleanup_task is not cleanup_task:
                return
            self._close_cleanup_task = None
            self._close_retry_connections = _unique_connections(
                *self._close_retry_connections,
                *failed_connections,
            )

    def _schedule_close_cleanup_locked(
        self,
        *connections: object | None,
    ) -> asyncio.Task[_CloseCleanupResult] | None:
        owned_connections = _unique_connections(
            *self._close_retry_connections,
            *connections,
        )
        self._close_retry_connections = ()
        cleanup_task = self._close_cleanup_task
        if cleanup_task is None and owned_connections:
            cleanup_task = asyncio.create_task(
                _close_owned_connections(self._transport, owned_connections)
            )
            self._close_cleanup_task = cleanup_task
        elif cleanup_task is not None and owned_connections:
            self._close_retry_connections = owned_connections
        return cleanup_task

    def _schedule_public_close_locked(
        self,
    ) -> asyncio.Task[_CloseCleanupResult] | None:
        self._lifecycle_generation += 1
        self._connecting = False
        connection = self._connection
        pending_connection = self._pending_connection
        self._connection = None
        self._pending_connection = None
        self._pending_generation = None
        self._clear_correlations_locked()
        return self._schedule_close_cleanup_locked(
            connection,
            pending_connection,
        )

    async def _schedule_public_close_cleanup(
        self,
        cancellation: asyncio.CancelledError | None,
    ) -> tuple[
        asyncio.Task[_CloseCleanupResult] | None,
        asyncio.CancelledError | None,
    ]:
        while True:
            try:
                async with self._lifecycle_lock:
                    return self._schedule_public_close_locked(), cancellation
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error

    async def _await_close_cleanup(
        self,
        cleanup_task: asyncio.Task[_CloseCleanupResult],
    ) -> _CloseCleanupResult:
        result, cancellation = await self._wait_close_cleanup(cleanup_task, None)
        if cancellation is not None:
            raise cancellation
        return result

    async def _wait_close_cleanup(
        self,
        cleanup_task: asyncio.Task[_CloseCleanupResult],
        cancellation: asyncio.CancelledError | None,
    ) -> tuple[_CloseCleanupResult, asyncio.CancelledError | None]:
        while True:
            try:
                result = await asyncio.shield(cleanup_task)
                break
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error
        finalize_task = asyncio.create_task(
            self._finalize_close_cleanup(cleanup_task, result)
        )
        while True:
            try:
                await asyncio.shield(finalize_task)
                return result, cancellation
            except asyncio.CancelledError as error:
                if cancellation is None:
                    cancellation = error

    async def _retire_connect_connection(
        self,
        generation: int,
        connection: object,
        *,
        pending_registered: bool,
    ) -> asyncio.Task[_CloseCleanupResult] | None:
        async with self._lifecycle_lock:
            if pending_registered:
                if (
                    self._pending_connection is not connection
                    or self._pending_generation != generation
                ):
                    return None
                self._pending_connection = None
                self._pending_generation = None
            return self._schedule_close_cleanup_locked(connection)

    async def _publish_connection(
        self,
        generation: int,
        connection: object,
    ) -> bool:
        async with self._lifecycle_lock:
            if (
                not self._connecting
                or self._lifecycle_generation != generation
                or self._pending_connection is not connection
                or self._pending_generation != generation
            ):
                return False
            self._pending_connection = None
            self._pending_generation = None
            self._connection = connection
            self._connecting = False
            return True

    async def _finish_connect_attempt(self, generation: int) -> None:
        async with self._lifecycle_lock:
            if self._lifecycle_generation == generation:
                self._connecting = False

    async def _current_connection(self) -> tuple[object, int] | None:
        async with self._lifecycle_lock:
            if self._connection is None:
                return None
            return self._connection, self._lifecycle_generation

    async def _connection_is_current(
        self,
        connection: object,
        generation: int,
    ) -> bool:
        async with self._lifecycle_lock:
            return (
                self._connection is connection
                and self._lifecycle_generation == generation
            )

    async def _accept_sent_command(
        self,
        connection: object,
        generation: int,
        command: ProviderCommand,
        *,
        transaction: _ResponseSendTransaction | None,
    ) -> bool:
        async with self._lifecycle_lock:
            if (
                self._connection is not connection
                or self._lifecycle_generation != generation
            ):
                self._resolve_response_send_transaction_locked(
                    transaction,
                    accepted=False,
                )
                return False
            if command.kind is ProviderCommandKind.CANCEL_RESPONSE:
                self._clear_correlations_locked(clear_barrier=False)
                self._create_requires_reconnect = True
                return True
            if command.kind is not ProviderCommandKind.CREATE_RESPONSE:
                return True
            if transaction is None:
                return True
            if self._response_send_transaction is not transaction:
                self._resolve_response_send_transaction_locked(
                    transaction,
                    accepted=False,
                )
                return False
            self._response_send_transaction = None
            self._pending_response_authority = transaction.authority
            self._resolve_response_send_transaction_locked(
                transaction,
                accepted=True,
            )
            return True

    async def _begin_response_send(
        self,
        connection: object,
        generation: int,
        command: ProviderCommand,
    ) -> tuple[bool, _ResponseSendTransaction | None]:
        async with self._lifecycle_lock:
            if (
                self._connection is not connection
                or self._lifecycle_generation != generation
                or self._create_requires_reconnect
                or self._response_send_transaction is not None
                or self._pending_response_authority is not None
                or self._current_response_id is not None
            ):
                return False, None
            request_id = command.data.get("request_id")
            stream_id = command.data.get("stream_id")
            if type(request_id) is not int or type(stream_id) is not str:
                return True, None
            transaction = _ResponseSendTransaction(
                authority=_ResponseAuthority(
                    generation=generation,
                    request_id=request_id,
                    stream_id=stream_id,
                ),
                completion=asyncio.get_running_loop().create_future(),
            )
            self._response_send_transaction = transaction
            return True, transaction

    async def _fail_response_send(
        self,
        connection: object,
        generation: int,
        transaction: _ResponseSendTransaction | None,
    ) -> None:
        if transaction is None:
            return
        async with self._lifecycle_lock:
            if (
                self._connection is connection
                and self._lifecycle_generation == generation
                and self._response_send_transaction is transaction
            ):
                self._response_send_transaction = None
            self._resolve_response_send_transaction_locked(
                transaction,
                accepted=False,
            )

    async def _fail_send_and_invalidate(
        self,
        connection: object,
        generation: int,
        transaction: _ResponseSendTransaction | None,
    ) -> None:
        await self._fail_response_send(connection, generation, transaction)
        await self._invalidate_current_connection(connection, generation)

    @staticmethod
    def _resolve_response_send_transaction_locked(
        transaction: _ResponseSendTransaction | None,
        *,
        accepted: bool,
    ) -> None:
        if transaction is not None and not transaction.completion.done():
            transaction.completion.set_result(accepted)

    async def _correlate_received_event(
        self,
        connection: object,
        generation: int,
        event: ProviderEvent,
    ) -> ProviderEvent | None:
        while True:
            wait_for_send: asyncio.Future[bool] | None = None
            async with self._lifecycle_lock:
                if (
                    self._connection is not connection
                    or self._lifecycle_generation != generation
                ):
                    return None
                transaction = self._response_send_transaction
                if (
                    event.kind is ProviderEventKind.RESPONSE_CREATED
                    and transaction is not None
                    and transaction.authority.generation == generation
                ):
                    wait_for_send = transaction.completion
                else:
                    return self._correlate_event_locked(
                        event,
                        generation=generation,
                    )
            if wait_for_send is None:
                return None
            if not await asyncio.shield(wait_for_send):
                return None

    def _correlate_event_locked(
        self,
        event: ProviderEvent,
        *,
        generation: int,
    ) -> ProviderEvent:
        if event.kind is ProviderEventKind.RESPONSE_CREATED:
            return self._correlate_response_created_locked(
                event,
                generation=generation,
            )

        authority = self._event_authority_locked(event, generation=generation)
        if authority is None or not _event_matches_authority(event, authority):
            return event
        correlated = _event_with_authority(event, authority)

        if (
            correlated.kind is ProviderEventKind.CONVERSATION_ITEM
            and correlated.call_id is not None
            and correlated.data.get("item_type") == "function_call"
        ):
            existing = self._call_authorities.get(correlated.call_id)
            if existing is None or existing == authority:
                self._call_authorities[correlated.call_id] = authority

        if correlated.kind is ProviderEventKind.RESPONSE_DONE:
            self._clear_response_authority_locked(authority)
        return correlated

    def _correlate_response_created_locked(
        self,
        event: ProviderEvent,
        *,
        generation: int,
    ) -> ProviderEvent:
        response_id = event.response_id
        if response_id is None:
            return event
        existing = self._response_authorities.get(response_id)
        if existing is not None:
            return (
                _event_with_authority(event, existing)
                if _event_matches_authority(event, existing)
                else event
            )
        pending = self._pending_response_authority
        if (
            pending is None
            or pending.generation != generation
            or (
                event.request_id is not None
                and event.request_id != pending.request_id
            )
            or (
                event.stream_id is not None
                and event.stream_id != pending.stream_id
            )
        ):
            return event
        authority = replace(pending, response_id=response_id)
        self._pending_response_authority = None
        self._response_authorities[response_id] = authority
        self._current_response_id = response_id
        return _event_with_authority(event, authority)

    def _event_authority_locked(
        self,
        event: ProviderEvent,
        *,
        generation: int,
    ) -> _ResponseAuthority | None:
        if event.response_id is not None:
            authority = self._response_authorities.get(event.response_id)
            return (
                authority
                if authority is not None and authority.generation == generation
                else None
            )
        if event.kind in {
            ProviderEventKind.FUNCTION_ARGUMENTS_DELTA,
            ProviderEventKind.FUNCTION_ARGUMENTS_DONE,
        }:
            authority = (
                self._call_authorities.get(event.call_id)
                if event.call_id is not None
                else None
            )
            return (
                authority
                if authority is not None and authority.generation == generation
                else None
            )
        if event.kind is ProviderEventKind.RESPONSE_DONE:
            output_authority = self._response_done_output_authority_locked(event)
            if output_authority is not None:
                return output_authority
        if event.kind is ProviderEventKind.CONVERSATION_ITEM:
            if event.data.get("item_type") != "function_call":
                return None
        elif event.kind not in _CORRELATABLE_RESPONSE_EVENT_KINDS:
            return None
        current = (
            self._response_authorities.get(self._current_response_id)
            if self._current_response_id is not None
            else None
        )
        return (
            current
            if current is not None and current.generation == generation
            else None
        )

    def _response_done_output_authority_locked(
        self,
        event: ProviderEvent,
    ) -> _ResponseAuthority | None:
        outputs = event.data.get("function_outputs")
        if type(outputs) is not tuple or not outputs:
            return None
        authorities: list[_ResponseAuthority] = []
        for output in outputs:
            if not isinstance(output, Mapping):
                return None
            call_id = output.get("call_id")
            if type(call_id) is not str:
                return None
            authority = self._call_authorities.get(call_id)
            if authority is None:
                return None
            authorities.append(authority)
        first = authorities[0]
        return first if all(item == first for item in authorities) else None

    def _clear_response_authority_locked(
        self,
        authority: _ResponseAuthority,
    ) -> None:
        if authority.response_id is not None:
            self._response_authorities.pop(authority.response_id, None)
            if self._current_response_id == authority.response_id:
                self._current_response_id = None
        self._call_authorities = {
            call_id: item
            for call_id, item in self._call_authorities.items()
            if item != authority
        }

    def _clear_correlations_locked(self, *, clear_barrier: bool = True) -> None:
        transaction = self._response_send_transaction
        self._response_send_transaction = None
        self._resolve_response_send_transaction_locked(
            transaction,
            accepted=False,
        )
        self._pending_response_authority = None
        self._response_authorities.clear()
        self._current_response_id = None
        self._call_authorities.clear()
        if clear_barrier:
            self._create_requires_reconnect = False

    async def _invalidate_current_connection(
        self,
        connection: object,
        generation: int,
    ) -> bool:
        async with self._lifecycle_lock:
            if (
                self._connection is not connection
                or self._lifecycle_generation != generation
            ):
                return False
            self._connection = None
            self._lifecycle_generation += 1
            self._clear_correlations_locked()
            cleanup_task = self._schedule_close_cleanup_locked(connection)
        if cleanup_task is None:
            return True
        _failed_connections, cleanup_base_error = await self._await_close_cleanup(
            cleanup_task
        )
        if cleanup_base_error is not None:
            raise cleanup_base_error
        return True

    def __repr__(self) -> str:
        return (
            "StepFunRealtimeProvider("
            "api_key='<redacted>', url='<redacted>', "
            f"connected={self._connection is not None!r}"
            ")"
        )


def _event_matches_authority(
    event: ProviderEvent,
    authority: _ResponseAuthority,
) -> bool:
    return bool(
        (event.request_id is None or event.request_id == authority.request_id)
        and (event.response_id is None or event.response_id == authority.response_id)
        and (event.stream_id is None or event.stream_id == authority.stream_id)
    )


def _event_with_authority(
    event: ProviderEvent,
    authority: _ResponseAuthority,
) -> ProviderEvent:
    return replace(
        event,
        request_id=authority.request_id,
        response_id=authority.response_id,
        stream_id=authority.stream_id,
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


def _unavailable_error() -> RealtimeProviderError:
    return RealtimeProviderError(
        category=ProviderErrorCategory.UNAVAILABLE,
        reason=ProviderErrorReason.UPSTREAM_UNAVAILABLE,
        retryable=True,
    )


def _disconnected_error() -> RealtimeProviderError:
    return RealtimeProviderError(
        category=ProviderErrorCategory.DISCONNECTED,
        reason=ProviderErrorReason.CONNECTION_CLOSED,
        retryable=True,
    )


def _disconnected_send_result() -> ProviderSendResult:
    return ProviderSendResult(
        accepted=False,
        error_category=ProviderErrorCategory.DISCONNECTED,
        error_reason=ProviderErrorReason.CONNECTION_CLOSED,
    )


def _disconnected_health_result() -> ProviderHealthResult:
    return ProviderHealthResult(
        healthy=False,
        error_category=ProviderErrorCategory.DISCONNECTED,
        error_reason=ProviderErrorReason.CONNECTION_CLOSED,
    )


def _unique_connections(*connections: object | None) -> tuple[object, ...]:
    unique: list[object] = []
    for connection in connections:
        if connection is None or any(connection is item for item in unique):
            continue
        unique.append(connection)
    return tuple(unique)


def _sensitive_query_values(url: str) -> tuple[str, ...]:
    try:
        parsed = urlsplit(url)
        return tuple(
            dict.fromkeys(
                value
                for key, value in parse_qsl(parsed.query)
                if value and key.lower() in STEPFUN_SENSITIVE_QUERY_KEYS
            )
        )
    except ValueError:
        return ()


def _sensitive_identifier_fragments(
    api_key: str,
    url: str,
    sensitive_query_values: tuple[str, ...],
) -> tuple[str, ...]:
    values = [api_key, url]
    try:
        parsed = urlsplit(url)
        values.extend(
            candidate
            for candidate in (
                urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")),
                parsed.netloc,
                parsed.hostname,
                parsed.username,
                parsed.password,
            )
            if candidate
        )
    except ValueError:
        pass
    values.extend(sensitive_query_values)
    return tuple(dict.fromkeys(value for value in values if value))


def _event_contains_sensitive_value(
    event: ProviderEvent,
    *,
    sensitive_identifier_fragments: tuple[str, ...],
    api_key: str,
    sensitive_query_values: tuple[str, ...],
) -> bool:
    identifiers = (
        event.response_id,
        event.stream_id,
        event.call_id,
        event.event_id,
        event.turn_id,
        *_nested_identifier_values(event.data),
    )
    if any(
        fragment in identifier
        for identifier in identifiers
        if identifier is not None
        for fragment in sensitive_identifier_fragments
    ):
        return True
    credentials = (api_key, *sensitive_query_values)
    if event.request_id is not None and str(event.request_id) in credentials:
        return True
    return any(
        api_key in value
        or any(
            _contains_exact_secret_token(value, secret)
            for secret in sensitive_query_values
        )
        for value in _nested_string_values(event.data)
    )


def _nested_identifier_values(
    value: Mapping[str, JsonValue],
) -> tuple[str, ...]:
    identifiers: list[str] = []
    pending: list[object] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            for key, item in current.items():
                if (key == "id" or key.endswith("_id")) and type(item) is str:
                    identifiers.append(item)
                pending.append(item)
        elif type(current) is tuple:
            pending.extend(current)
    return tuple(identifiers)


def _nested_string_values(value: Mapping[str, JsonValue]) -> tuple[str, ...]:
    strings: list[str] = []
    pending: list[object] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, Mapping):
            pending.extend(current.values())
        elif type(current) is tuple:
            pending.extend(current)
        elif type(current) is str:
            strings.append(current)
    return tuple(strings)


def _contains_exact_secret_token(value: str, secret: str) -> bool:
    """Match a whole known query secret, not incidental text substrings."""
    offset = 0
    while True:
        index = value.find(secret, offset)
        if index < 0:
            return False
        end = index + len(secret)
        before_is_boundary = index == 0 or not _is_secret_token_char(value[index - 1])
        after_is_boundary = end == len(value) or not _is_secret_token_char(value[end])
        if before_is_boundary and after_is_boundary:
            return True
        offset = index + 1


def _is_secret_token_char(value: str) -> bool:
    return value.isalnum() or value in {"_", "-"}


def _sensitive_event_error(connection_epoch: int) -> ProviderEvent:
    return ProviderEvent(
        kind=ProviderEventKind.ERROR,
        provider_event_type="invalid",
        connection_epoch=connection_epoch,
        error_category=ProviderErrorCategory.PROTOCOL,
        error_reason=ProviderErrorReason.INVALID_EVENT,
    )


async def _close_owned_connections(
    transport: StepFunTransport,
    connections: tuple[object, ...],
) -> _CloseCleanupResult:
    failed: list[object] = []
    cleanup_base_error: BaseException | None = None
    for index, connection in enumerate(connections):
        try:
            await transport.close(connection)
        except Exception:
            failed.append(connection)
        except BaseException as error:
            failed.extend(connections[index:])
            cleanup_base_error = error
            break
    return _unique_connections(*failed), cleanup_base_error


async def _wait_task_preserving_cancellation(
    task: asyncio.Task[_T],
    cancellation: asyncio.CancelledError | None,
) -> tuple[_T, asyncio.CancelledError | None]:
    while True:
        try:
            return await asyncio.shield(task), cancellation
        except asyncio.CancelledError as error:
            if task.cancelled():
                raise
            if cancellation is None:
                cancellation = error


__all__ = ["StepFunRealtimeProvider"]
