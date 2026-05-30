from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


class BusinessRuleConfigSituationPackAdapter(SituationPackRepository):
    """Phase A adapter — reads roleplay.situation_packs.ruleset from BusinessRuleConfig."""

    def __init__(self, packs: dict[str, SituationPackDTO] | None = None) -> None:
        self._packs = packs or _packs_from_ruleset(DEFAULT_ROLEPLAY_SITUATION_PACKS)

    @classmethod
    async def from_database(
        cls,
        db: AsyncSession,
    ) -> BusinessRuleConfigSituationPackAdapter:
        resolution = await BusinessRuleConfigService(db).resolve_active_config(
            ROLEPLAY_SITUATION_PACKS_KEY,
            fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
            fallback_source="bundled_roleplay_situation_packs",
        )
        return cls(_packs_from_ruleset(resolution.value))

    @classmethod
    def from_builtin_defaults(cls) -> BusinessRuleConfigSituationPackAdapter:
        return cls(_packs_from_ruleset(DEFAULT_ROLEPLAY_SITUATION_PACKS))

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


def _packs_from_ruleset(value: dict[str, Any]) -> dict[str, SituationPackDTO]:
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
