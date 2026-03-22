"""
Repair legacy deployment schema drift for production-like environments.

Usage:
    python scripts/repair_legacy_schema.py
    python scripts/repair_legacy_schema.py --stamp-revision 20260314_1200_018
    python scripts/repair_legacy_schema.py --database-url postgresql+asyncpg://...

This script is intended for environments that were created outside Alembic and
need a one-time compatibility repair plus optional alembic_version bootstrap.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from common.db.session import _ensure_knowledge_document_schema_compatibility
from common.monitoring.logger import configure_logging, get_logger

load_dotenv()
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


def _to_sync_database_url(database_url: str) -> str:
    return (
        database_url.replace("+asyncpg", "+psycopg2")
        .replace("+aiosqlite", "")
        .strip()
    )


def _revision_exists(revision: str) -> bool:
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    return any(path.name.startswith(revision) for path in versions_dir.glob("*.py"))


def _table_exists(sync_conn, table_name: str) -> bool:
    inspector = inspect(sync_conn)
    return table_name in set(inspector.get_table_names())


def _bootstrap_alembic_version(sync_conn, revision: str) -> None:
    if not _revision_exists(revision):
        raise RuntimeError(f"Unknown Alembic revision: {revision}")

    if not _table_exists(sync_conn, "alembic_version"):
        sync_conn.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        sync_conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )
        logger.info("Bootstrapped alembic_version table", revision=revision)
        return

    existing_rows = sync_conn.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalars().all()

    if len(existing_rows) > 1:
        raise RuntimeError(
            "Multiple alembic_version rows detected. Refusing automatic rewrite."
        )

    if not existing_rows:
        sync_conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )
        logger.info("Inserted alembic revision", revision=revision)
        return

    current_revision = str(existing_rows[0]).strip()
    if current_revision == revision:
        logger.info("Alembic revision already matches target", revision=revision)
        return

    sync_conn.execute(
        text("UPDATE alembic_version SET version_num = :revision"),
        {"revision": revision},
    )
    logger.warning(
        "Updated alembic_version revision",
        from_revision=current_revision,
        to_revision=revision,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair legacy schema drift and optionally bootstrap Alembic state."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "").strip(),
        help="Database URL. Defaults to DATABASE_URL from environment.",
    )
    parser.add_argument(
        "--stamp-revision",
        default="",
        help="Optional Alembic revision to write into alembic_version.",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise RuntimeError("DATABASE_URL is required")

    sync_database_url = _to_sync_database_url(args.database_url)
    logger.info(
        "Running legacy schema repair",
        stamp_revision=args.stamp_revision or None,
    )

    engine = create_engine(sync_database_url, poolclass=NullPool)
    try:
        with engine.begin() as sync_conn:
            _ensure_knowledge_document_schema_compatibility(sync_conn)
            if args.stamp_revision:
                _bootstrap_alembic_version(sync_conn, args.stamp_revision.strip())
    finally:
        engine.dispose()

    logger.info("Legacy schema repair finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
