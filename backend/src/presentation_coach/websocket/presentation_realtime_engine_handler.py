"""Presentation production façade for the explicit realtime session Engine."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import WebSocket

from common.db.session_lifecycle import SessionLifecycleTransition
from common.websocket.base_handler import WebSocketSendResult
from presentation_coach.websocket.presentation_stepfun_realtime_handler import (
    LegacyPresentationStepFunRealtimeHandler,
)


class RealtimeEngine(Protocol):
    @property
    def state(self) -> Any: ...

    def snapshot(self) -> dict[str, object]: ...


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
RuntimeEngineFactory = Callable[..., RealtimeEngine]


@dataclass(slots=True)
class PresentationScenarioHooks:
    scenario_type: str = "presentation"
    transition_count: int = 0
    last_event_name: str | None = None

    def on_transition(self, transition: Any) -> None:
        self.transition_count += 1
        self.last_event_name = transition.event_name


class PresentationRealtimeEngineHandler:
    """Explicit composition boundary used by the Presentation websocket route."""

    def __init__(
        self,
        *,
        runtime_engine_factory: RuntimeEngineFactory,
        runtime_adapter_factory: RuntimeAdapterFactory = (
            LegacyPresentationStepFunRealtimeHandler
        ),
    ) -> None:
        self._hooks = PresentationScenarioHooks()
        self._engine = runtime_engine_factory(
            scenario_type="presentation",
            hooks=self._hooks,
        )
        self._runtime_adapter = runtime_adapter_factory(runtime_engine=self._engine)

    @property
    def engine(self) -> RealtimeEngine:
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
        engine_snapshot = self._engine.snapshot()
        safe_adapter_fields = {
            key: deepcopy(adapter_diagnostics[key])
            for key in (
                "session_status",
                "ai_state",
                "provider_port_enabled",
                "selected_provider_path",
                "current_request_id",
                "live_session_summary",
                "claim_truth",
                "coach_health",
                "knowledge_answer_diagnostics",
                "reconnect_state",
                "runtime_events",
            )
            if key in adapter_diagnostics
        }
        return {
            **safe_adapter_fields,
            "selected_runtime": "presentation_realtime_engine",
            "rollout_enabled": True,
            "rollback_runtime": "legacy_presentation_stepfun",
            "engine_state_version": engine_snapshot.get("version"),
            "engine_state": engine_snapshot,
            "adapter": safe_adapter_fields,
            "transition_count": self._hooks.transition_count,
            "last_transition": self._hooks.last_event_name,
        }
