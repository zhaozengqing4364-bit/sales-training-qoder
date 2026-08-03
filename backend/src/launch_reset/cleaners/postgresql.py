"""PostgreSQL schema cleaner; database deletion is intentionally unsupported."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text

from launch_reset.errors import ResetSafetyError
from launch_reset.guards import inspect_postgresql_target, sync_database_url

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PostgreSQLCleaner:
    name = "postgresql"

    def __init__(self, raw_url: str, scope: dict[str, Any]) -> None:
        self.raw_url = raw_url
        self.scope = scope
        self.schema = str(scope["schema"])
        if not _IDENTIFIER.fullmatch(self.schema):
            raise ResetSafetyError("[RESET_POSTGRES_SCHEMA_INVALID]")

    async def inspect(self) -> dict[str, Any]:
        target = inspect_postgresql_target(self.raw_url, self.scope)
        engine = create_engine(sync_database_url(self.raw_url))
        try:
            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT relname, n_live_tup FROM pg_stat_user_tables "
                        "WHERE schemaname = :schema ORDER BY relname"
                    ),
                    {"schema": self.schema},
                ).mappings()
                tables = [
                    {
                        "name": str(row["relname"]),
                        "estimated_rows": int(row["n_live_tup"]),
                    }
                    for row in rows
                ]
        finally:
            engine.dispose()
        return {**target, "tables": tables}

    async def apply(self) -> dict[str, Any]:
        engine = create_engine(
            sync_database_url(self.raw_url), isolation_level="AUTOCOMMIT"
        )
        quoted_schema = f'"{self.schema}"'
        try:
            with engine.connect() as connection:
                connection.execute(
                    text(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
                )
                connection.execute(text(f"CREATE SCHEMA {quoted_schema}"))
        finally:
            engine.dispose()
        verification = await self.verify()
        if not verification["clean"]:
            raise ResetSafetyError("[RESET_POSTGRES_CLEAN_VERIFY_FAILED]")
        return {"schema": self.schema, "clean": True}

    async def verify(self) -> dict[str, Any]:
        engine = create_engine(sync_database_url(self.raw_url))
        try:
            with engine.connect() as connection:
                count = connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema = :schema AND table_type = 'BASE TABLE'"
                    ),
                    {"schema": self.schema},
                ).scalar_one()
        finally:
            engine.dispose()
        return {
            "schema": self.schema,
            "table_count": int(count),
            "clean": int(count) == 0,
        }


__all__ = ["PostgreSQLCleaner"]
