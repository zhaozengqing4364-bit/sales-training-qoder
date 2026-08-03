from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from foundation_standard_pack import COMPETENCIES, install_or_verify_standard_pack
from learning.models import LearningQuestion, LearningQuiz
from newcomer_training.models import NewcomerPath

BACKEND_ROOT = Path(__file__).resolve().parents[3]
BASELINE_REVISION = "20260715_0000_001"
EXPECTED_HEAD_REVISION = "20260717_1500_006"


def _postgres_url() -> str | None:
    candidate = (
        os.getenv("FOUNDATION_MIGRATION_TEST_DATABASE_URL")
        or os.getenv("NEWCOMER_TRAINING_TEST_DATABASE_URL")
        or os.getenv("TASK_RUNTIME_TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
    )
    if not candidate or not candidate.startswith(("postgresql://", "postgresql+asyncpg://")):
        return None
    return candidate


POSTGRES_URL = _postgres_url()

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        POSTGRES_URL is None,
        reason="An isolated-schema PostgreSQL URL is required for the Foundation release migration gate",
    ),
]


class FoundationMigrationHarness:
    def __init__(
        self,
        *,
        schema: str,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.schema = schema
        self.engine = engine
        self.session_factory = session_factory

    async def run_alembic(self, *arguments: str) -> str:
        assert POSTGRES_URL is not None
        migration_url = make_url(POSTGRES_URL).update_query_dict(
            {"options": f"-csearch_path={self.schema}"}
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            *arguments,
            cwd=BACKEND_ROOT,
            env={
                **os.environ,
                "DATABASE_URL": migration_url.render_as_string(hide_password=False),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_bytes, _ = await process.communicate()
        output = output_bytes.decode("utf-8", errors="replace")
        assert process.returncode == 0, output
        return output


@pytest_asyncio.fixture
async def migration_harness() -> AsyncIterator[FoundationMigrationHarness]:
    assert POSTGRES_URL is not None
    schema = f"foundation_release_{uuid.uuid4().hex[:12]}"
    admin_engine = create_async_engine(POSTGRES_URL, pool_pre_ping=True)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        POSTGRES_URL,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield FoundationMigrationHarness(
            schema=schema,
            engine=engine,
            session_factory=factory,
        )
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


async def _current_revision(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        return str(
            (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
        )


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
            )
        )
        return {str(value) for value in rows.scalars()}


@pytest.mark.asyncio
async def test_foundation_release_migration_round_trip_and_repeatable_seed(
    migration_harness: FoundationMigrationHarness,
) -> None:
    harness = migration_harness
    script = ScriptDirectory.from_config(Config(str(BACKEND_ROOT / "alembic.ini")))
    assert script.get_heads() == [EXPECTED_HEAD_REVISION]

    # Empty database -> current launch head.
    await harness.run_alembic("upgrade", "head")
    assert await _current_revision(harness.engine) == EXPECTED_HEAD_REVISION
    required_tables = {
        "durable_tasks",
        "ai_invocations",
        "newcomer_paths",
        "learning_question_candidates",
        "audio_submissions_v2",
        "coach_sessions",
        "competency_evidence_records",
        "readiness_dossiers",
        "newcomer_release_plans",
    }
    assert required_tables <= await _table_names(harness.engine)
    assert "No new upgrade operations detected" in await harness.run_alembic("check")

    # Current head -> launch baseline -> current head proves the supported old baseline.
    await harness.run_alembic("downgrade", BASELINE_REVISION)
    assert await _current_revision(harness.engine) == BASELINE_REVISION
    assert required_tables.isdisjoint(await _table_names(harness.engine))
    async with harness.engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO users "
                "(user_id, wechat_user_id, name, email, credential_status, "
                "credential_version, role, is_active) VALUES "
                "('baseline-user', 'baseline-wechat', '基线用户', "
                "'baseline-user@example.invalid', 'active', 1, 'user', true)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO admin_role_permissions "
                "(id, role, permission, created_at) VALUES "
                "('baseline-custom-permission', 'admin', "
                "'foundation.baseline.custom', now())"
            )
        )

    await harness.run_alembic("upgrade", "head")
    await harness.run_alembic("upgrade", "head")
    assert await _current_revision(harness.engine) == EXPECTED_HEAD_REVISION
    async with harness.engine.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM users WHERE user_id = 'baseline-user'")
            )
            == 1
        )
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM admin_role_permissions "
                    "WHERE id = 'baseline-custom-permission'"
                )
            )
            == 1
        )

    # The governed standard pack is effect-once and verify-only detects drift.
    async with harness.session_factory() as session:
        first = await install_or_verify_standard_pack(
            session,
            organization_id="foundation-release-org",
        )
        await session.commit()
    async with harness.session_factory() as session:
        second = await install_or_verify_standard_pack(
            session,
            organization_id="foundation-release-org",
        )
        await session.commit()
    async with harness.session_factory() as session:
        verified = await install_or_verify_standard_pack(
            session,
            organization_id="foundation-release-org",
            verify_only=True,
        )
        await session.rollback()

    assert first.path_revision_id == second.path_revision_id == verified.path_revision_id
    assert verified.verified_only is True
    assert verified.competency_keys == tuple(item.key for item in COMPETENCIES)
    async with harness.session_factory() as session:
        assert (
            int(await session.scalar(select(func.count(NewcomerPath.path_id))) or 0)
            == 1
        )
        assert (
            int(await session.scalar(select(func.count(LearningQuestion.question_id))) or 0)
            == 7
        )
        assert (
            int(await session.scalar(select(func.count(LearningQuiz.quiz_id))) or 0)
            == 7
        )

    # PostgreSQL reports no unvalidated FK and the standard pack still verifies.
    async with harness.engine.connect() as connection:
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE contype = 'f' AND connamespace = current_schema()::regnamespace "
                    "AND NOT convalidated"
                )
            )
            == 0
        )
