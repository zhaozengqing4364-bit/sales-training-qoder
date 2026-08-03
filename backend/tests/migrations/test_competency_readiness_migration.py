from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def test_competency_readiness_migration_creates_and_removes_authoritative_schema(
    tmp_path: Path,
) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'competency-readiness.db'}")
    with engine.begin() as connection:
        script = ScriptDirectory.from_config(Config("alembic.ini"))
        migration = script.get_revision("20260717_1230_005")
        assert migration is not None
        assert migration.down_revision == "20260717_0930_004"
        module = migration.module
        setattr(module, "op", Operations(MigrationContext.configure(connection)))

        module.upgrade()

        inspector = sa.inspect(connection)
        expected_tables = {
            "canonical_competencies",
            "canonical_competency_revisions",
            "competency_mappings",
            "competency_evidence_records",
            "competency_evidence_validity_events",
            "readiness_policy_revisions",
            "readiness_dossiers",
            "readiness_dossier_snapshots",
            "readiness_review_decisions",
            "readiness_exception_previews",
            "readiness_retraining_assignments",
            "readiness_appeals",
            "readiness_calibration_sessions",
            "readiness_ai_summaries",
            "readiness_command_audits",
        }
        assert expected_tables <= set(inspector.get_table_names())
        assert ("organization_id", "enrollment_id") in {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints("readiness_dossiers")
        }
        assert (
            "organization_id",
            "outcome_id",
            "outcome_version",
            "competency_revision_id",
        ) in {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints(
                "competency_evidence_records"
            )
        }
        assert {
            item["name"]
            for item in inspector.get_check_constraints("readiness_review_decisions")
        } >= {"ck_readiness_decision_status", "ck_readiness_decision_type"}

        module.downgrade()
        assert expected_tables.isdisjoint(sa.inspect(connection).get_table_names())
