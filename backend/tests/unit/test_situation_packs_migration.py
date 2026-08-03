"""Situation-pack schema contract owned by the first-launch baseline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import UniqueConstraint

from curriculum_practice.models import SituationPack


def _launch_baseline_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20260715_0000_001_launch_baseline.py"
    )


def test_situation_packs_schema_is_owned_by_launch_baseline() -> None:
    migration_path = _launch_baseline_path()
    spec = importlib.util.spec_from_file_location("launch_baseline", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260715_0000_001"
    assert migration.down_revision is None

    table = SituationPack.__table__
    assert set(table.columns.keys()) == {
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
    assert {index.name for index in table.indexes} >= {
        "idx_situation_packs_code",
        "idx_situation_packs_status",
    }
    assert {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    } >= {("code",)}

    source = migration_path.read_text(encoding="utf-8")
    assert 'op.create_table(\n        "situation_packs"' in source
    assert 'op.drop_table("situation_packs")' in source
