from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import ConfigVersion
from curriculum_practice.schemas import PublishedAssetRef, PublishedAssetRefSchema
from curriculum_practice.services.asset_references import stable_hash
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)

_SNAPSHOT_SELECTOR_PATTERN = re.compile(r"^(?P<collection>\w+)\[code=(?P<code>[^\]]+)\]$")

ConfigVersionLoader = Callable[[str], Awaitable[dict[str, Any] | None]]
CONFIG_VERSION_RESOLUTION_MODE = "config_version_snapshot"
LEGACY_SOURCE_CONFIG_RESOLUTION_MODE = "legacy_source_config_id_fallback"


class FrozenAssetRefError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def parse_published_asset_refs(
    raw: object | None,
) -> dict[str, PublishedAssetRef]:
    if not isinstance(raw, dict) or not raw:
        return {}
    parsed: dict[str, PublishedAssetRef] = {}
    for key, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        parsed[str(key)] = PublishedAssetRefSchema.model_validate(payload).to_dataclass()
    return parsed


def extract_snapshot_entry(
    snapshot_json: dict[str, Any],
    *,
    selector: str,
) -> dict[str, Any]:
    match = _SNAPSHOT_SELECTOR_PATTERN.match(selector.strip())
    if match is None:
        raise FrozenAssetRefError(
            "snapshot_selector_invalid",
            f"Unsupported snapshot selector {selector!r}.",
        )
    collection_name = match.group("collection")
    code = match.group("code")
    collection = snapshot_json.get(collection_name)
    if not isinstance(collection, list):
        raise FrozenAssetRefError(
            "snapshot_reconstruction_failed",
            f"Snapshot collection {collection_name!r} is missing.",
        )
    for entry in collection:
        if isinstance(entry, dict) and str(entry.get("code") or "").strip() == code:
            return entry
    raise FrozenAssetRefError(
        "situation_pack_missing",
        f"Situation pack {code!r} is missing from frozen snapshot.",
    )


class FrozenSituationPackResolver:
    """Reconstruct SituationPackDTO from immutable ConfigVersion snapshots."""

    def __init__(
        self,
        *,
        config_version_loader: ConfigVersionLoader | None = None,
        legacy_source_config_loader: ConfigVersionLoader | None = None,
    ) -> None:
        self._config_version_loader = config_version_loader
        self._legacy_source_config_loader = legacy_source_config_loader
        self.last_resolution_mode: str | None = None

    @classmethod
    def from_database(cls, db: AsyncSession) -> FrozenSituationPackResolver:
        async def loader(config_version_id: str) -> dict[str, Any] | None:
            result = await db.execute(
                select(ConfigVersion).where(ConfigVersion.version_id == config_version_id)
            )
            version = result.scalar_one_or_none()
            if version is None:
                return None
            snapshot = version.snapshot_json
            return snapshot if isinstance(snapshot, dict) else None

        async def legacy_loader(source_config_id: str) -> dict[str, Any] | None:
            result = await db.execute(
                select(ConfigVersion)
                .where(ConfigVersion.source_config_id == source_config_id)
                .limit(1)
            )
            version = result.scalar_one_or_none()
            if version is None:
                return None
            snapshot = version.snapshot_json
            return snapshot if isinstance(snapshot, dict) else None

        return cls(
            config_version_loader=loader,
            legacy_source_config_loader=legacy_loader,
        )

    async def resolve(self, ref: PublishedAssetRef) -> SituationPackDTO:
        if not ref.can_reconstruct_from_snapshot():
            raise FrozenAssetRefError(
                "snapshot_reconstruction_failed",
                "PublishedAssetRef cannot be reconstructed from snapshot.",
            )
        if self._config_version_loader is None:
            raise FrozenAssetRefError(
                "snapshot_reconstruction_failed",
                "ConfigVersion loader is not configured.",
            )
        self.last_resolution_mode = None
        config_version_id = str(ref.source_config_version_id or "").strip()
        if not config_version_id:
            raise FrozenAssetRefError(
                "snapshot_reconstruction_failed",
                "PublishedAssetRef is missing source_config_version_id.",
            )
        snapshot_json = await self._config_version_loader(config_version_id)
        self.last_resolution_mode = CONFIG_VERSION_RESOLUTION_MODE
        if snapshot_json is None and self._legacy_source_config_loader is not None:
            source_config_id = str(ref.source_config_id or "").strip()
            if source_config_id:
                snapshot_json = await self._legacy_source_config_loader(source_config_id)
                if snapshot_json is not None:
                    self.last_resolution_mode = LEGACY_SOURCE_CONFIG_RESOLUTION_MODE
        if not isinstance(snapshot_json, dict):
            raise FrozenAssetRefError(
                "snapshot_reconstruction_failed",
                f"ConfigVersion snapshot {config_version_id!r} is unavailable.",
            )
        if ref.source_snapshot_hash is not None:
            actual_hash = stable_hash(snapshot_json)
            if actual_hash != ref.source_snapshot_hash:
                raise FrozenAssetRefError(
                    "snapshot_hash_mismatch",
                    "Frozen snapshot hash does not match published ref.",
                )
        entry = extract_snapshot_entry(
            snapshot_json,
            selector=str(ref.snapshot_selector or ""),
        )
        pack = SituationPackDTO.from_ruleset_entry(entry)
        actual_content_hash = situation_pack_content_hash(pack)
        if actual_content_hash != ref.content_hash:
            raise FrozenAssetRefError(
                "asset_hash_mismatch",
                "Frozen SituationPack content hash does not match published ref.",
            )
        return pack
