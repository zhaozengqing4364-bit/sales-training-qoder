from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from common.config import settings
from curriculum_practice.models import SituationPack
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


class EntitySituationPackProjectionAdapter(SituationPackRepository):
    """Phase B1 adapter skeleton — projection read model.

    Phase 1 does **not** read ``situation_packs`` ORM rows as runtime authority.
    By default ``from_database`` mirrors the ConfigBundle backing store into an
    in-memory projection map. When ``SITUATION_PACK_READ_ORM=true``, the adapter
    loads head rows from ``situation_packs`` for Phase 2 dual-read prep.
    """

    def __init__(self, packs: dict[str, SituationPackDTO] | None = None) -> None:
        self._packs = packs or {}

    @classmethod
    async def from_database(
        cls,
        db: AsyncSession,
    ) -> EntitySituationPackProjectionAdapter:
        if settings.SITUATION_PACK_READ_ORM:
            adapter = await cls._from_orm(db)
            resolution = await BusinessRuleConfigService(db).resolve_active_config(
                ROLEPLAY_SITUATION_PACKS_KEY,
                fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
                fallback_source="bundled_roleplay_situation_packs",
            )
            source_packs = _packs_from_projection_mirror(resolution.value)
            return cls(
                {
                    code: replace(
                        pack,
                        initial_stage_hint=source.initial_stage_hint,
                        stage_transition_notes=source.stage_transition_notes,
                    )
                    if (source := source_packs.get(code)) is not None
                    else pack
                    for code, pack in adapter._packs.items()
                }
            )
        resolution = await BusinessRuleConfigService(db).resolve_active_config(
            ROLEPLAY_SITUATION_PACKS_KEY,
            fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
            fallback_source="bundled_roleplay_situation_packs",
        )
        return cls(_packs_from_projection_mirror(resolution.value))

    @classmethod
    async def _from_orm(cls, db: AsyncSession) -> EntitySituationPackProjectionAdapter:
        result = await db.execute(select(SituationPack))
        rows = result.scalars().all()
        indexed = {
            str(row.code): SituationPackDTO.from_entity(row)
            for row in rows
            if row.code
        }
        return cls(indexed)

    @classmethod
    def from_in_memory(
        cls,
        packs: dict[str, SituationPackDTO],
    ) -> EntitySituationPackProjectionAdapter:
        return cls(dict(packs))

    def get_published(self, code: str) -> SituationPackDTO | None:
        pack = self._packs.get(code)
        if pack is None or pack.status != "published":
            return None
        return pack

    def list_published(self) -> list[SituationPackDTO]:
        return [pack for pack in self._packs.values() if pack.status == "published"]

    def get_any(self, code: str) -> SituationPackDTO | None:
        return self._packs.get(code)

    def list_all(self) -> list[SituationPackDTO]:
        return list(self._packs.values())


def _packs_from_projection_mirror(value: dict[str, Any]) -> dict[str, SituationPackDTO]:
    packs = value.get("packs") if isinstance(value, dict) else None
    if not isinstance(packs, list):
        return {}
    indexed: dict[str, SituationPackDTO] = {}
    for item in packs:
        if not isinstance(item, dict):
            continue
        dto = SituationPackDTO.from_ruleset_entry(item)
        if dto.code:
            indexed[dto.code] = dto
    return indexed
