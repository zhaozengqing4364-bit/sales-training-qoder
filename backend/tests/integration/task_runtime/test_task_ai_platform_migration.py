from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

POSTGRES_URL = os.getenv("TASK_RUNTIME_TEST_DATABASE_URL")
BACKEND_ROOT = Path(__file__).resolve().parents[3]
BASELINE_REVISION = "20260715_0000_001"
HEAD_REVISION = "20260716_2300_002"
SEEDED_READ_ID = "5dd8af58-8278-55b8-b651-bec1eaa79001"
SEEDED_OPERATE_ID = "5dd8af58-8278-55b8-b651-bec1eaa79002"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not POSTGRES_URL,
        reason="TASK_RUNTIME_TEST_DATABASE_URL is required for migration semantics",
    ),
]


class MigrationHarness:
    def __init__(self, *, schema: str, engine: AsyncEngine) -> None:
        self.schema = schema
        self.engine = engine

    async def run_alembic(self, *arguments: str) -> str:
        assert POSTGRES_URL is not None
        migration_url = make_url(POSTGRES_URL).update_query_dict(
            {"options": f"-csearch_path={self.schema}"}
        )
        environment = {
            **os.environ,
            "DATABASE_URL": migration_url.render_as_string(hide_password=False),
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            *arguments,
            cwd=BACKEND_ROOT,
            env=environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_bytes, _ = await process.communicate()
        output = output_bytes.decode("utf-8", errors="replace")
        assert process.returncode == 0, output
        return output


@pytest_asyncio.fixture
async def migration_harness() -> AsyncIterator[MigrationHarness]:
    assert POSTGRES_URL is not None
    schema = f"slice1_migration_{uuid.uuid4().hex[:12]}"
    admin_engine = create_async_engine(POSTGRES_URL, pool_pre_ping=True)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    schema_engine = create_async_engine(
        POSTGRES_URL,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        yield MigrationHarness(schema=schema, engine=schema_engine)
    finally:
        await schema_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


async def _current_revision(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        return str(
            (
                await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalar_one()
        )


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema()"
            )
        )
        return {str(value) for value in rows.scalars()}


async def _permission_rows(engine: AsyncEngine) -> set[tuple[str, str, str]]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT id, role, permission FROM admin_role_permissions "
                "WHERE permission LIKE 'task_runtime.%' OR id = 'custom-unrelated'"
            )
        )
        return {(str(row.id), str(row.role), str(row.permission)) for row in rows}


@pytest.mark.asyncio
async def test_migration_round_trip_preserves_custom_permission_rows(
    migration_harness: MigrationHarness,
) -> None:
    harness = migration_harness

    # Empty database -> head includes the launch baseline and both platform schemas.
    await harness.run_alembic("upgrade", "head")
    assert await _current_revision(harness.engine) == HEAD_REVISION
    assert {
        "durable_tasks",
        "task_leases",
        "outbox_events",
        "ai_invocations",
        "ai_invocation_artifacts",
        "ai_usage_ledger",
    } <= await _table_names(harness.engine)
    assert await _permission_rows(harness.engine) == {
        (SEEDED_READ_ID, "admin", "task_runtime.read"),
        (SEEDED_OPERATE_ID, "admin", "task_runtime.operate"),
    }
    async with harness.engine.connect() as connection:
        result_artifact_fk = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conname = 'fk_ai_invocations_result_artifact' "
                    "AND conrelid = 'ai_invocations'::regclass"
                )
            )
        ).scalar_one()
    assert result_artifact_fk == 1
    assert "No new upgrade operations detected" in await harness.run_alembic("check")

    # Head -> baseline removes only this revision's schema and owned seed rows.
    await harness.run_alembic("downgrade", BASELINE_REVISION)
    assert await _current_revision(harness.engine) == BASELINE_REVISION
    assert not {
        "durable_tasks",
        "task_leases",
        "outbox_events",
        "ai_invocations",
        "ai_invocation_artifacts",
        "ai_usage_ledger",
    } & await _table_names(harness.engine)
    assert await _permission_rows(harness.engine) == set()

    # A pre-existing logical permission must win the seed conflict and survive downgrade.
    async with harness.engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO admin_role_permissions "
                "(id, role, permission, created_at) VALUES "
                "('custom-read', 'admin', 'task_runtime.read', now()), "
                "('custom-unrelated', 'admin', 'custom.permission', now())"
            )
        )

    await harness.run_alembic("upgrade", "head")
    await harness.run_alembic("upgrade", "head")
    assert await _permission_rows(harness.engine) == {
        ("custom-read", "admin", "task_runtime.read"),
        (SEEDED_OPERATE_ID, "admin", "task_runtime.operate"),
        ("custom-unrelated", "admin", "custom.permission"),
    }

    await harness.run_alembic("downgrade", BASELINE_REVISION)
    assert await _permission_rows(harness.engine) == {
        ("custom-read", "admin", "task_runtime.read"),
        ("custom-unrelated", "admin", "custom.permission"),
    }
