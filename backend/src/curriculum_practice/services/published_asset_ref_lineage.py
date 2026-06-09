from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PublishedAssetRevisionLineage:
    logical_id: str | None
    revision_id: str | None
    revision_no: int | None


def published_asset_revision_lineage(
    reference: dict[str, Any],
    *,
    fallback_logical_id: str,
) -> PublishedAssetRevisionLineage:
    revision_id = _lineage_revision_id(reference)
    return PublishedAssetRevisionLineage(
        logical_id=str(reference.get("logical_id") or fallback_logical_id)
        if revision_id
        else None,
        revision_id=revision_id,
        revision_no=_lineage_revision_no(reference),
    )


def _lineage_revision_id(reference: dict[str, Any]) -> str | None:
    raw_revision_id = reference.get("revision_id") or reference.get(
        "active_revision_id"
    )
    if isinstance(raw_revision_id, str) and raw_revision_id.strip():
        return raw_revision_id.strip()
    return None


def _lineage_revision_no(reference: dict[str, Any]) -> int | None:
    raw_revision_no = reference.get("revision_no")
    if isinstance(raw_revision_no, int):
        return raw_revision_no
    if isinstance(raw_revision_no, str) and raw_revision_no.isdigit():
        return int(raw_revision_no)
    return None
