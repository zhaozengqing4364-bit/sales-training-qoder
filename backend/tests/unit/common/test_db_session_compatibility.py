from __future__ import annotations

import pytest
from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import common.db.session as db_session
from common.db.session import (
    STARTUP_DB_AUTHORITY,
    DatabaseSchemaNotReadyError,
    verify_database_schema,
)


def test_startup_db_authority_is_read_only_and_alembic_owned() -> None:
    assert (
        STARTUP_DB_AUTHORITY["startup_verifier"]
        == "common.db.session.verify_database_schema"
    )
    assert STARTUP_DB_AUTHORITY["startup_table_bootstrap"] == "disabled"
    assert STARTUP_DB_AUTHORITY["startup_compatibility_guards"] == (
        "alembic head equality",
    )
    assert (
        STARTUP_DB_AUTHORITY["schema_migration_entrypoint"]
        == "cd backend && alembic upgrade head"
    )
    assert "legacy_schema_repair_entrypoint" not in STARTUP_DB_AUTHORITY
    assert STARTUP_DB_AUTHORITY["auth_bootstrap_entrypoint"].endswith(
        "--email <email> --role admin"
    )


@pytest.mark.asyncio
async def test_unstamped_database_is_rejected_without_creating_tables(
    monkeypatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db_session, "get_expected_alembic_heads", lambda: ("head-a",))
    try:
        with pytest.raises(DatabaseSchemaNotReadyError, match=r"found \[\]"):
            await verify_database_schema(db_engine=engine)

        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
        assert tables == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_matching_database_head_is_verified_with_no_ddl(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(db_session, "get_expected_alembic_heads", lambda: ("head-a",))
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE alembic_version "
                    "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                )
            )
            await connection.execute(
                text("INSERT INTO alembic_version(version_num) VALUES ('head-a')")
            )

        observed_statements: list[str] = []

        def capture_statement(
            _connection, _cursor, statement, _parameters, _context, _executemany
        ) -> None:
            observed_statements.append(str(statement).strip().upper())

        event.listen(engine.sync_engine, "before_cursor_execute", capture_statement)
        await verify_database_schema(db_engine=engine)

        assert observed_statements
        assert not any(
            statement.startswith(("CREATE ", "ALTER ", "DROP ", "INSERT ", "UPDATE "))
            for statement in observed_statements
        )
    finally:
        await engine.dispose()


def test_active_alembic_history_has_exactly_one_expected_head() -> None:
    assert db_session.get_expected_alembic_heads() == ("20260717_1500_006",)
