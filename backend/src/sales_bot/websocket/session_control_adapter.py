"""Thin lifecycle-control adapter for StepFun websocket sessions."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
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


@dataclass(frozen=True, slots=True)
class SessionControlTransitionRecord:
    session_id: str | None
    action: SessionLifecycleAction
    payload_fingerprint: str
    success: bool
    error: str | None = None


class SessionControlAdapter:
    """Small injectable seam around existing SessionLifecycleService rules."""

    _ALLOWED_ACTION_STATUSES: dict[SessionLifecycleAction, set[str]] = {
        "start": {"preparing", "in_progress"},
        "pause": {"in_progress", "paused"},
        "resume": {"paused", "in_progress"},
        "end": {"in_progress", "paused", "scoring", "completed"},
    }
    _EXPECTED_ACTION_STATUSES: dict[SessionLifecycleAction, str] = {
        "start": "preparing|in_progress",
        "pause": "in_progress|paused",
        "resume": "paused|in_progress",
        "end": "in_progress|paused|completed|scoring",
    }

    def __init__(
        self,
        lifecycle_service: SessionLifecycleTransitionService,
        *,
        max_history_size: int = 100,
    ) -> None:
        self._lifecycle_service = lifecycle_service
        self._history: deque[SessionControlTransitionRecord] = deque(
            maxlen=max_history_size
        )

    async def apply_action(
        self,
        *,
        session: Any,
        scenario_type: str | None,
        action: SessionLifecycleAction,
        payload: Any | None = None,
    ) -> Any:
        payload_fingerprint = self._fingerprint_payload(payload)
        if hasattr(session, "status"):
            from_status = str(getattr(session, "status") or "preparing")
            if not self.validate_transition(from_status, action=action):
                exc = InvalidSessionTransitionError(
                    action=action,
                    from_status=from_status,
                    expected=self._EXPECTED_ACTION_STATUSES[action],
                    scenario_type=(scenario_type or "sales").lower(),
                )
                self._record_transition(
                    session=session,
                    action=action,
                    payload_fingerprint=payload_fingerprint,
                    success=False,
                    error=exc.message,
                )
                raise exc

        try:
            transition = await self._lifecycle_service.transition(
                session=session,
                scenario_type=scenario_type,
                action=action,
            )
        except Exception as exc:
            self._record_transition(
                session=session,
                action=action,
                payload_fingerprint=payload_fingerprint,
                success=False,
                error=str(exc),
            )
            raise

        self._record_transition(
            session=session,
            action=action,
            payload_fingerprint=payload_fingerprint,
            success=True,
        )
        return transition

    def transition_history(self) -> tuple[SessionControlTransitionRecord, ...]:
        return tuple(self._history)

    def recover_last_failed_transition(
        self,
    ) -> SessionControlTransitionRecord | None:
        for record in reversed(self._history):
            if not record.success:
                return record
        return None

    def is_idempotent(
        self,
        *,
        session: Any,
        action: SessionLifecycleAction,
        payload: Any | None = None,
    ) -> bool:
        session_id = self._session_id(session)
        payload_fingerprint = self._fingerprint_payload(payload)
        return any(
            record.success
            and record.session_id == session_id
            and record.action == action
            and record.payload_fingerprint == payload_fingerprint
            for record in self._history
        )

    def _record_transition(
        self,
        *,
        session: Any,
        action: SessionLifecycleAction,
        payload_fingerprint: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        self._history.append(
            SessionControlTransitionRecord(
                session_id=self._session_id(session),
                action=action,
                payload_fingerprint=payload_fingerprint,
                success=success,
                error=error,
            )
        )

    @staticmethod
    def _session_id(session: Any) -> str | None:
        session_id = getattr(session, "session_id", None)
        return str(session_id) if session_id is not None else None

    @staticmethod
    def _fingerprint_payload(payload: Any | None) -> str:
        return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))

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

    def validate_transition(
        self,
        status: str,
        action: SessionLifecycleAction | None = None,
    ) -> bool:
        """Expose lifecycle validation while preserving legacy input-allowed rule."""
        if action is not None:
            return status in self._ALLOWED_ACTION_STATUSES[action]
        return SessionLifecycleService.is_input_allowed(status)
