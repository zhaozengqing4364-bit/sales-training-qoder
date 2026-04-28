"""Unit tests for the audio archival job."""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from common.error_handling.result import Result
from common.jobs.audio_archival import AudioArchivalJob, AudioArchivalScheduler


class _EmptyScalarResult:
    def all(self) -> list[object]:
        return []


class _EmptyExecuteResult:
    def scalars(self) -> _EmptyScalarResult:
        return _EmptyScalarResult()


class _CapturingAsyncSession:
    def __init__(self) -> None:
        self.statement = None
        self.rollback_called = False

    async def execute(self, statement):
        self.statement = statement
        return _EmptyExecuteResult()

    async def rollback(self) -> None:
        self.rollback_called = True


class _AsyncSessionContext:
    def __init__(self) -> None:
        self.session = object()
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True


class _FakeArchivalJob:
    def __init__(self) -> None:
        self.calls: list[tuple[object, int]] = []

    async def archive_old_audio(self, db, batch_size: int):
        self.calls.append((db, batch_size))
        return Result.ok({"archived_count": 1})


@pytest.mark.asyncio
async def test_should_filter_unarchived_sessions_with_sqlalchemy_boolean_expression():
    """Regression: do not use Python ``not`` against SQLAlchemy boolean columns."""
    db = _CapturingAsyncSession()

    result = await AudioArchivalJob().archive_old_audio(db, batch_size=25)

    assert result.is_success
    assert db.statement is not None
    compiled = str(
        db.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "practice_sessions.archived is false" in compiled
    assert "where false" not in compiled
    assert not db.rollback_called


def test_audio_archival_job_reads_storage_paths_from_env(monkeypatch: pytest.MonkeyPatch):
    """Scheduler-enabled jobs should honor deployment storage paths."""
    monkeypatch.setenv("AUDIO_ARCHIVAL_RETENTION_DAYS", "45")
    monkeypatch.setenv("AUDIO_STORAGE_PATH", "/tmp/audio-source")
    monkeypatch.setenv("AUDIO_ARCHIVE_STORAGE_PATH", "/tmp/audio-archive")

    job = AudioArchivalJob()

    assert job.retention_days == 45
    assert job.audio_storage_path == "/tmp/audio-source"
    assert job.archive_storage_path == "/tmp/audio-archive"


@pytest.mark.asyncio
async def test_audio_archival_scheduler_runs_job_with_fresh_session() -> None:
    """The lifespan-owned scheduler seam should open a session per batch."""
    context = _AsyncSessionContext()
    job = _FakeArchivalJob()
    scheduler = AudioArchivalScheduler(
        job=job,
        session_factory=lambda: context,
        interval_seconds=3600,
        batch_size=25,
    )

    result = await scheduler.run_once()

    assert result.is_success
    assert job.calls == [(context.session, 25)]
    assert context.entered is True
    assert context.exited is True


@pytest.mark.asyncio
async def test_audio_archival_scheduler_start_stop_is_idempotent() -> None:
    """Startup/shutdown should be safe for repeated lifespan calls."""
    scheduler = AudioArchivalScheduler(
        job=_FakeArchivalJob(),
        session_factory=_AsyncSessionContext,
        interval_seconds=3600,
        batch_size=10,
    )

    await scheduler.start()
    await scheduler.start()

    assert scheduler.is_running is True

    await scheduler.stop()
    await scheduler.stop()

    assert scheduler.is_running is False
