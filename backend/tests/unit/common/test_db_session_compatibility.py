from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from common.db.session import _ensure_knowledge_document_schema_compatibility


def test_sqlite_legacy_knowledge_documents_schema_is_upgraded_for_spreadsheets(
    tmp_path,
):
    db_path = tmp_path / "legacy_knowledge.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE knowledge_bases (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(
            text(
                """
                CREATE TABLE knowledge_documents (
                    id VARCHAR(36) PRIMARY KEY,
                    knowledge_base_id VARCHAR(36) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    file_type VARCHAR(20) NOT NULL,
                    file_url VARCHAR(500) NOT NULL,
                    file_size INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT ck_knowledge_document_status
                        CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
                    CONSTRAINT ck_knowledge_document_file_type
                        CHECK (file_type IN ('pdf', 'docx', 'txt', 'md')),
                    FOREIGN KEY(knowledge_base_id) REFERENCES knowledge_bases(id)
                )
                """
            )
        )
        conn.execute(
            text("INSERT INTO knowledge_bases (id) VALUES ('kb-1')")
        )
        conn.execute(
            text(
                """
                INSERT INTO knowledge_documents (
                    id,
                    knowledge_base_id,
                    title,
                    file_type,
                    file_url,
                    file_size,
                    status,
                    chunk_count
                ) VALUES (
                    'doc-1',
                    'kb-1',
                    '旧文档',
                    'docx',
                    '/tmp/doc-1.docx',
                    123,
                    'ready',
                    1
                )
                """
            )
        )

        _ensure_knowledge_document_schema_compatibility(conn)

    with engine.begin() as conn:
        inspector = inspect(conn)
        columns = {column["name"] for column in inspector.get_columns("knowledge_documents")}
        assert "content_hash" in columns

        constraints = inspector.get_check_constraints("knowledge_documents")
        file_type_constraint = next(
            item
            for item in constraints
            if item.get("name") == "ck_knowledge_document_file_type"
        )
        sql_text = str(file_type_constraint.get("sqltext") or "").lower()
        assert "xlsx" in sql_text
        assert "xls" in sql_text

        conn.execute(
            text(
                """
                INSERT INTO knowledge_documents (
                    id,
                    knowledge_base_id,
                    title,
                    file_type,
                    file_url,
                    file_size,
                    status,
                    chunk_count,
                    content_hash
                ) VALUES (
                    'doc-2',
                    'kb-1',
                    '表格文档',
                    'xlsx',
                    '/tmp/doc-2.xlsx',
                    456,
                    'pending',
                    0,
                    'hash-2'
                )
                """
            )
        )

        row_count = conn.execute(
            text("SELECT COUNT(*) FROM knowledge_documents")
        ).scalar_one()
        assert row_count == 2
