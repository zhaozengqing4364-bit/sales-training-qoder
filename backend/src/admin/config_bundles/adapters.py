"""Read-only adapter contract for ConfigBundle snapshots."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import (
    ROLEPLAY_SITUATION_PACKS_KEY,
    SALES_COMBINATION_RULES_KEY,
    SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY,
    BusinessRuleDefinition,
    get_business_rule_definition,
)
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import BusinessRuleConfig, ScoringRuleset
from common.effectiveness.scoring_rulesets import (
    SCORING_RULESETS_BUNDLE_KEY,
    ScoringRulesetService,
    ScoringRulesetView,
)
from configuration_governance.contracts import (
    ConfigBundleAdapter,
    ConfigBundleSnapshot,
    ConfigVersionSnapshot,
)

if TYPE_CHECKING:
    from curriculum_practice.services.roleplay.situation_pack_projection_sync import (
        SituationPackProjectionSyncResult,
    )


class BusinessRuleSalesCombinationConfigBundleAdapter:
    """ConfigBundle adapter for BusinessRuleConfig sales-combination rules."""

    adapter_key = "business_rule_sales_combinations"
    bundle_key = SALES_COMBINATION_RULES_KEY
    display_name = "销售训练组合规则"
    domain = "business_rules"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        definition = service_definition()
        versions = await self.versions(db)
        active = next(
            (item for item in versions if item.status in {"published", "disabled"}),
            versions[0] if versions else None,
        )
        snapshot = active.snapshot if active else {}
        overview = _sales_combination_overview(snapshot)
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain=definition.domain,
            adapter_key=self.adapter_key,
            read_path=definition.read_path,
            admin_entry=definition.admin_entry,
            status=active.status if active else "default",
            overview=overview,
            active_version=active,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        service = BusinessRuleConfigService(db)
        rows = await service.list_configs(key=self.bundle_key)
        if not rows:
            resolution = await service.resolve_active_config(self.bundle_key)
            return [
                ConfigVersionSnapshot(
                    source_config_id=resolution.config_id,
                    version=resolution.version,
                    version_label=_version_label(resolution.value, resolution.version),
                    status=resolution.status or "default",
                    snapshot=deepcopy(resolution.value),
                    created_at=None,
                    updated_at=None,
                )
            ]
        return [_version_from_business_rule_row(row) for row in rows]


class ScoringRulesetBundleAdapter:
    """ConfigBundle adapter for the existing ScoringRuleset governance service."""

    adapter_key = "scoring_rulesets"
    bundle_key = SCORING_RULESETS_BUNDLE_KEY
    display_name = "评分规则集"
    domain = "scoring"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        versions = await self.versions(db)
        active = next(
            (item for item in versions if item.status == "published"),
            versions[0] if versions else None,
        )
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain="evaluation_scoring_rulesets",
            adapter_key=self.adapter_key,
            read_path="/api/v1/evaluation/admin/scoring-rulesets",
            admin_entry="/admin/scoring-rulesets",
            status=active.status if active else "default",
            overview=_scoring_ruleset_overview(versions),
            active_version=active,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        result = await db.execute(
            select(ScoringRuleset).order_by(
                ScoringRuleset.scenario_type,
                ScoringRuleset.created_at.desc(),
            )
        )
        rows = result.scalars().all()
        if rows:
            return [
                _version_from_scoring_ruleset_view(
                    ScoringRulesetService.view_from_model(row)
                )
                for row in rows
            ]
        return [
            _version_from_scoring_ruleset_view(
                ScoringRulesetService.build_default_view("sales")
            ),
            _version_from_scoring_ruleset_view(
                ScoringRulesetService.build_default_view("presentation")
            ),
        ]


class RoleplaySituationPacksConfigBundleAdapter:
    """ConfigBundle adapter for governed Roleplay Situation Packs."""

    adapter_key = "roleplay_situation_packs"
    bundle_key = ROLEPLAY_SITUATION_PACKS_KEY
    display_name = "角色扮演情景包"
    domain = "voice_runtime"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        definition = get_business_rule_definition(self.bundle_key)
        versions = await self.versions(db)
        active = next(
            (item for item in versions if item.status in {"published", "disabled"}),
            versions[0] if versions else None,
        )
        snapshot = active.snapshot if active else {}
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain=definition.domain,
            adapter_key=self.adapter_key,
            read_path=definition.read_path,
            admin_entry=definition.admin_entry,
            status=active.status if active else "default",
            overview=_roleplay_situation_pack_overview(snapshot),
            active_version=active,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        service = BusinessRuleConfigService(db)
        rows = await service.list_configs(key=self.bundle_key)
        if not rows:
            resolution = await service.resolve_active_config(self.bundle_key)
            return [
                ConfigVersionSnapshot(
                    source_config_id=resolution.config_id,
                    version=resolution.version,
                    version_label=_version_label(resolution.value, resolution.version),
                    status=resolution.status or "default",
                    snapshot=deepcopy(resolution.value),
                    created_at=None,
                    updated_at=None,
                )
            ]
        return [_version_from_business_rule_row(row) for row in rows]

    async def sync_head_projection(
        self,
        db: AsyncSession,
        *,
        snapshot: dict[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> SituationPackProjectionSyncResult:
        from curriculum_practice.services.roleplay.situation_pack_projection_sync import (
            SituationPackProjectionSyncService,
        )

        service = SituationPackProjectionSyncService(db)
        if snapshot is not None:
            return await service.sync_from_ruleset_snapshot(
                snapshot,
                actor_id=actor_id,
            )
        return await service.sync_active_published_ruleset(actor_id=actor_id)


class SalesTrainerRealtimeProviderRegistryBundleAdapter:
    """ConfigBundle adapter for the newcomer realtime provider registry."""

    adapter_key = "sales_trainer_realtime_provider_registry"
    bundle_key = SALES_TRAINER_REALTIME_PROVIDER_REGISTRY_KEY
    display_name = "新人训练实时对练 Provider Registry"
    domain = "voice_runtime"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        definition = get_business_rule_definition(self.bundle_key)
        versions = await self.versions(db)
        active = next(
            (item for item in versions if item.status in {"published", "disabled"}),
            versions[0] if versions else None,
        )
        snapshot = active.snapshot if active else {}
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain=definition.domain,
            adapter_key=self.adapter_key,
            read_path=definition.read_path,
            admin_entry=definition.admin_entry,
            status=active.status if active else "default",
            overview=_realtime_provider_registry_overview(snapshot),
            active_version=active,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        service = BusinessRuleConfigService(db)
        rows = await service.list_configs(key=self.bundle_key)
        if not rows:
            resolution = await service.resolve_active_config(self.bundle_key)
            return [
                ConfigVersionSnapshot(
                    source_config_id=resolution.config_id,
                    version=resolution.version,
                    version_label=_version_label(resolution.value, resolution.version),
                    status=resolution.status or "default",
                    snapshot=deepcopy(resolution.value),
                    created_at=None,
                    updated_at=None,
                )
            ]
        return [_version_from_business_rule_row(row) for row in rows]


def service_definition() -> BusinessRuleDefinition:
    from common.business_rules.defaults import get_business_rule_definition

    return get_business_rule_definition(SALES_COMBINATION_RULES_KEY)


def _version_from_business_rule_row(row: BusinessRuleConfig) -> ConfigVersionSnapshot:
    row_any = cast(Any, row)
    value = dict(row_any.value_json or {})
    return ConfigVersionSnapshot(
        source_config_id=str(row_any.id),
        version=int(row_any.version),
        version_label=_version_label(value, int(row_any.version)),
        status=str(row_any.status),
        snapshot=deepcopy(value),
        created_at=row_any.created_at,
        updated_at=row_any.updated_at,
    )


def _version_from_scoring_ruleset_view(
    view: ScoringRulesetView,
) -> ConfigVersionSnapshot:
    return ConfigVersionSnapshot(
        source_config_id=view.ruleset_id,
        version=None,
        version_label=view.version,
        status=view.status,
        snapshot=view.to_dict(),
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _version_label(value: dict[str, Any], version: int | None) -> str:
    raw = value.get("version")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return f"v{version}" if version is not None else "default"


def _sales_combination_overview(snapshot: dict[str, Any]) -> dict[str, Any]:
    combinations = [
        item for item in snapshot.get("combinations", []) if isinstance(item, dict)
    ]
    enabled_count = sum(1 for item in combinations if item.get("enabled", True) is not False)
    return {
        "rule_set_id": snapshot.get("rule_set_id"),
        "combination_count": len(combinations),
        "enabled_combination_count": enabled_count,
        "fallback_policy": snapshot.get("fallback_policy"),
    }


def _scoring_ruleset_overview(
    versions: list[ConfigVersionSnapshot],
) -> dict[str, Any]:
    active_sales = next(
        (
            item
            for item in versions
            if item.status == "published" and item.snapshot.get("scenario_type") == "sales"
        ),
        None,
    )
    active_presentation = next(
        (
            item
            for item in versions
            if item.status == "published"
            and item.snapshot.get("scenario_type") == "presentation"
        ),
        None,
    )
    return {
        "ruleset_count": len(versions),
        "active_sales_version": active_sales.version_label if active_sales else None,
        "active_presentation_version": active_presentation.version_label
        if active_presentation
        else None,
    }


def _roleplay_situation_pack_overview(snapshot: dict[str, Any]) -> dict[str, Any]:
    packs = [item for item in snapshot.get("packs", []) if isinstance(item, dict)]
    published = [
        item for item in packs if str(item.get("status") or "") == "published"
    ]
    return {
        "ruleset_version": snapshot.get("version"),
        "pack_count": len(packs),
        "published_pack_count": len(published),
        "published_codes": sorted(
            str(item.get("code")) for item in published if item.get("code")
        ),
    }


def _realtime_provider_registry_overview(snapshot: dict[str, Any]) -> dict[str, Any]:
    descriptors = [
        item for item in snapshot.get("descriptors", []) if isinstance(item, dict)
    ]
    enabled = [item for item in descriptors if item.get("enabled") is True]
    ready = [
        item
        for item in enabled
        if isinstance(item.get("readiness"), dict)
        and item["readiness"].get("ready") is True
    ]
    return {
        "registry_version": snapshot.get("version"),
        "registry_enabled": snapshot.get("enabled") is True,
        "descriptor_count": len(descriptors),
        "enabled_descriptor_count": len(enabled),
        "ready_descriptor_count": len(ready),
        "descriptor_ids": sorted(
            str(item.get("descriptor_id"))
            for item in descriptors
            if item.get("descriptor_id")
        ),
    }


def list_config_bundle_adapters() -> list[ConfigBundleAdapter]:
    from admin.config_bundles.inventory_adapters import (
        PromptTemplatesConfigBundleAdapter,
        SalesTrainerAiCoachConfigBundleAdapter,
        SalesTrainerPathConfigBundleAdapter,
    )

    return [
        BusinessRuleSalesCombinationConfigBundleAdapter(),
        ScoringRulesetBundleAdapter(),
        RoleplaySituationPacksConfigBundleAdapter(),
        SalesTrainerRealtimeProviderRegistryBundleAdapter(),
        SalesTrainerPathConfigBundleAdapter(),
        SalesTrainerAiCoachConfigBundleAdapter(),
        PromptTemplatesConfigBundleAdapter(),
    ]
