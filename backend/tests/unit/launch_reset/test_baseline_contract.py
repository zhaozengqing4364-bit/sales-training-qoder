from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from common.db.model_registry.registration import register_all_models
from common.db.models import Base, User

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_launch_baseline_is_the_only_root_and_platform_revision_is_the_head() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    assert script.get_bases() == ["20260715_0000_001"]
    assert script.get_heads() == ["20260717_1500_006"]
    assert sorted(
        path.name for path in (BACKEND_ROOT / "alembic/versions").glob("*.py")
    ) == [
        "20260715_0000_001_launch_baseline.py",
        "20260717_0103_20260716_2300_002_durable_task_ai_platform.py",
        "20260717_0259_b9fc04c1ad65_newcomer_journey_learning_question_.py",
        "20260717_0600_003_audio_assessment_pipeline.py",
        "20260717_0930_004_structured_ai_coach.py",
        "20260717_1230_005_competency_readiness.py",
        "20260717_1500_006_admin_release_governance.py",
    ]


def test_user_department_is_absent_from_authoritative_metadata_and_baseline() -> None:
    register_all_models()
    assert "department" not in User.__table__.columns
    assert "department" not in Base.metadata.tables["users"].columns

    baseline = (
        BACKEND_ROOT / "alembic/versions/20260715_0000_001_launch_baseline.py"
    ).read_text(encoding="utf-8")
    users_block = baseline.split('op.create_table(\n        "users"', maxsplit=1)[1]
    users_block = users_block.split("op.create_table(", maxsplit=1)[0]
    assert 'sa.Column("department"' not in users_block


def test_prelaunch_history_is_archived_outside_active_versions() -> None:
    archive = BACKEND_ROOT / "alembic/archive/prelaunch_20260715/versions"
    archived_revisions = list(archive.glob("*.py"))

    assert len(archived_revisions) >= 95
    assert (archive.parent / "README.md").is_file()


def test_unsafe_prelaunch_schema_mutation_entrypoints_are_retired() -> None:
    assert not (BACKEND_ROOT / "reset_db.py").exists()
    assert not (BACKEND_ROOT / "scripts/repair_legacy_schema.py").exists()
    assert not (BACKEND_ROOT / "src/common/db/legacy_schema_repair.py").exists()
