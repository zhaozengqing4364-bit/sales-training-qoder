from __future__ import annotations

from sales_bot.websocket.realtime_turn_coordinator import RealtimeTurnCoordinator


def test_start_turn_creates_turn_with_id() -> None:
    coordinator = RealtimeTurnCoordinator()

    result = coordinator.start_turn("turn-1")

    assert result.started is True
    assert result.reason is None
    current_turn = coordinator.get_current_turn()
    assert current_turn is not None
    assert current_turn.turn_id == "turn-1"


def test_end_turn_clears_current_turn() -> None:
    coordinator = RealtimeTurnCoordinator()
    coordinator.start_turn("turn-1")

    ended = coordinator.end_turn("turn-1")

    assert ended is True
    assert coordinator.get_current_turn() is None


def test_is_speaking_true_during_model_response() -> None:
    coordinator = RealtimeTurnCoordinator()

    coordinator.on_model_response_start()

    assert coordinator.is_speaking() is True


def test_is_speaking_false_after_response_done() -> None:
    coordinator = RealtimeTurnCoordinator()
    coordinator.on_model_response_start()

    coordinator.on_model_response_done()

    assert coordinator.is_speaking() is False


def test_concurrent_turn_rejected() -> None:
    coordinator = RealtimeTurnCoordinator()
    coordinator.start_turn("turn-1")

    result = coordinator.start_turn("turn-2")

    assert result.started is False
    assert result.reason == "turn_already_active"
    current_turn = coordinator.get_current_turn()
    assert current_turn is not None
    assert current_turn.turn_id == "turn-1"


def test_reset_clears_all_state() -> None:
    coordinator = RealtimeTurnCoordinator()
    coordinator.start_turn("turn-1")
    coordinator.on_user_audio_start()
    coordinator.on_model_response_start()

    coordinator.reset()

    assert coordinator.get_current_turn() is None
    assert coordinator.is_speaking() is False
