"""Validate config-asset-export-v1 fixture against architecture JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "docs/architecture/config-asset-export-v1.schema.json"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures/config_asset_export_v1_example.json"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def export_schema() -> dict[str, object]:
    return _load_json(SCHEMA_PATH)


@pytest.fixture(scope="module")
def export_validator(export_schema: dict[str, object]) -> Draft202012Validator:
    return Draft202012Validator(export_schema)


@pytest.fixture(scope="module")
def example_export() -> dict[str, object]:
    return _load_json(FIXTURE_PATH)


def test_should_validate_example_fixture_against_export_schema(
    export_validator: Draft202012Validator,
    example_export: dict[str, object],
) -> None:
    errors = sorted(export_validator.iter_errors(example_export), key=lambda e: e.path)
    assert not errors, "\n".join(str(error) for error in errors)


def test_should_include_required_asset_types_in_example(
    example_export: dict[str, object],
) -> None:
    asset_types = {
        str(entry["asset_type"])
        for entry in example_export["assets"]  # type: ignore[index]
    }
    assert {"persona", "situation_pack", "practice_template"}.issubset(asset_types)


def test_should_align_topology_order_with_exported_natural_keys(
    example_export: dict[str, object],
) -> None:
    assets = example_export["assets"]  # type: ignore[index]
    asset_refs = {
        f"{entry['asset_type']}:{entry['natural_key']}" for entry in assets  # type: ignore[index]
    }
    topology = example_export["topology_order"]  # type: ignore[index]
    assert set(topology) == asset_refs
    assert topology == [
        "knowledge_base:presales-cio-first-visit-kb",
        "situation_pack:first_visit",
        "persona:manufacturing-cio-first-visit",
        "practice_template:cio-first-visit-loop",
    ]
