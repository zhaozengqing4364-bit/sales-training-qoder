from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _create_previous_schema(connection: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("user_id", sa.String(36), primary_key=True),
    )
    sa.Table(
        "newcomer_enrollments_v2",
        metadata,
        sa.Column("enrollment_id", sa.String(36), primary_key=True),
    )
    sa.Table(
        "newcomer_activity_attempts_v2",
        metadata,
        sa.Column("attempt_id", sa.String(36), primary_key=True),
    )
    sa.Table(
        "durable_tasks",
        metadata,
        sa.Column("task_id", sa.String(36), primary_key=True),
    )
    metadata.create_all(connection)


def test_structured_coach_migration_creates_single_authoritative_schema(
    tmp_path: Path,
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'structured-coach.db'}")
    with engine.begin() as connection:
        _create_previous_schema(connection)
        script = ScriptDirectory.from_config(Config("alembic.ini"))
        migration = script.get_revision("20260717_0930_004")
        assert migration is not None
        assert migration.down_revision == "20260717_0600_003"
        module = migration.module
        setattr(module, "op", Operations(MigrationContext.configure(connection)))

        module.upgrade()

        inspector = sa.inspect(connection)
        expected_tables = {
            "coach_profile_revisions",
            "coach_sessions",
            "coach_remediation_cycles",
            "coach_turns",
            "coach_training_cards",
            "coach_card_responses",
            "coach_assistances",
            "coach_outcomes",
            "coach_human_interventions",
            "coach_command_audits",
        }
        assert expected_tables <= set(inspector.get_table_names())
        assert {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("coach_sessions")
        } == {("attempt_id",)}
        assert (
            "session_id",
            "checkpoint_index",
            "cycle_no",
        ) in {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("coach_remediation_cycles")
        }
        response_uniques = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("coach_card_responses")
        }
        assert ("card_id",) in response_uniques
        assert ("session_id", "client_token_hash") in response_uniques
        assert {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("coach_outcomes")
        } == {("session_id",)}
        assert {
            item["name"] for item in inspector.get_check_constraints("coach_sessions")
        } >= {
            "ck_coach_session_checkpoint",
            "ck_coach_session_cycle",
            "ck_coach_session_status",
            "ck_coach_session_human_help_status",
        }

        module.downgrade()
        assert expected_tables.isdisjoint(sa.inspect(connection).get_table_names())
