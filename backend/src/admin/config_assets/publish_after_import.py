"""Publish imported assets through ConfigBundle or native lifecycle paths."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_assets.natural_keys import asset_identity, topology_ref
from admin.config_assets.types import ImportAssetResult
from admin.config_bundles.lifecycle import ConfigBundleLifecycleService
from common.business_rules.defaults import ROLEPLAY_SITUATION_PACKS_KEY
from common.db.models import BusinessRuleConfig
from curriculum_practice.models import PracticeTemplate
from curriculum_practice.services.practice_templates import PracticeTemplateService


async def publish_imported_assets(
    db: AsyncSession,
    *,
    assets: list[dict[str, Any]],
    results: list[ImportAssetResult],
    id_mapping: dict[str, str],
    actor_id: str,
    import_reason: str | None,
) -> list[str]:
    """Publish assets whose export entries were marked ``status=published``.

    ConfigBundle-governed assets use ConfigBundle lifecycle publish.
    Native lifecycle assets use their respective service publish paths.
    """
    errors: list[str] = []
    entries_by_ref = {
        topology_ref(str(item["asset_type"]), str(item["natural_key"])): item
        for item in assets
    }
    lifecycle = ConfigBundleLifecycleService(db)
    publish_reason = import_reason or "config_asset_import:publish_after_import"

    for result in results:
        if result.status != "imported":
            continue
        ref = topology_ref(result.asset_type, result.natural_key)
        entry = entries_by_ref.get(ref)
        if entry is None:
            errors.append(f"[PUBLISH_MISSING_ENTRY] {ref}")
            continue
        if str(entry.get("status") or "draft") != "published":
            continue

        governance = str(entry.get("governance") or "native_lifecycle")
        if governance == "config_bundle":
            bundle_key = str(
                entry.get("source_bundle_key") or ROLEPLAY_SITUATION_PACKS_KEY
            )
            draft = await _latest_draft_for_bundle(db, bundle_key)
            if draft is None:
                errors.append(
                    f"[PUBLISH_NO_DRAFT] {result.asset_type}:{result.natural_key}"
                )
                continue
            value = dict(getattr(draft, "value_json") or {})
            try:
                await lifecycle.validate(
                    bundle_key=bundle_key,
                    value=value,
                    actor_id=actor_id,
                    reason=publish_reason,
                )
                await lifecycle.publish(
                    bundle_key=bundle_key,
                    actor_id=actor_id,
                    config_id=str(getattr(draft, "id")),
                    reason=publish_reason,
                )
            except Exception as exc:  # noqa: BLE001 — collect per-asset failure
                errors.append(
                    f"[PUBLISH_CONFIG_BUNDLE_FAILED] {ref}: {exc}"
                )
            continue

        if result.asset_type == "practice_template":
            template_id = result.instance_id or id_mapping.get(
                asset_identity(
                    result.asset_type,
                    result.natural_key,
                    result.namespace,
                )
            )
            if not template_id:
                errors.append(f"[PUBLISH_MISSING_TEMPLATE_ID] {ref}")
                continue
            template = await db.get(PracticeTemplate, template_id)
            if template is None:
                errors.append(f"[PUBLISH_TEMPLATE_NOT_FOUND] {ref}")
                continue
            published, decision = await PracticeTemplateService(db).publish_template(
                template,
                actor_id=actor_id,
            )
            if published is None:
                gate_errors = [
                    gate.message
                    for gate in decision.results
                    if gate.status == "failed"
                ]
                detail = "; ".join(gate_errors) or "publish gate rejected template"
                errors.append(f"[PUBLISH_TEMPLATE_GATE_FAILED] {ref}: {detail}")

    return errors


async def _latest_draft_for_bundle(
    db: AsyncSession,
    bundle_key: str,
) -> BusinessRuleConfig | None:
    result = await db.execute(
        select(BusinessRuleConfig)
        .where(
            BusinessRuleConfig.key == bundle_key,
            BusinessRuleConfig.status == "draft",
        )
        .order_by(
            BusinessRuleConfig.version.desc(),
            BusinessRuleConfig.updated_at.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()
