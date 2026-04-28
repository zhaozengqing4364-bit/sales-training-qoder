"""Unit tests for the audio archival job."""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql

from common.jobs.audio_archival import AudioArchivalJob


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
