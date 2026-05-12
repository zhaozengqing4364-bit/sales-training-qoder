from __future__ import annotations

from pathlib import Path

from common.db.models import PracticeSession, TrainingTaskStatus


def test_should_keep_training_task_and_practice_session_statuses_free_of_runtime_states() -> None:
    assert {item.value for item in TrainingTaskStatus} == {
        "assigned",
        "in_progress",
        "completed",
        "expired",
        "cancelled",
    }
    assert "preflight" not in str(PracticeSession.__table__.constraints)
    assert "reconnect" not in str(PracticeSession.__table__.constraints)
    assert "stage" not in str(PracticeSession.__table__.constraints)
    assert "preflight" not in str(TrainingTaskStatus.__members__)
    assert "reconnect" not in str(TrainingTaskStatus.__members__)
    assert "stage" not in str(TrainingTaskStatus.__members__)


def test_should_not_restore_legacy_sales_handler_modules() -> None:
    websocket_dir = Path(__file__).resolve().parents[2] / "src" / "sales_bot" / "websocket"

    assert not (websocket_dir / "base_sales_handler.py").exists()
    assert not (websocket_dir / "enhanced_handler.py").exists()
    assert not (websocket_dir / "simple_handler.py").exists()
