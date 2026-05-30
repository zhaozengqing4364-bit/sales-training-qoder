"""Shared types for config asset import/export."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ConflictStrategy = Literal["skip", "fail", "new_version", "replace_draft"]


@dataclass(frozen=True)
class AssetRef:
    asset_type: str
    natural_key: str
    namespace: str = "default"


@dataclass(frozen=True)
class ImportOptions:
    dry_run: bool = False
    conflict_strategy: ConflictStrategy = "new_version"
    publish_after_import: bool = False
    import_reason: str | None = None


@dataclass
class ImportAssetResult:
    asset_type: str
    namespace: str
    natural_key: str
    status: Literal["imported", "skipped", "failed"]
    instance_id: str | None = None
    message: str | None = None


@dataclass
class ImportReport:
    total: int
    imported: int
    skipped: int
    failed: int
    dry_run: bool
    id_mapping: dict[str, str] = field(default_factory=dict)
    results: list[ImportAssetResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    audit_recorded: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "imported": self.imported,
            "skipped": self.skipped,
            "failed": self.failed,
            "dry_run": self.dry_run,
            "id_mapping": dict(self.id_mapping),
            "results": [
                {
                    "asset_type": item.asset_type,
                    "namespace": item.namespace,
                    "natural_key": item.natural_key,
                    "status": item.status,
                    "instance_id": item.instance_id,
                    "message": item.message,
                }
                for item in self.results
            ],
            "errors": list(self.errors),
            "audit_recorded": self.audit_recorded,
        }
