from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnState:
    turn_id: str
    user_audio_active: bool = False
    model_response_active: bool = False


@dataclass(frozen=True)
class TurnStartResult:
    started: bool
    reason: str | None = None


@dataclass(frozen=True)
class TurnEventResult:
    event: str
    turn_id: str | None
    state_changed: bool


@dataclass(frozen=True)
class InterruptionDecision:
    should_interrupt: bool
    reason: str | None = None
    turn_id: str | None = None
    user_interrupted: bool = False


@dataclass(frozen=True)
class TurnTimeoutResult:
    expired: bool
    turn_id: str | None
    elapsed_seconds: float
    timeout_seconds: float


class RealtimeTurnCoordinator:
    """Coordinates realtime turn lifecycle state behind a small interface."""

    def __init__(
        self,
        *,
        turn_timeout_seconds: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._current_turn_id: str | None = None
        self._is_user_speaking = False
        self._is_model_responding = False
        self._user_interrupted_current_turn = False
        self._turn_started_at: float | None = None
        self._turn_timeout_seconds = turn_timeout_seconds
        self._clock = clock or time.monotonic

    def start_turn(self, turn_id: str) -> TurnStartResult:
        if self._current_turn_id is not None:
            return TurnStartResult(started=False, reason="turn_already_active")
        self._current_turn_id = turn_id
        self._turn_started_at = self._clock()
        self._user_interrupted_current_turn = False
        return TurnStartResult(started=True)

    def end_turn(self, turn_id: str) -> bool:
        if self._current_turn_id is None or self._current_turn_id != turn_id:
            return False
        self._current_turn_id = None
        self._is_user_speaking = False
        self._is_model_responding = False
        self._user_interrupted_current_turn = False
        self._turn_started_at = None
        return True

    def is_speaking(self) -> bool:
        return self._is_model_responding

    def get_current_turn(self) -> TurnState | None:
        if self._current_turn_id is None:
            return None
        return TurnState(
            turn_id=self._current_turn_id,
            user_audio_active=self._is_user_speaking,
            model_response_active=self._is_model_responding,
        )

    def on_user_audio_start(self) -> TurnEventResult:
        changed = not self._is_user_speaking
        self._is_user_speaking = True
        return TurnEventResult(
            event="user_audio_start",
            turn_id=self._current_turn_id,
            state_changed=changed,
        )

    def on_user_audio_stop(self) -> TurnEventResult:
        changed = self._is_user_speaking
        self._is_user_speaking = False
        return TurnEventResult(
            event="user_audio_stop",
            turn_id=self._current_turn_id,
            state_changed=changed,
        )

    def on_model_response_start(self) -> TurnEventResult:
        changed = not self._is_model_responding
        self._is_model_responding = True
        return TurnEventResult(
            event="model_response_start",
            turn_id=self._current_turn_id,
            state_changed=changed,
        )

    def on_model_response_done(self) -> TurnEventResult:
        changed = self._is_model_responding
        self._is_model_responding = False
        return TurnEventResult(
            event="model_response_done",
            turn_id=self._current_turn_id,
            state_changed=changed,
        )

    def resolve_interruption(self) -> InterruptionDecision:
        if not (self._is_user_speaking and self._is_model_responding):
            return InterruptionDecision(
                should_interrupt=False,
                turn_id=self._current_turn_id,
            )
        self._user_interrupted_current_turn = True
        return InterruptionDecision(
            should_interrupt=True,
            reason="user_audio_overlaps_model_response",
            turn_id=self._current_turn_id,
            user_interrupted=True,
        )

    def check_turn_timeout(self) -> TurnTimeoutResult:
        if self._current_turn_id is None or self._turn_started_at is None:
            return TurnTimeoutResult(
                expired=False,
                turn_id=self._current_turn_id,
                elapsed_seconds=0.0,
                timeout_seconds=self._turn_timeout_seconds,
            )
        elapsed_seconds = self._clock() - self._turn_started_at
        return TurnTimeoutResult(
            expired=elapsed_seconds >= self._turn_timeout_seconds,
            turn_id=self._current_turn_id,
            elapsed_seconds=elapsed_seconds,
            timeout_seconds=self._turn_timeout_seconds,
        )

    def reset(self) -> None:
        self._current_turn_id = None
        self._is_user_speaking = False
        self._is_model_responding = False
        self._user_interrupted_current_turn = False
        self._turn_started_at = None
