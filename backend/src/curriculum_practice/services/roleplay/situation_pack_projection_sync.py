from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.monitoring.logger import get_logger
from curriculum_practice.models import SituationPack
from curriculum_practice.services.orm_payload_typing import set_orm_field
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_hasher import (
    situation_pack_content_hash,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class SituationPackProjectionSyncResult:
    synced_codes: tuple[str, ...]
    created_count: int
    updated_count: int


class SituationPackProjectionSyncService:
    """Write-path sync from ConfigBundle ruleset snapshot to ``situation_packs`` head rows."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def sync_active_published_ruleset(
        self,
        *,
        actor_id: str | None = None,
    ) -> SituationPackProjectionSyncResult:
        resolution = await BusinessRuleConfigService(self._db).resolve_active_config(
            ROLEPLAY_SITUATION_PACKS_KEY,
            fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
            fallback_source="bundled_roleplay_situation_packs",
        )
        return await self.sync_from_ruleset_snapshot(
            resolution.value,
            actor_id=actor_id,
        )

    async def sync_from_ruleset_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        actor_id: str | None = None,
    ) -> SituationPackProjectionSyncResult:
        packs = _packs_from_snapshot(snapshot)
        existing = await self._load_existing_by_code()
        created_count = 0
        updated_count = 0
        synced_codes: list[str] = []

        for code, dto in sorted(packs.items()):
            content_hash = situation_pack_content_hash(dto)
            row = existing.get(code)
            if row is None:
                row = SituationPack(code=code, label=dto.label)
                if actor_id:
                    set_orm_field(row, "created_by", actor_id)
                self._db.add(row)
                created_count += 1
            else:
                updated_count += 1
            _apply_dto_to_row(
                row,
                dto,
                content_hash=content_hash,
                actor_id=actor_id,
            )
            synced_codes.append(code)

        await self._db.flush()
        logger.info(
            "situation_pack_projection_sync_completed",
            bundle_key=ROLEPLAY_SITUATION_PACKS_KEY,
            synced_codes=synced_codes,
            created_count=created_count,
            updated_count=updated_count,
        )
        return SituationPackProjectionSyncResult(
            synced_codes=tuple(synced_codes),
            created_count=created_count,
            updated_count=updated_count,
        )

    async def _load_existing_by_code(self) -> dict[str, SituationPack]:
        result = await self._db.execute(select(SituationPack))
        rows = result.scalars().all()
        return {str(row.code): row for row in rows if row.code}


def _packs_from_snapshot(snapshot: dict[str, Any]) -> dict[str, SituationPackDTO]:
    raw_packs = snapshot.get("packs") if isinstance(snapshot, dict) else None
    if not isinstance(raw_packs, list):
        return {}
    indexed: dict[str, SituationPackDTO] = {}
    for item in raw_packs:
        if not isinstance(item, dict):
            continue
        dto = SituationPackDTO.from_ruleset_entry(item)
        if dto.code:
            indexed[dto.code] = dto
    return indexed


def _apply_dto_to_row(
    row: SituationPack,
    dto: SituationPackDTO,
    *,
    content_hash: str,
    actor_id: str | None,
) -> None:
    set_orm_field(row, "label", dto.label)
    set_orm_field(row, "version", dto.version)
    set_orm_field(row, "status", dto.status)
    set_orm_field(row, "content_hash", content_hash)
    set_orm_field(row, "relationship_context", dict(dto.relationship_context))
    set_orm_field(
        row,
        "visible_information_scope",
        dict(dto.visible_information_scope),
    )
    set_orm_field(
        row,
        "forbidden_claim_patterns",
        list(dto.forbidden_claim_patterns),
    )
    set_orm_field(row, "forbidden_topic_codes", list(dto.forbidden_topic_codes))
    set_orm_field(row, "forbidden_stage_codes", list(dto.forbidden_stage_codes))
    set_orm_field(
        row,
        "conflict_response_strategy",
        dto.conflict_response_strategy,
    )
    set_orm_field(
        row,
        "behavior_rules_for_prompt_only",
        list(dto.behavior_rules_for_prompt_only),
    )
    set_orm_field(row, "disclosure_policy", dict(dto.disclosure_policy))
    set_orm_field(
        row,
        "runtime_violation_policy",
        dict(dto.runtime_violation_policy),
    )
    set_orm_field(
        row,
        "compatible_practice_modes",
        list(dto.compatible_practice_modes),
    )
    set_orm_field(
        row,
        "compatible_scenario_types",
        list(dto.compatible_scenario_types),
    )
    if dto.status == "published":
        if row.published_at is None:
            set_orm_field(row, "published_at", datetime.now(UTC))
    else:
        set_orm_field(row, "published_at", None)
    if actor_id:
        set_orm_field(row, "updated_by", actor_id)
