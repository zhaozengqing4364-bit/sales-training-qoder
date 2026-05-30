"""Tests for situation_packs Alembic migration upgrade/downgrade."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op as alembic_op
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_migration_module():
    migration_path = (
        _backend_root()
        / "alembic"
        / "versions"
        / "20260527_1100_069_situation_packs.py"
    )
    spec = importlib.util.spec_from_file_location("migration_069", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_with_op_proxy(connection, fn) -> None:
    context = MigrationContext.configure(connection)
    alembic_op._proxy = Operations(context)
    fn()


def test_situation_packs_migration_upgrade_downgrade() -> None:
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            sa.text("CREATE TABLE users (user_id VARCHAR(36) PRIMARY KEY NOT NULL)")
        )

    migration = _load_migration_module()

    with engine.begin() as conn:
        _run_with_op_proxy(conn, migration.upgrade)

    with engine.connect() as conn:
        inspector = inspect(conn)
        assert "situation_packs" in inspector.get_table_names()

        columns = {column["name"] for column in inspector.get_columns("situation_packs")}
        assert columns == {
            "id",
            "code",
            "label",
            "description",
            "version",
            "content_hash",
            "status",
            "relationship_context",
            "visible_information_scope",
            "forbidden_claim_patterns",
            "forbidden_topic_codes",
            "forbidden_stage_codes",
            "conflict_response_strategy",
            "behavior_rules_for_prompt_only",
            "disclosure_policy",
            "runtime_violation_policy",
            "compatible_practice_modes",
            "compatible_scenario_types",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "published_at",
        }

        indexes = {index["name"] for index in inspector.get_indexes("situation_packs")}
        assert "idx_situation_packs_status" in indexes
        assert "idx_situation_packs_code" in indexes

        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("situation_packs")
        }
        assert "uq_situation_packs_code" in unique_constraints

    with engine.begin() as conn:
        _run_with_op_proxy(conn, migration.downgrade)

    with engine.connect() as conn:
        assert "situation_packs" not in inspect(conn).get_table_names()
