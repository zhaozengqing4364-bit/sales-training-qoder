from __future__ import annotations

from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from common.business_rules.defaults import (
    DEFAULT_ROLEPLAY_SITUATION_PACKS,
    ROLEPLAY_SITUATION_PACKS_KEY,
)
from common.business_rules.service import BusinessRuleConfigService
from curriculum_practice.services.asset_references import CurriculumAssetReferenceReader
from curriculum_practice.services.publishing_gates import PublishingGateService
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)


async def build_practice_template_gate_service(
    db: AsyncSession,
) -> PublishingGateService:
    reference_reader = CurriculumAssetReferenceReader(db).read_publish_gate_reference
    situation_pack_config = await BusinessRuleConfigService(db).resolve_active_config(
        ROLEPLAY_SITUATION_PACKS_KEY,
        fallback_value=DEFAULT_ROLEPLAY_SITUATION_PACKS,
        fallback_source="bundled_roleplay_situation_packs",
    )
    if situation_pack_config.config_id is not None:
        active_version = await ConfigBundleLifecycleService(
            db
        ).resolve_active_version(ROLEPLAY_SITUATION_PACKS_KEY)
        if (
            active_version is not None
            and active_version.source_config_id == situation_pack_config.config_id
        ):
            situation_pack_config = replace(
                situation_pack_config,
                config_version_id=str(active_version.version_id),
            )
    return PublishingGateService(
        reference_reader=reference_reader,
        situation_packs=await SituationPackRepository.from_database(db),
        situation_pack_config=situation_pack_config,
    )
