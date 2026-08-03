from __future__ import annotations

from datetime import UTC, datetime

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
    attempts = sa.Table(
        "newcomer_activity_attempts_v2",
        metadata,
        sa.Column("attempt_id", sa.String(36), primary_key=True),
    )
    sa.Table(
        "durable_tasks",
        metadata,
        sa.Column("task_id", sa.String(36), primary_key=True),
    )
    sa.Table(
        "newcomer_activity_outcomes",
        metadata,
        sa.Column("outcome_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(120), nullable=False),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey(attempts.c.attempt_id, ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("result_fingerprint", sa.String(64), nullable=False),
        sa.Column("lifecycle_result", sa.String(32), nullable=False),
        sa.Column("assessment_result", sa.String(32)),
        sa.Column("score", sa.Numeric(10, 4)),
        sa.Column("max_score", sa.Numeric(10, 4)),
        sa.Column("passed", sa.Boolean),
        sa.Column("competency_evidence_refs_json", sa.JSON, nullable=False),
        sa.Column("source_refs_json", sa.JSON, nullable=False),
        sa.Column("lineage_json", sa.JSON, nullable=False),
        sa.Column("confidence", sa.Numeric(6, 5)),
        sa.Column("critical_flags_json", sa.JSON, nullable=False),
        sa.Column("degradations_json", sa.JSON, nullable=False),
        sa.Column("next_action_json", sa.JSON),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(connection)


def test_audio_migration_upgrades_outcomes_and_creates_durable_tables(
    tmp_path,
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'audio-migration.db'}")
    with engine.begin() as connection:
        _create_previous_schema(connection)
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        migration = script.get_revision("20260717_0600_003")
        assert migration is not None
        module = migration.module
        module.op = Operations(MigrationContext.configure(connection))

        module.upgrade()

        inspector = sa.inspect(connection)
        expected_tables = {
            "audio_activity_resource_revisions",
            "audio_activity_runs",
            "audio_submissions_v2",
            "audio_upload_sessions",
            "audio_upload_parts",
            "audio_artifacts",
            "audio_transcript_revisions",
            "audio_quality_reports",
            "audio_score_outcome_versions",
            "audio_command_audits",
            "audio_change_previews",
        }
        assert expected_tables <= set(inspector.get_table_names())
        outcome_columns = {
            item["name"] for item in inspector.get_columns("newcomer_activity_outcomes")
        }
        assert "supersedes_outcome_id" in outcome_columns
        unique_columns = {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("newcomer_activity_outcomes")
        }
        assert ("attempt_id",) not in unique_columns
        assert ("attempt_id", "version") in unique_columns
        assert (
            "organization_id",
            "attempt_id",
            "idempotency_key_hash",
        ) in unique_columns

        now = datetime.now(UTC)
        connection.execute(
            sa.text(
                "INSERT INTO newcomer_activity_attempts_v2 (attempt_id) "
                "VALUES ('attempt-1')"
            )
        )
        payload = {
            "organization_id": "org-1",
            "attempt_id": "attempt-1",
            "result_fingerprint": "f" * 64,
            "lifecycle_result": "completed",
            "assessment_result": "passed",
            "competency_evidence_refs_json": "[]",
            "source_refs_json": "[]",
            "lineage_json": "{}",
            "critical_flags_json": "[]",
            "degradations_json": "[]",
            "produced_at": now,
        }
        for version in (1, 2):
            connection.execute(
                sa.text(
                    "INSERT INTO newcomer_activity_outcomes ("
                    "outcome_id, organization_id, attempt_id, "
                    "idempotency_key_hash, result_fingerprint, lifecycle_result, "
                    "assessment_result, competency_evidence_refs_json, "
                    "source_refs_json, lineage_json, critical_flags_json, "
                    "degradations_json, version, produced_at, supersedes_outcome_id"
                    ") VALUES ("
                    ":outcome_id, :organization_id, :attempt_id, :idempotency_key_hash, "
                    ":result_fingerprint, :lifecycle_result, :assessment_result, "
                    ":competency_evidence_refs_json, :source_refs_json, :lineage_json, "
                    ":critical_flags_json, :degradations_json, :version, "
                    ":produced_at, :supersedes_outcome_id)"
                ),
                {
                    **payload,
                    "outcome_id": f"outcome-{version}",
                    "idempotency_key_hash": str(version) * 64,
                    "version": version,
                    "supersedes_outcome_id": ("outcome-1" if version == 2 else None),
                },
            )

        count = connection.scalar(
            sa.text(
                "SELECT COUNT(*) FROM newcomer_activity_outcomes "
                "WHERE attempt_id = 'attempt-1'"
            )
        )
        assert count == 2
