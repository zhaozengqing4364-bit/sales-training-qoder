"""Thin lifecycle-control adapter for StepFun websocket sessions."""

from __future__ import annotations

from typing import Any, Protocol

from common.db.session_lifecycle import (
    SessionLifecycleAction,
    SessionLifecycleService,
)


class SessionLifecycleTransitionService(Protocol):
    async def transition(
        self,
        *,
        session: Any,
        scenario_type: str | None,
        action: SessionLifecycleAction,
    ) -> Any: ...


class SessionControlAdapter:
    """Small injectable seam around existing SessionLifecycleService rules."""

    def __init__(self, lifecycle_service: SessionLifecycleTransitionService) -> None:
        self._lifecycle_service = lifecycle_service

    async def apply_action(
        self,
        *,
        session: Any,
        scenario_type: str | None,
        action: SessionLifecycleAction,
    ) -> Any:
        return await self._lifecycle_service.transition(
            session=session,
            scenario_type=scenario_type,
            action=action,
        )

    async def start(
        self,
        *,
        session: Any,
        scenario_type: str | None,
    ) -> Any:
        return await self.apply_action(
            session=session,
            scenario_type=scenario_type,
            action="start",
        )

    async def pause(
        self,
        *,
        session: Any,
        scenario_type: str | None,
    ) -> Any:
        return await self.apply_action(
            session=session,
            scenario_type=scenario_type,
            action="pause",
        )

    async def resume(
        self,
        *,
        session: Any,
        scenario_type: str | None,
    ) -> Any:
        return await self.apply_action(
            session=session,
            scenario_type=scenario_type,
            action="resume",
        )

    async def end(
        self,
        *,
        session: Any,
        scenario_type: str | None,
    ) -> Any:
        return await self.apply_action(
            session=session,
            scenario_type=scenario_type,
            action="end",
        )

    def validate_transition(self, status: str) -> bool:
        """Expose existing input-allowed lifecycle rule without reauthoring states."""
        return SessionLifecycleService.is_input_allowed(status)
