"""Presentation production façade for the explicit realtime session Engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import WebSocket

from common.db.session_lifecycle import SessionLifecycleTransition
from common.websocket.base_handler import WebSocketSendResult
from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
    LegacyPresentationStepFunRealtimeHandler,
)
from training_runtime.realtime import (
    ENGINE_STATE_VERSION,
    RealtimeSessionEngine,
    RealtimeTransition,
)


class PresentationRuntimeAdapter(Protocol):
    scenario: str
    session_status: str
    ai_state: str

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None: ...

    async def send_message(self, message: dict[str, Any]) -> Any: ...

    async def close(
        self, code: int = 1000, reason: str = "Session closed"
    ) -> None: ...

    async def sync_lifecycle_transition(
        self, transition: SessionLifecycleTransition
    ) -> None: ...

    def get_runtime_diagnostics(self) -> dict[str, Any]: ...


RuntimeAdapterFactory = Callable[..., PresentationRuntimeAdapter]


@dataclass(slots=True)
class PresentationScenarioHooks:
    scenario_type: str = "presentation"
    transition_count: int = 0
    last_event_name: str | None = None

    def on_transition(self, transition: RealtimeTransition) -> None:
        self.transition_count += 1
        self.last_event_name = transition.event_name


class PresentationRealtimeEngineHandler:
    """Explicit composition boundary used by the Presentation websocket route."""

    def __init__(
        self,
        *,
        runtime_adapter_factory: RuntimeAdapterFactory = (
            LegacyPresentationStepFunRealtimeHandler
        ),
    ) -> None:
        self._hooks = PresentationScenarioHooks()
        self._engine = RealtimeSessionEngine(
            scenario_type="presentation",
            hooks=self._hooks,
        )
        self._runtime_adapter = runtime_adapter_factory(runtime_engine=self._engine)

    @property
    def engine(self) -> RealtimeSessionEngine:
        return self._engine

    @property
    def runtime_adapter(self) -> PresentationRuntimeAdapter:
        return self._runtime_adapter

    @property
    def scenario(self) -> str:
        return self._runtime_adapter.scenario

    @property
    def session_status(self) -> str:
        return self._runtime_adapter.session_status

    @property
    def ai_state(self) -> str:
        return self._runtime_adapter.ai_state

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str,
        trace_id: str | None = None,
    ) -> None:
        await self._runtime_adapter.handle_connection(
            websocket,
            session_id,
            token,
            trace_id=trace_id,
        )

    async def send_message(
        self, message: dict[str, Any]
    ) -> WebSocketSendResult | Any:
        return await self._runtime_adapter.send_message(message)

    async def close(
        self, code: int = 1000, reason: str = "Session closed"
    ) -> None:
        await self._runtime_adapter.close(code=code, reason=reason)

    async def sync_lifecycle_transition(
        self, transition: SessionLifecycleTransition
    ) -> None:
        await self._runtime_adapter.sync_lifecycle_transition(transition)

    def get_runtime_diagnostics(self) -> dict[str, Any]:
        adapter_diagnostics = self._runtime_adapter.get_runtime_diagnostics()
        safe_adapter_fields = {
            key: adapter_diagnostics[key]
            for key in (
                "session_status",
                "ai_state",
                "current_request_id",
                "coach_health",
                "reconnect_state",
            )
            if key in adapter_diagnostics
        }
        return {
            "selected_runtime": "presentation_realtime_engine",
            "rollout_enabled": True,
            "rollback_runtime": "legacy_presentation_stepfun",
            "engine_state_version": ENGINE_STATE_VERSION,
            "engine_state": self._engine.snapshot(),
            "adapter": safe_adapter_fields,
            "transition_count": self._hooks.transition_count,
            "last_transition": self._hooks.last_event_name,
        }
