"""
Unit tests for SessionLifecycleService state machine transitions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import common.db.session_lifecycle as session_lifecycle_module
from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SESSION_LIFECYCLE_RACE_SCENARIOS,
    SessionLifecycleService,
)


LIFECYCLE_CONCURRENCY_CONTRACT = {
    "locking_strategy": (
        "Use optimistic compare-and-swap on PracticeSession.status instead of row locks so the "
        "focused SQLite-backed lifecycle proof can reproduce stale AsyncSession snapshots across two "
        "writers and still verify deterministic convergence."
    ),
    "converged_races": {
        "sales_end_beats_stale_resume": "A stale resume must converge to persisted scoring as a no-op.",
        "presentation_end_beats_stale_pause": "A stale pause must converge to persisted completed as a no-op.",
    },
    "intentional_terminal_statuses": {
        "sales": "scoring",
        "presentation": "completed",
    },
    "intentional_differences": {
        "sales": "Fresh sales end keeps the scoring handoff explicit; later background work may finalize to completed.",
        "presentation": "Presentation end lands directly on completed without introducing a scoring handoff.",
    },
    "regression_entrypoint": (
        "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
        "backend/tests/unit/test_session_lifecycle_service.py "
        "backend/tests/integration/test_session_lifecycle_api.py -x -q"
    ),
}


def _make_session(
    *,
    session_id: str | None = None,
    status: str = "preparing",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    return SimpleNamespace(
        session_id=session_id,
        status=status,
        start_time=start_time,
        end_time=end_time,
        total_duration_seconds=None,
    )


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    return SessionLifecycleService(mock_db)


def test_lifecycle_concurrency_contract_documents_strategy_and_regression_entrypoint() -> None:
    assert "optimistic compare-and-swap" in LIFECYCLE_CONCURRENCY_CONTRACT["locking_strategy"]
    assert "SQLite" in LIFECYCLE_CONCURRENCY_CONTRACT["locking_strategy"]
    assert "row locks" in LIFECYCLE_CONCURRENCY_CONTRACT["locking_strategy"]
    assert set(LIFECYCLE_CONCURRENCY_CONTRACT["converged_races"]) == {
        scenario.slug for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS
    }
    assert LIFECYCLE_CONCURRENCY_CONTRACT["regression_entrypoint"] == (
        "backend/venv/bin/python -m pytest -c backend/pyproject.toml "
        "backend/tests/unit/test_session_lifecycle_service.py "
        "backend/tests/integration/test_session_lifecycle_api.py -x -q"
    )


def test_lifecycle_concurrency_contract_keeps_terminal_split_explicit(service) -> None:
    assert LIFECYCLE_CONCURRENCY_CONTRACT["intentional_terminal_statuses"] == {
        "sales": "scoring",
        "presentation": "completed",
    }
    assert service.terminal_status_for_scenario("sales") == "scoring"
    assert service.terminal_status_for_scenario("presentation") == "completed"
    assert "background work may finalize to completed" in LIFECYCLE_CONCURRENCY_CONTRACT[
        "intentional_differences"
    ]["sales"]
    assert "directly on completed" not in LIFECYCLE_CONCURRENCY_CONTRACT[
        "intentional_differences"
    ]["sales"]
    assert "directly on completed" in LIFECYCLE_CONCURRENCY_CONTRACT[
        "intentional_differences"
    ]["presentation"]


def test_race_catalog_prioritizes_terminal_regressions() -> None:
    assert [scenario.slug for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS] == [
        "sales_end_beats_stale_resume",
        "presentation_end_beats_stale_pause",
    ]
    assert [scenario.expected_status for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS] == [
        "scoring",
        "completed",
    ]
    assert all(scenario.priority == "critical" for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS)
    assert all(scenario.winner_action == "end" for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS)
    assert {scenario.stale_action for scenario in SESSION_LIFECYCLE_RACE_SCENARIOS} == {"resume", "pause"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "race_scenario",
    SESSION_LIFECYCLE_RACE_SCENARIOS,
    ids=lambda scenario: scenario.slug,
)
async def test_stale_terminal_writer_converges_to_persisted_terminal_noop(
    service,
    mock_db,
    monkeypatch,
    race_scenario,
):
    session = _make_session(
        session_id=str(uuid4()),
        status=race_scenario.initial_status,
    )
    update_result = MagicMock()
    update_result.rowcount = 0
    read_result = MagicMock()
    read_result.first.return_value = (
        race_scenario.expected_status,
        session.start_time,
        datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
        300,
        race_scenario.scenario_type,
    )
    mock_db.execute.side_effect = [update_result, read_result]
    warning_spy = MagicMock()
    monkeypatch.setattr(session_lifecycle_module.logger, "warning", warning_spy)

    transition = await service.transition(
        session=session,
        scenario_type=race_scenario.scenario_type,
        action=race_scenario.stale_action,
        now=datetime(2026, 2, 11, 12, 1, tzinfo=UTC),
    )

    assert transition.changed is False
    assert transition.from_status == race_scenario.expected_status
    assert transition.to_status == race_scenario.expected_status
    assert session.status == race_scenario.expected_status
    mock_db.flush.assert_not_awaited()
    warning_spy.assert_called_once()
    assert warning_spy.call_args.args[0] == "practice_session_lifecycle_concurrency_conflict"
    assert warning_spy.call_args.kwargs == {
        "session_id": session.session_id,
        "action": race_scenario.stale_action,
        "stale_status": race_scenario.initial_status,
        "persisted_status": race_scenario.expected_status,
        "scenario_type": race_scenario.scenario_type,
        "converged_to_terminal": True,
    }


@pytest.mark.asyncio
async def test_fresh_terminal_resume_still_raises_invalid_transition(service, mock_db):
    session = _make_session(status="scoring")
    result = MagicMock()
    result.first.return_value = ("scoring", session.start_time, None, None, "sales")
    result.scalar_one_or_none.return_value = "scoring"
    mock_db.execute.return_value = result

    with pytest.raises(InvalidSessionTransitionError) as exc_info:
        await service.transition(
            session=session,
            scenario_type="sales",
            action="resume",
        )

    assert exc_info.value.action == "resume"
    assert exc_info.value.from_status == "scoring"
    assert exc_info.value.expected == "paused|in_progress"
    mock_db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_transition_sets_in_progress_and_start_time(service, mock_db):
    session = _make_session(status="preparing")
    now = datetime(2026, 2, 11, 8, 30, tzinfo=UTC)

    transition = await service.transition(
        session=session,
        scenario_type="sales",
        action="start",
        now=now,
    )

    assert transition.changed is True
    assert transition.from_status == "preparing"
    assert transition.to_status == "in_progress"
    assert transition.ai_state == "listening"
    assert session.status == "in_progress"
    assert session.start_time == now
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_pause_then_resume_transitions(service, mock_db):
    session = _make_session(
        status="in_progress",
        start_time=datetime(2026, 2, 11, 9, 0, tzinfo=UTC),
    )

    pause_transition = await service.transition(
        session=session,
        scenario_type="sales",
        action="pause",
    )

    assert pause_transition.changed is True
    assert pause_transition.to_status == "paused"
    assert pause_transition.ai_state == "idle"
    assert session.status == "paused"

    mock_db.flush.reset_mock()

    resume_transition = await service.transition(
        session=session,
        scenario_type="sales",
        action="resume",
    )

    assert resume_transition.changed is True
    assert resume_transition.from_status == "paused"
    assert resume_transition.to_status == "in_progress"
    assert resume_transition.ai_state == "listening"
    assert session.status == "in_progress"
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_pause_transition_is_idempotent(service, mock_db):
    session = _make_session(status="paused")

    transition = await service.transition(
        session=session,
        scenario_type="sales",
        action="pause",
    )

    assert transition.changed is False
    assert transition.from_status == "paused"
    assert transition.to_status == "paused"
    mock_db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_end_transition_sales_sets_scoring_and_duration(service, mock_db):
    start_time = datetime(2026, 2, 11, 10, 0, 0)  # naive timestamp
    now = datetime(2026, 2, 11, 10, 5, 30, tzinfo=UTC)
    session = _make_session(status="in_progress", start_time=start_time)

    transition = await service.transition(
        session=session,
        scenario_type="sales",
        action="end",
        now=now,
    )

    assert transition.changed is True
    assert transition.to_status == "scoring"
    assert transition.session_ended is True
    assert session.status == "scoring"
    assert session.end_time == now
    assert session.total_duration_seconds == 330
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_end_transition_presentation_sets_completed(service, mock_db):
    now = datetime(2026, 2, 11, 11, 0, tzinfo=UTC)
    session = _make_session(status="paused", start_time=datetime(2026, 2, 11, 10, 45, tzinfo=UTC))

    transition = await service.transition(
        session=session,
        scenario_type="presentation",
        action="end",
        now=now,
    )

    assert transition.changed is True
    assert transition.to_status == "completed"
    assert session.status == "completed"
    assert session.end_time == now
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_resume_from_preparing_raises(service, mock_db):
    session = _make_session(status="preparing")

    with pytest.raises(InvalidSessionTransitionError) as exc_info:
        await service.transition(
            session=session,
            scenario_type="sales",
            action="resume",
        )

    assert exc_info.value.action == "resume"
    assert exc_info.value.from_status == "preparing"
    assert exc_info.value.expected == "paused|in_progress"
    mock_db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_transition_by_target_status_uses_resume_from_paused(service, mock_db):
    session = _make_session(status="paused")

    transition = await service.transition_by_target_status(
        session=session,
        scenario_type="sales",
        target_status="in_progress",
    )

    assert transition.action == "resume"
    assert transition.to_status == "in_progress"
    assert session.status == "in_progress"
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_transition_by_target_status_rejects_terminal_mismatch(service, mock_db):
    session = _make_session(status="in_progress")

    with pytest.raises(InvalidSessionTransitionError) as exc_info:
        await service.transition_by_target_status(
            session=session,
            scenario_type="sales",
            target_status="completed",
        )

    assert exc_info.value.expected == "scoring"
    mock_db.flush.assert_not_awaited()

