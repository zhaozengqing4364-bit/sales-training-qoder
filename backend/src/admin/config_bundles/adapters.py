"""Read-only adapter contract for ConfigBundle snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.business_rules.defaults import SALES_COMBINATION_RULES_KEY
from common.business_rules.service import BusinessRuleConfigService
from common.db.models import BusinessRuleConfig, ScoringRuleset
from common.effectiveness.scoring_rulesets import (
    SCORING_RULESETS_BUNDLE_KEY,
    ScoringRulesetService,
    ScoringRulesetView,
)


@dataclass(frozen=True)
class ConfigVersionSnapshot:
    source_config_id: str | None
    version: int | None
    version_label: str
    status: str
    snapshot: dict[str, Any]
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class ConfigBundleSnapshot:
    bundle_key: str
    display_name: str
    domain: str
    legacy_domain: str
    adapter_key: str
    read_path: str
    admin_entry: str
    status: str
    overview: dict[str, Any]
    active_version: ConfigVersionSnapshot | None


class ConfigBundleAdapter(Protocol):
    """Read-only adapter that exposes legacy config as ConfigBundle snapshots."""

    adapter_key: str
    bundle_key: str

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        """Return one bundle overview without mutating legacy config."""
        ...

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        """Return version snapshots without mutating legacy config."""
        ...


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


def service_definition():
    from common.business_rules.defaults import get_business_rule_definition

    return get_business_rule_definition(SALES_COMBINATION_RULES_KEY)


def _version_from_business_rule_row(row: BusinessRuleConfig) -> ConfigVersionSnapshot:
    value = dict(row.value_json or {})
    return ConfigVersionSnapshot(
        source_config_id=str(row.id),
        version=int(row.version),
        version_label=_version_label(value, int(row.version)),
        status=str(row.status),
        snapshot=deepcopy(value),
        created_at=row.created_at,
        updated_at=row.updated_at,
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


def list_config_bundle_adapters() -> list[ConfigBundleAdapter]:
    return [
        BusinessRuleSalesCombinationConfigBundleAdapter(),
        ScoringRulesetBundleAdapter(),
    ]
