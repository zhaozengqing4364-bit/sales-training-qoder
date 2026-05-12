from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import CheckConstraint

from common.db.models import (
    PracticeSession,
    SessionStatus,
    TrainingTask,
    TrainingTaskStatus,
)


def _constraint_allowed_values(table, constraint_name: str) -> set[str]:
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint) and constraint.name == constraint_name:
            return set(re.findall(r"'([^']+)'", str(constraint.sqltext)))
    raise AssertionError(f"Missing check constraint: {constraint_name}")


def test_should_keep_training_task_and_practice_session_statuses_free_of_runtime_states() -> None:
    forbidden_runtime_states = {"preflight", "reconnect", "stage"}
    training_task_statuses = {item.value for item in TrainingTaskStatus}
    practice_session_statuses = {item.value for item in SessionStatus}

    assert training_task_statuses == {
        "assigned",
        "in_progress",
        "completed",
        "expired",
        "cancelled",
    }
    assert practice_session_statuses == {
        "preparing",
        "in_progress",
        "paused",
        "completed",
        "scoring",
    }
    assert training_task_statuses.isdisjoint(forbidden_runtime_states)
    assert practice_session_statuses.isdisjoint(forbidden_runtime_states)
    assert _constraint_allowed_values(
        PracticeSession.__table__,
        "ck_session_status",
    ) == practice_session_statuses
    assert _constraint_allowed_values(
        TrainingTask.__table__,
        "ck_training_tasks_status",
    ) == training_task_statuses


def test_stepfun_realtime_requirements_include_python_socks() -> None:
    requirements_path = Path(__file__).resolve().parents[2] / "requirements.txt"
    requirements = requirements_path.read_text(encoding="utf-8").splitlines()

    assert any(line.startswith("python-socks>=") for line in requirements)


def test_should_not_restore_legacy_sales_handler_modules() -> None:
    websocket_dir = Path(__file__).resolve().parents[2] / "src" / "sales_bot" / "websocket"

    assert not (websocket_dir / "base_sales_handler.py").exists()
    assert not (websocket_dir / "enhanced_handler.py").exists()
    assert not (websocket_dir / "simple_handler.py").exists()
