"""
Database session management with async support
"""
import json
import os
from collections.abc import AsyncGenerator
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import inspect, text

from common.monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/ai_practice")

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
    """Initialize database and apply critical compatibility guards."""
    from common.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_persona_policy_column_compatibility)


def _parse_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _ensure_persona_policy_column_compatibility(sync_conn) -> None:
    """
    Ensure `personas.persona_policy` exists for persona-centered policy runtime.

    This guards against environments where code is upgraded before Alembic
    migration `20260216_0100_015` has been applied.
    """
    inspector = inspect(sync_conn)
    if "personas" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("personas")}
    if "persona_policy" in columns:
        return

    dialect = str(getattr(sync_conn.dialect, "name", "")).lower()
    if dialect != "sqlite":
        raise RuntimeError(
            "Detected legacy personas table without personas.persona_policy. "
            "Run Alembic migration 20260216_0100_015 before starting the service."
        )

    logger.warning(
        "Detected legacy personas table without persona_policy in sqlite; "
        "applying local compatibility patch"
    )

    sync_conn.execute(text("ALTER TABLE personas ADD COLUMN persona_policy JSON"))

    rows = sync_conn.execute(
        text("SELECT id, system_prompt, knowledge_base_ids FROM personas")
    ).mappings()

    for row in rows:
        persona_policy_payload = {
            "version": 1,
            "system_prompt": str(row.get("system_prompt") or "").strip(),
            "knowledge_base_ids": _parse_json_list(row.get("knowledge_base_ids")),
            "tool_policy": {},
        }
        payload = json.dumps(persona_policy_payload, ensure_ascii=False)
        sync_conn.execute(
            text(
                "UPDATE personas "
                "SET persona_policy = :payload "
                "WHERE id = :persona_id"
            ),
            {"payload": payload, "persona_id": str(row.get("id"))},
        )

    logger.info("Startup compatibility patch applied for personas.persona_policy")


def get_database_url() -> str:
    """Get the database URL for creating new connections."""
    return DATABASE_URL
