from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect, text

from common.monitoring.logger import get_logger

logger = get_logger(__name__)


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


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def repair_persona_policy_legacy_schema(
    sync_conn: Any, *, repair_surface: str
) -> bool:
    inspector = inspect(sync_conn)
    if "personas" not in set(inspector.get_table_names()):
        return False

    columns = {column["name"] for column in inspector.get_columns("personas")}
    if "persona_policy" not in columns:
        dialect = str(getattr(sync_conn.dialect, "name", "")).lower()
        if dialect == "postgresql":
            sync_conn.execute(
                text(
                    "ALTER TABLE personas ADD COLUMN IF NOT EXISTS persona_policy JSON"
                )
            )
        else:
            sync_conn.execute(
                text("ALTER TABLE personas ADD COLUMN persona_policy JSON")
            )

    rows = sync_conn.execute(
        text(
            "SELECT id, system_prompt, knowledge_base_ids, persona_policy FROM personas"
        )
    ).mappings()

    repaired = False
    for row in rows:
        existing_policy = _parse_json_dict(row.get("persona_policy"))
        if existing_policy:
            continue

        persona_policy_payload = {
            "version": 1,
            "system_prompt": str(row.get("system_prompt") or "").strip(),
            "knowledge_base_ids": _parse_json_list(row.get("knowledge_base_ids")),
            "tool_policy": {},
        }
        payload = json.dumps(persona_policy_payload, ensure_ascii=False)
        sync_conn.execute(
            text(
                "UPDATE personas SET persona_policy = :payload WHERE id = :persona_id"
            ),
            {"payload": payload, "persona_id": str(row.get("id"))},
        )
        repaired = True

    if "persona_policy" not in columns or repaired:
        logger.info(
            "Legacy personas.persona_policy compatibility repair applied",
            repair_surface=repair_surface,
        )
        return True

    return False


def _index_exists(inspector: Any, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspector.get_indexes(table_name)
    except Exception:
        return False
    return any(index.get("name") == index_name for index in indexes)


def _get_check_constraint_sql(
    sync_conn: Any, table_name: str, constraint_name: str
) -> str:
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


def _rebuild_sqlite_knowledge_documents_table(
    sync_conn: Any, columns: set[str]
) -> None:
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


def knowledge_documents_needs_legacy_repair(sync_conn: Any) -> bool:
    inspector = inspect(sync_conn)
    if "knowledge_documents" not in set(inspector.get_table_names()):
        return False

    columns = {
        column["name"] for column in inspector.get_columns("knowledge_documents")
    }
    file_type_constraint_sql = _get_check_constraint_sql(
        sync_conn,
        "knowledge_documents",
        "ck_knowledge_document_file_type",
    )
    return (
        "content_hash" not in columns
        or not _file_type_constraint_supports_spreadsheets(file_type_constraint_sql)
    )


def repair_knowledge_document_legacy_schema(
    sync_conn: Any, *, repair_surface: str
) -> bool:
    inspector = inspect(sync_conn)
    if "knowledge_documents" not in set(inspector.get_table_names()):
        return False

    columns = {
        column["name"] for column in inspector.get_columns("knowledge_documents")
    }
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
        return False

    if dialect == "sqlite":
        _rebuild_sqlite_knowledge_documents_table(sync_conn, columns)
    else:
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

    logger.info(
        "Legacy knowledge_documents compatibility repair applied",
        repair_surface=repair_surface,
    )
    return True
