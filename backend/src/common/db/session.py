"""
Database session management with async support.

`init_db()` is the startup-time database bootstrap surface. It is intentionally
not the long-term schema evolution authority: Alembic revisions own forward
schema changes, while one-off recovery/bootstrap lives in dedicated scripts.
"""

import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.db.legacy_schema_repair import (
    knowledge_documents_needs_legacy_repair,
    repair_knowledge_document_legacy_schema,
    repair_persona_policy_legacy_schema,
)
from common.monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

STARTUP_DB_AUTHORITY = {
    "startup_initializer": "common.db.session.init_db",
    "startup_table_bootstrap": "Base.metadata.create_all",
    "startup_compatibility_guards": (
        "development/test-only personas.persona_policy compatibility guard",
        "development/test-only knowledge_documents schema compatibility guard",
    ),
    "schema_migration_entrypoint": "cd backend && alembic upgrade head",
    "schema_migration_owner": "backend/alembic/env.py + backend/alembic/versions/*",
    "legacy_schema_repair_entrypoint": (
        "cd backend && python scripts/repair_legacy_schema.py"
    ),
    "auth_bootstrap_entrypoint": (
        "cd backend && python scripts/bootstrap_auth_admin.py "
        "--email <email> --role <role>"
    ),
    "note": (
        "Startup compatibility guards are development/test bootstrap only; "
        "non-development schema drift must be repaired explicitly via Alembic "
        "or scripts/repair_legacy_schema.py."
    ),
}

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/ai_practice",
)

# Determine if using SQLite (for development/testing)
is_sqlite = DATABASE_URL.startswith("sqlite")

# Create engine with appropriate settings for the database type
if is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
    )
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


def _startup_schema_repairs_allowed() -> bool:
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    return env in {"development", "test", "testing"}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session.

    P1-9: Removed implicit auto-commit. Business logic must explicitly
    call session.commit() to control transaction boundaries.
    This prevents accidental commits of incomplete data.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except (SQLAlchemyError, ValueError):
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize mapped tables and run startup-time compatibility guards.

    This function is the startup bootstrap surface only. Alembic remains the
    schema evolution authority, while legacy repair/bootstrap stay in explicit
    scripts so failures can be localized to the right entrypoint.
    """
    from common.db.models import Base

    logger.info(
        "Running startup database bootstrap",
        startup_initializer=STARTUP_DB_AUTHORITY["startup_initializer"],
        startup_table_bootstrap=STARTUP_DB_AUTHORITY["startup_table_bootstrap"],
        startup_compatibility_guards=STARTUP_DB_AUTHORITY[
            "startup_compatibility_guards"
        ],
        schema_migration_entrypoint=STARTUP_DB_AUTHORITY[
            "schema_migration_entrypoint"
        ],
        legacy_schema_repair_entrypoint=STARTUP_DB_AUTHORITY[
            "legacy_schema_repair_entrypoint"
        ],
        auth_bootstrap_entrypoint=STARTUP_DB_AUTHORITY[
            "auth_bootstrap_entrypoint"
        ],
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_persona_policy_column_compatibility)
        await conn.run_sync(_ensure_knowledge_document_schema_compatibility)

    logger.info("Startup database bootstrap finished")


def _ensure_persona_policy_column_compatibility(sync_conn) -> None:
    """
    Ensure `personas.persona_policy` exists for persona-centered policy runtime.

    Development/test startup may apply a local compatibility patch for legacy
    SQLite fixtures. Non-development environments must use Alembic migration
    `20260216_0100_015` or the explicit repair script.
    """
    if _startup_schema_repairs_allowed():
        repair_persona_policy_legacy_schema(
            sync_conn,
            repair_surface="startup bootstrap (development/test)",
        )
        return

    from sqlalchemy import inspect

    inspector = inspect(sync_conn)
    if "personas" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("personas")}
    if "persona_policy" not in columns:
        raise RuntimeError(
            "Detected legacy personas table without personas.persona_policy. "
            "Run Alembic migration 20260216_0100_015 or "
            "python scripts/repair_legacy_schema.py before starting the service."
        )


def _ensure_knowledge_document_schema_compatibility(sync_conn) -> None:
    """
    Ensure knowledge_documents accepts spreadsheet uploads on legacy databases.

    Development/test startup may repair local legacy fixtures. Non-development
    environments must use Alembic migrations `20260225_1000_017` and
    `20260314_1200_018` or the explicit repair script.
    """
    if _startup_schema_repairs_allowed():
        repair_knowledge_document_legacy_schema(
            sync_conn,
            repair_surface="startup bootstrap (development/test)",
        )
        return

    if knowledge_documents_needs_legacy_repair(sync_conn):
        raise RuntimeError(
            "Detected legacy knowledge_documents schema drift. "
            "Run Alembic migrations 20260225_1000_017 and 20260314_1200_018 "
            "or python scripts/repair_legacy_schema.py before starting the service."
        )


def get_database_url() -> str:
    """Get the database URL for creating new connections."""
    return DATABASE_URL
