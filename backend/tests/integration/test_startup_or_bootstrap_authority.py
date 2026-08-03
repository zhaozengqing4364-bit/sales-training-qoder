from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import common.db.session as db_session
from common.db.session import DatabaseSchemaNotReadyError


def _create_legacy_personas_schema(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE personas (
                        id VARCHAR(36) PRIMARY KEY,
                        system_prompt TEXT,
                        knowledge_base_ids TEXT
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO personas (id, system_prompt, knowledge_base_ids)
                    VALUES ('persona-1', 'legacy prompt', '["kb-1"]')
                    """
                )
            )
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_startup_refuses_unstamped_legacy_schema_without_patching_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.db"
    _create_legacy_personas_schema(db_path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(db_session, "get_expected_alembic_heads", lambda: ("head-a",))

    try:
        with pytest.raises(DatabaseSchemaNotReadyError, match=r"found \[\]"):
            await db_session.verify_database_schema(db_engine=engine)
    finally:
        await engine.dispose()

    sync_engine = create_engine(f"sqlite:///{db_path}")
    try:
        with sync_engine.connect() as connection:
            columns = {
                column["name"] for column in inspect(connection).get_columns("personas")
            }
            assert columns == {"id", "system_prompt", "knowledge_base_ids"}
    finally:
        sync_engine.dispose()
