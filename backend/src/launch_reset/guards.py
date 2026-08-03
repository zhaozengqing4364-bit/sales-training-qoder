"""Environment, target, and execution-lock guards for destructive apply."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

from launch_reset.errors import ResetSafetyError
from launch_reset.scopes import database_target_fingerprint


def sync_database_url(raw_url: str) -> str:
    parsed = make_url(raw_url)
    driver = parsed.drivername
    if driver.startswith("postgresql+"):
        parsed = parsed.set(drivername="postgresql")
    return parsed.render_as_string(hide_password=False)


def inspect_postgresql_target(raw_url: str, scope: dict[str, Any]) -> dict[str, Any]:
    engine = create_engine(sync_database_url(raw_url), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT current_database() AS database_name, "
                        "current_user AS user_name, "
                        "COALESCE(inet_server_addr()::text, 'local-socket') AS server_address, "
                        "COALESCE(inet_server_port(), 0) AS server_port, "
                        "current_setting('server_version_num') AS server_version_num"
                    )
                )
                .mappings()
                .one()
            )
            table_count = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_type = 'BASE TABLE'"
                ),
                {"schema": scope["schema"]},
            ).scalar_one()
    finally:
        engine.dispose()
    server = {
        "database_name": str(row["database_name"]),
        "user_name_hash": hashlib.sha256(str(row["user_name"]).encode()).hexdigest(),
        "server_address": str(row["server_address"]),
        "server_port": int(row["server_port"]),
        "server_version_major": int(str(row["server_version_num"])) // 10000,
    }
    return {
        "fingerprint": database_target_fingerprint(scope, server),
        "server": server,
        "table_count": int(table_count),
    }


def require_apply_authorization(
    *,
    manifest: dict[str, Any],
    current_fingerprint: str,
    supplied_fingerprint: str,
) -> None:
    environment = str(manifest.get("environment") or "").lower()
    allowed_environments = {
        value.strip().lower()
        for value in os.getenv(
            "LAUNCH_RESET_ALLOWED_ENVIRONMENTS",
            "development,test,testing,internal,staging",
        ).split(",")
        if value.strip()
    }
    if environment in {"production", "prod"} or environment not in allowed_environments:
        raise ResetSafetyError("[RESET_ENVIRONMENT_NOT_ALLOWED]")
    if os.getenv("LAUNCH_RESET_APPLY_ENABLED", "false").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        raise ResetSafetyError("[RESET_APPLY_NOT_ENABLED]")

    database_name = str(manifest["scopes"]["postgresql"]["database"])
    allowed_databases = {
        value.strip()
        for value in os.getenv("LAUNCH_RESET_ALLOWED_DATABASES", "").split(",")
        if value.strip()
    }
    if not allowed_databases or database_name not in allowed_databases:
        raise ResetSafetyError("[RESET_DATABASE_NOT_ALLOWLISTED]")

    expected = str(
        manifest.get("inspection", {}).get("postgresql", {}).get("fingerprint") or ""
    )
    if (
        not expected
        or supplied_fingerprint != expected
        or current_fingerprint != expected
    ):
        raise ResetSafetyError("[RESET_DATABASE_FINGERPRINT_MISMATCH]")


class PostgreSQLRunLock:
    """Session-level advisory lock keyed by the target fingerprint."""

    def __init__(self, raw_url: str, fingerprint: str) -> None:
        self._engine: Engine = create_engine(sync_database_url(raw_url))
        self._connection: Connection | None = None
        self._key = int(fingerprint[:15], 16)

    def __enter__(self) -> PostgreSQLRunLock:
        connection = self._engine.connect()
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": self._key}
        ).scalar_one()
        if not acquired:
            connection.close()
            self._engine.dispose()
            raise ResetSafetyError("[RESET_RUN_ALREADY_ACTIVE]")
        self._connection = connection
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._connection is not None:
            self._connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": self._key}
            )
            self._connection.close()
        self._engine.dispose()


@contextmanager
def null_run_lock() -> Iterator[None]:
    yield None


__all__ = [
    "PostgreSQLRunLock",
    "inspect_postgresql_target",
    "null_run_lock",
    "require_apply_authorization",
    "sync_database_url",
]
