"""Clean database seed/reset helpers for Phase 4 E2E runs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from common.e2e.fixtures import load_versioned_fixture


class _ExecutableSession(Protocol):
    async def execute(self, statement: Any) -> Any: ...


@dataclass(frozen=True)
class Phase4SeedPlan:
    fixture_version: str
    reset_tables: list[str]
    seed_users: list[dict[str, Any]]


def build_seed_plan(fixture_name: str = "db-seed.v1.json") -> Phase4SeedPlan:
    fixture = load_versioned_fixture(fixture_name)
    reset_tables = fixture.get("reset_tables")
    seed_users = fixture.get("seed_users")
    return Phase4SeedPlan(
        fixture_version=str(fixture["fixture_version"]),
        reset_tables=[str(table) for table in reset_tables if isinstance(table, str)]
        if isinstance(reset_tables, list)
        else [],
        seed_users=[dict(user) for user in seed_users if isinstance(user, Mapping)]
        if isinstance(seed_users, list)
        else [],
    )


async def reset_tables_for_clean_e2e_run(
    session: _ExecutableSession,
    table_names: Sequence[str],
    *,
    database_url: str,
) -> list[str]:
    if not _is_safe_e2e_database_url(database_url):
        raise ValueError("Phase 4 E2E reset refused for non-local database URL")

    normalized = sorted({_validate_table_name(table) for table in table_names})
    for table in normalized:
        await session.execute(_sql_text(f'DELETE FROM "{table}"'))
    return normalized


def _is_safe_e2e_database_url(database_url: str) -> bool:
    lowered = database_url.strip().lower()
    return ":memory:" in lowered or "test" in lowered or "e2e" in lowered


def _validate_table_name(table_name: str) -> str:
    normalized = table_name.strip()
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", normalized):
        raise ValueError(f"Invalid E2E reset table name: {table_name}")
    return normalized


def _sql_text(statement: str) -> Any:
    sqlalchemy = __import__("sqlalchemy", fromlist=["text"])
    return sqlalchemy.text(statement)
