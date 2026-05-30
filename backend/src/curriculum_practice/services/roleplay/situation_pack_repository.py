from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from common.config import settings
from curriculum_practice.services.roleplay.situation_pack_dto import SituationPackDTO


class SituationPackRepository(ABC):
    """Stable interface for SituationPack resolution.

    Callers depend on this interface, not on concrete storage. The async factory
    loads data once; lookup methods stay sync so direct-practice compile paths
    remain pure and testable.

    Runtime authority switch (#96):
    - Default: Phase A (BusinessRuleConfig ruleset)
    - ``SITUATION_PACK_DUAL_READ=true``: shadow Phase B1, serve Phase A
    - Both ``SITUATION_PACK_DUAL_READ`` and ``SITUATION_PACK_B1_AUTHORITY``:
      shadow + serve B1 on hash match; mismatch still logs and falls back to A

    Production gate: enable B1 authority only after dual-read mismatch rate stays
    at zero for at least two weeks (see config-asset-center.md §10 Phase 2.5).
    """

    @classmethod
    async def from_database(cls, db: AsyncSession) -> SituationPackRepository:
        from curriculum_practice.services.roleplay.adapters.business_rule_config_adapter import (
            BusinessRuleConfigSituationPackAdapter,
        )

        phase_a = await BusinessRuleConfigSituationPackAdapter.from_database(db)
        if not settings.SITUATION_PACK_DUAL_READ:
            return phase_a

        from curriculum_practice.services.roleplay.adapters.entity_projection_adapter import (
            EntitySituationPackProjectionAdapter,
        )
        from curriculum_practice.services.roleplay.dual_read_repository import (
            DualReadSituationPackRepository,
        )
        from curriculum_practice.services.roleplay.dual_read_promotion_gate import (
            DualReadPromotionGateService,
            record_dual_read_projection_mismatch_audits,
        )

        phase_b1 = await EntitySituationPackProjectionAdapter.from_database(db)
        await record_dual_read_projection_mismatch_audits(
            db,
            phase_a=phase_a,
            phase_b1=phase_b1,
        )
        promotion_gate = await DualReadPromotionGateService(db).evaluate(
            requested_b1_authority=settings.SITUATION_PACK_B1_AUTHORITY,
            approval_id=settings.SITUATION_PACK_B1_APPROVAL_ID,
            write_audit=settings.SITUATION_PACK_B1_AUTHORITY,
        )
        return DualReadSituationPackRepository(
            phase_a=phase_a,
            phase_b1=phase_b1,
            authority=promotion_gate.authority,
        )

    @classmethod
    def from_defaults(cls) -> SituationPackRepository:
        from curriculum_practice.services.roleplay.adapters.business_rule_config_adapter import (
            BusinessRuleConfigSituationPackAdapter,
        )

        return BusinessRuleConfigSituationPackAdapter.from_builtin_defaults()

    @abstractmethod
    def get_published(self, code: str) -> SituationPackDTO | None:
        """Return published situation pack DTO, or None."""

    @abstractmethod
    def list_published(self) -> list[SituationPackDTO]:
        """Return all published packs."""

    @abstractmethod
    def get_any(self, code: str) -> SituationPackDTO | None:
        """Return pack by code regardless of status."""

    @abstractmethod
    def list_all(self) -> list[SituationPackDTO]:
        """Return all packs regardless of status."""
