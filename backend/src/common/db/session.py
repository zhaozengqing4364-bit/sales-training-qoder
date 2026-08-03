"""Async database sessions and read-only startup schema verification.

Alembic is the only schema authority. Application startup never creates,
alters, repairs, or stamps database objects.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from common.db.model_registry.registration import register_all_models
from common.monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[3]

STARTUP_DB_AUTHORITY = {
    "startup_verifier": "common.db.session.verify_database_schema",
    "startup_table_bootstrap": "disabled",
    "startup_compatibility_guards": ("alembic head equality",),
    "schema_migration_entrypoint": "cd backend && alembic upgrade head",
    "schema_migration_owner": "backend/alembic/env.py + backend/alembic/versions/*",
    "auth_bootstrap_entrypoint": (
        "cd backend && python scripts/bootstrap_auth_admin.py "
        "--email <email> --role admin"
    ),
    "note": (
        "Startup is read-only and fails unless the database already matches the "
        "single Alembic head. Schema changes are Alembic-only; pre-launch legacy "
        "databases must be rebuilt from the launch baseline."
    ),
}

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/ai_practice",
)

is_sqlite = DATABASE_URL.startswith("sqlite")
if is_sqlite:
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class DatabaseSchemaNotReadyError(RuntimeError):
    """Raised when startup observes an unstamped or out-of-date database."""


def get_expected_alembic_heads() -> tuple[str, ...]:
    """Resolve the expected heads from the active Alembic script directory."""

    config = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return tuple(sorted(ScriptDirectory.from_config(config).get_heads()))


def _read_database_alembic_heads(sync_conn: Connection) -> tuple[str, ...]:
    inspector = inspect(sync_conn)
    if "alembic_version" not in set(inspector.get_table_names()):
        return ()
    rows = sync_conn.execute(text("SELECT version_num FROM alembic_version"))
    return tuple(sorted(str(row[0]) for row in rows if row[0]))


async def verify_database_schema(*, db_engine: AsyncEngine | None = None) -> None:
    """Fail startup unless the target database exactly matches Alembic head.

    This function performs only metadata imports and SELECT/introspection calls.
    It deliberately contains no DDL fallback for development or tests.
    """

    register_all_models()
    expected_heads = get_expected_alembic_heads()
    if len(expected_heads) != 1:
        raise DatabaseSchemaNotReadyError(
            "Active Alembic history must have exactly one head before startup; "
            f"found {list(expected_heads)}."
        )

    target_engine = db_engine or engine
    async with target_engine.connect() as conn:
        current_heads = await conn.run_sync(_read_database_alembic_heads)

    if current_heads != expected_heads:
        raise DatabaseSchemaNotReadyError(
            "Database schema is not at the active Alembic head. "
            f"Expected {list(expected_heads)}, found {list(current_heads)}. "
            "Run `cd backend && alembic upgrade head` before starting the service."
        )

    logger.info(
        "Database schema verified at Alembic head",
        alembic_head=expected_heads[0],
        ddl_executed=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped session with explicit transaction ownership."""

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except (SQLAlchemyError, ValueError):
            await session.rollback()
            raise
        finally:
            await session.close()


def get_database_url() -> str:
    """Return the configured database URL for explicit operational tooling."""

    return DATABASE_URL
