"""Explicit structural seam required by scenario-specific StepFun mixins."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastapi import WebSocket

from common.db.session_lifecycle import SessionLifecycleTransition


class StepFunRuntimeAdapterPort:
    """Typed cooperative-MRO bridge to an application-root transport base.

    Scenario mixins inherit this port. The application root places the concrete
    transport after it in the MRO, so every forwarding method delegates to that
    selected transport without either domain importing the other.
    """

    manager: Any
    websocket: Any
    session_id: str | None
    user_id: str | None
    session_status: str
    ai_state: str
    turn_count: int
    current_request_id: int
    _active_response: Any
    _connection_epoch: int
    _last_disconnect_reason: str | None
    _grounding_result: Any
    _grounding_module: Any
    _pending_blocked_response_text: str
    _latest_knowledge_answer_diagnostics: Any
    _instruction_contract_hash: Any
    _agent_capabilities_config: dict[str, Any]
    _persona_behavior_config: dict[str, Any]
    _db_session_factory: Callable[[], Any]
    _persisted_message_keys: set[tuple[int, str, str]]
    _db_lock: Any
    _last_final_transcript_text: Any
    _last_final_transcript_turn: Any
    _last_final_transcript_at: Any
    _normalize_connection_epoch: Callable[[Any], int]
    _record_runtime_error: Callable[[str, str], None]
    _handle_interrupt: Any
    _normalize_transcript: Callable[..., Any]
    _build_transcript_metadata: Callable[..., dict[str, Any]]
    _cancel_pending_response_after_commit: Any
    _create_response_from_pending_commit: Any

    def _transport(self) -> Any:
        """Return the next explicit transport implementation in the root MRO."""
        return cast(Any, super())

    def __init__(self, **kwargs: Any) -> None:
        self._transport().__init__(**kwargs)

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None:
        await self._transport().handle_connection(
            websocket,
            session_id,
            token,
            trace_id=trace_id,
        )

    def _create_state_snapshot(self) -> Any:
        return self._transport()._create_state_snapshot()

    async def _restore_session_state(self, state: Any) -> None:
        await self._transport()._restore_session_state(state)

    async def _connect_upstream(self) -> None:
        await self._transport()._connect_upstream()

    async def _save_session_state(self) -> None:
        await self._transport()._save_session_state()

    async def _create_response(self, *, count_turn: bool = False) -> bool:
        return bool(
            await self._transport()._create_response(count_turn=count_turn)
        )

    async def _handle_upstream_response_created(
        self, event: dict[str, Any]
    ) -> None:
        await self._transport()._handle_upstream_response_created(event)

    async def _handle_upstream_response_audio_delta(
        self, event: dict[str, Any]
    ) -> None:
        await self._transport()._handle_upstream_response_audio_delta(event)

    async def _handle_binary_frame(self, data: bytes) -> bool:
        return bool(await self._transport()._handle_binary_frame(data))

    def _reset_turn_runtime_state(self) -> None:
        self._transport()._reset_turn_runtime_state()

    async def _prepare_grounding_context(self, user_text: str) -> None:
        await self._transport()._prepare_grounding_context(user_text)

    async def _load_effective_policy(self) -> None:
        await self._transport()._load_effective_policy()

    async def sync_lifecycle_transition(
        self, transition: SessionLifecycleTransition
    ) -> None:
        await self._transport().sync_lifecycle_transition(transition)

    async def _handle_client_text(self, raw_text: str) -> None:
        await self._transport()._handle_client_text(raw_text)
