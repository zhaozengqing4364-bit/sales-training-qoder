from __future__ import annotations

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


class RealtimeTurnCoordinator:
    """Coordinates realtime turn lifecycle state behind a small interface."""

    def __init__(self) -> None:
        self._current_turn_id: str | None = None
        self._is_user_speaking = False
        self._is_model_responding = False

    def start_turn(self, turn_id: str) -> TurnStartResult:
        if self._current_turn_id is not None:
            return TurnStartResult(started=False, reason="turn_already_active")
        self._current_turn_id = turn_id
        return TurnStartResult(started=True)

    def end_turn(self, turn_id: str) -> bool:
        if self._current_turn_id is None or self._current_turn_id != turn_id:
            return False
        self._current_turn_id = None
        self._is_user_speaking = False
        self._is_model_responding = False
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

    def on_user_audio_start(self) -> None:
        self._is_user_speaking = True

    def on_user_audio_stop(self) -> None:
        self._is_user_speaking = False

    def on_model_response_start(self) -> None:
        self._is_model_responding = True

    def on_model_response_done(self) -> None:
        self._is_model_responding = False

    def reset(self) -> None:
        self._current_turn_id = None
        self._is_user_speaking = False
        self._is_model_responding = False
