"""
Database session management with async support.

`init_db()` is the startup-time database bootstrap surface. It is intentionally
not the long-term schema evolution authority: Alembic revisions own forward
schema changes, while one-off recovery/bootstrap lives in dedicated scripts.
"""
import json
import os
from collections.abc import AsyncGenerator
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.monitoring.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

STARTUP_DB_AUTHORITY = {
    "startup_initializer": "common.db.session.init_db",
    "startup_table_bootstrap": "Base.metadata.create_all",
    "startup_compatibility_guards": (
        "personas.persona_policy compatibility guard",
        "knowledge_documents schema compatibility guard",
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
        "Startup compatibility guards are not a substitute for Alembic migrations; "
        "non-development schema drift should be repaired explicitly."
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


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(index.get("name") == index_name for index in indexes)


def _get_check_constraint_sql(sync_conn, table_name: str, constraint_name: str) -> str:
    inspector = inspect(sync_conn)
    try:
        constraints = inspector.get_check_constraints(table_name)
    except Exception:
        return ""

    for constraint in constraints:
        if constraint.get("name") == constraint_name:
            return str(constraint.get("sqltext") or "")
    return ""


def _file_type_constraint_supports_spreadsheets(sql_text: str) -> bool:
    normalized = sql_text.lower()
    return "xlsx" in normalized and "xls" in normalized


def _rebuild_sqlite_knowledge_documents_table(sync_conn, columns: set[str]) -> None:
    logger.warning(
        "Detected legacy knowledge_documents schema in sqlite; "
        "applying local compatibility patch"
    )

    select_expressions = {
        "id": "id",
        "knowledge_base_id": "knowledge_base_id",
        "title": "title",
        "file_type": "file_type",
        "file_url": "file_url",
        "file_size": "file_size",
        "content_hash": "content_hash" if "content_hash" in columns else "NULL",
        "status": "status" if "status" in columns else "'pending'",
        "chunk_count": "chunk_count" if "chunk_count" in columns else "0",
        "error_message": "error_message" if "error_message" in columns else "NULL",
        "created_at": "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP",
    }

    sync_conn.execute(text("PRAGMA foreign_keys=OFF"))
    sync_conn.execute(text("DROP TABLE IF EXISTS knowledge_documents__compat"))
    sync_conn.execute(
        text(
            """
            CREATE TABLE knowledge_documents__compat (
                id VARCHAR(36) PRIMARY KEY,
                knowledge_base_id VARCHAR(36) NOT NULL,
                title VARCHAR(200) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                file_url VARCHAR(500) NOT NULL,
                file_size INTEGER NOT NULL,
                content_hash VARCHAR(64),
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ck_knowledge_document_status
                    CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
                CONSTRAINT ck_knowledge_document_file_type
                    CHECK (file_type IN ('pdf', 'docx', 'txt', 'md', 'xlsx', 'xls')),
                CONSTRAINT uq_knowledge_document_kb_content_hash
                    UNIQUE (knowledge_base_id, content_hash),
                FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
            )
            """
        )
    )
    sync_conn.execute(
        text(
            f"""
            INSERT INTO knowledge_documents__compat (
                id,
                knowledge_base_id,
                title,
                file_type,
                file_url,
                file_size,
                content_hash,
                status,
                chunk_count,
                error_message,
                created_at
            )
            SELECT
                {select_expressions["id"]},
                {select_expressions["knowledge_base_id"]},
                {select_expressions["title"]},
                {select_expressions["file_type"]},
                {select_expressions["file_url"]},
                {select_expressions["file_size"]},
                {select_expressions["content_hash"]},
                {select_expressions["status"]},
                {select_expressions["chunk_count"]},
                {select_expressions["error_message"]},
                {select_expressions["created_at"]}
            FROM knowledge_documents
            """
        )
    )
    sync_conn.execute(text("DROP TABLE knowledge_documents"))
    sync_conn.execute(
        text("ALTER TABLE knowledge_documents__compat RENAME TO knowledge_documents")
    )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status "
            "ON knowledge_documents (status)"
        )
    )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_documents_knowledge_base "
            "ON knowledge_documents (knowledge_base_id)"
        )
    )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_documents_created_at "
            "ON knowledge_documents (created_at)"
        )
    )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_content_hash "
            "ON knowledge_documents (content_hash)"
        )
    )
    sync_conn.execute(text("PRAGMA foreign_keys=ON"))

    logger.info("Startup compatibility patch applied for knowledge_documents in sqlite")


def _ensure_knowledge_document_schema_compatibility(sync_conn) -> None:
    """
    Ensure knowledge_documents accepts spreadsheet uploads on legacy databases.

    This guards against environments where code is upgraded before Alembic
    migrations `20260225_1000_017` and `20260314_1200_018` have been applied.
    """
    inspector = inspect(sync_conn)
    if "knowledge_documents" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("knowledge_documents")}
    dialect = str(getattr(sync_conn.dialect, "name", "")).lower()
    file_type_constraint_sql = _get_check_constraint_sql(
        sync_conn,
        "knowledge_documents",
        "ck_knowledge_document_file_type",
    )

    needs_content_hash = "content_hash" not in columns
    needs_file_type_patch = not _file_type_constraint_supports_spreadsheets(
        file_type_constraint_sql
    )

    if not needs_content_hash and not needs_file_type_patch:
        return

    if dialect == "sqlite":
        _rebuild_sqlite_knowledge_documents_table(sync_conn, columns)
        return

    if needs_content_hash:
        sync_conn.execute(
            text(
                "ALTER TABLE knowledge_documents "
                "ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)"
            )
        )

    refreshed_inspector = inspect(sync_conn)
    if not _index_exists(
        refreshed_inspector,
        "knowledge_documents",
        "ix_knowledge_documents_content_hash",
    ):
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_content_hash "
                "ON knowledge_documents (content_hash)"
            )
        )

    if needs_file_type_patch:
        logger.warning(
            "Detected legacy knowledge_documents.file_type constraint; "
            "applying startup compatibility patch"
        )
        sync_conn.execute(
            text(
                "ALTER TABLE knowledge_documents "
                "DROP CONSTRAINT IF EXISTS ck_knowledge_document_file_type"
            )
        )
        sync_conn.execute(
            text(
                "ALTER TABLE knowledge_documents "
                "ADD CONSTRAINT ck_knowledge_document_file_type "
                "CHECK (file_type IN ('pdf', 'docx', 'txt', 'md', 'xlsx', 'xls'))"
            )
        )

    logger.info("Startup compatibility patch applied for knowledge_documents")


def get_database_url() -> str:
    """Get the database URL for creating new connections."""
    return DATABASE_URL
