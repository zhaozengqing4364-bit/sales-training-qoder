"""JSON Schema validation for config-asset-export-v1 bundles."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = REPO_ROOT / "docs/architecture/config-asset-export-v1.schema.json"


class ConfigAssetSchemaError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        message = "; ".join(errors[:5])
        if len(errors) > 5:
            message += f" (+{len(errors) - 5} more)"
        super().__init__(f"[CONFIG_ASSET_SCHEMA_INVALID] {message}")
        self.errors = errors


@lru_cache(maxsize=1)
def load_export_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def export_validator() -> Draft202012Validator:
    return Draft202012Validator(load_export_schema())


def validate_export_bundle(bundle: dict[str, Any]) -> None:
    validator = export_validator()
    errors = sorted(validator.iter_errors(bundle), key=lambda item: list(item.path))
    if errors:
        raise ConfigAssetSchemaError([str(error) for error in errors])
