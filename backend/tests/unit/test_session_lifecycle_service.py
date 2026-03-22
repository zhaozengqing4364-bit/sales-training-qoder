"""
Unit tests for SessionLifecycleService state machine transitions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from common.db.session_lifecycle import (
    InvalidSessionTransitionError,
    SessionLifecycleService,
)


def _make_session(
    *,
    status: str = "preparing",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    return SimpleNamespace(
        session_id=str(uuid4()),
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

