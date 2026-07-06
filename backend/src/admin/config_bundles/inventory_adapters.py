from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.adapters import ConfigBundleSnapshot, ConfigVersionSnapshot
from common.db.models import PromptTemplate as PromptTemplateRow
from sales_trainer.models import SalesTrainerAssetRevision
from sales_trainer.services.asset_revision_service import (
    SalesTrainerAssetRevisionService,
)
from sales_trainer.services.path_config_models import (
    NEWCOMER_PATH_LOGICAL_ID,
    NEWCOMER_PATH_RESOURCE_TYPE,
    payload_from_revision,
)

NEWCOMER_PATH_CONFIG_BUNDLE_KEY = "sales_trainer.newcomer_path_config"
AI_COACH_CONFIG_BUNDLE_KEY = "sales_trainer.ai_coach_config"
PROMPT_TEMPLATES_BUNDLE_KEY = "prompt_templates"


class SalesTrainerPathConfigBundleAdapter:
    adapter_key = "sales_trainer_path_config"
    bundle_key = NEWCOMER_PATH_CONFIG_BUNDLE_KEY
    display_name = "新人训练路径配置"
    domain = "business_rules"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        service = SalesTrainerAssetRevisionService(db)
        active = await service.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await service.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active_version = _path_version(active) if active is not None else None
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain="sales_trainer_asset_revision",
            adapter_key=self.adapter_key,
            read_path="/api/v1/admin/newcomer-training/path-config",
            admin_entry="/admin/sales-trainer/paths",
            status=(
                str(active.status)
                if active is not None
                else str(working.status)
                if working is not None
                else "default"
            ),
            overview=_path_overview(active=active, working=working),
            active_version=active_version,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        revisions = await SalesTrainerAssetRevisionService(db).list_revisions(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        return [_path_version(revision) for revision in revisions]


class SalesTrainerAiCoachConfigBundleAdapter:
    adapter_key = "sales_trainer_ai_coach_config"
    bundle_key = AI_COACH_CONFIG_BUNDLE_KEY
    display_name = "商务技巧 AI Coach 配置"
    domain = "ai_analysis"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        service = SalesTrainerAssetRevisionService(db)
        active = await service.active_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        working = await service.latest_working_revision(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        active_version = _ai_coach_version(active) if active is not None else None
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain="sales_trainer_asset_revision.ai_coach",
            adapter_key=self.adapter_key,
            read_path="/api/v1/admin/newcomer-training/ai-coach/business_skills",
            admin_entry="/admin/sales-trainer/ai-coach",
            status=(
                str(active.status)
                if active is not None
                else str(working.status)
                if working is not None
                else "default"
            ),
            overview=_ai_coach_overview(active=active, working=working),
            active_version=active_version,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        revisions = await SalesTrainerAssetRevisionService(db).list_revisions(
            resource_type=NEWCOMER_PATH_RESOURCE_TYPE,
            logical_id=NEWCOMER_PATH_LOGICAL_ID,
        )
        return [_ai_coach_version(revision) for revision in revisions]


class PromptTemplatesConfigBundleAdapter:
    adapter_key = "prompt_templates"
    bundle_key = PROMPT_TEMPLATES_BUNDLE_KEY
    display_name = "Prompt 模板"
    domain = "ai_analysis"

    async def bundle(self, db: AsyncSession) -> ConfigBundleSnapshot:
        versions = await self.versions(db)
        active = next((item for item in versions if item.status == "published"), None)
        return ConfigBundleSnapshot(
            bundle_key=self.bundle_key,
            display_name=self.display_name,
            domain=self.domain,
            legacy_domain="prompt_templates",
            adapter_key=self.adapter_key,
            read_path="/api/v1/prompt-templates",
            admin_entry="/admin/prompts",
            status=active.status if active is not None else "default",
            overview=_prompt_template_overview(versions),
            active_version=active,
        )

    async def versions(self, db: AsyncSession) -> list[ConfigVersionSnapshot]:
        result = await db.execute(
            select(PromptTemplateRow).order_by(
                PromptTemplateRow.prompt_type,
                PromptTemplateRow.name,
            )
        )
        return [_prompt_template_version(row) for row in result.scalars().all()]


def _path_version(revision: SalesTrainerAssetRevision) -> ConfigVersionSnapshot:
    payload = payload_from_revision(revision)
    return ConfigVersionSnapshot(
        source_config_id=str(revision.revision_id),
        version=int(revision.revision_no),
        version_label=f"v{revision.revision_no}",
        status=str(revision.status),
        snapshot=payload.model_dump(mode="json"),
        created_at=_datetime_or_none(revision.created_at),
        updated_at=_datetime_or_none(revision.published_at),
    )


def _ai_coach_version(revision: SalesTrainerAssetRevision) -> ConfigVersionSnapshot:
    payload = payload_from_revision(revision)
    return ConfigVersionSnapshot(
        source_config_id=str(revision.revision_id),
        version=int(revision.revision_no),
        version_label=f"v{revision.revision_no}",
        status=str(revision.status),
        snapshot={
            "path_key": payload.path_key,
            "modules": [
                {
                    "module_key": module.module_key,
                    "ai_coach": module.ai_coach.model_dump(mode="json")
                    if module.ai_coach
                    else None,
                }
                for module in payload.modules
            ],
        },
        created_at=_datetime_or_none(revision.created_at),
        updated_at=_datetime_or_none(revision.published_at),
    )


def _path_overview(
    *,
    active: SalesTrainerAssetRevision | None,
    working: SalesTrainerAssetRevision | None,
) -> dict[str, Any]:
    active_payload = payload_from_revision(active) if active is not None else None
    return {
        "logical_id": NEWCOMER_PATH_LOGICAL_ID,
        "resource_type": NEWCOMER_PATH_RESOURCE_TYPE,
        "backing_store": "SalesTrainerAssetRevision",
        "active_revision_id": str(active.revision_id) if active is not None else None,
        "active_revision_no": active.revision_no if active is not None else None,
        "working_revision_id": str(working.revision_id) if working is not None else None,
        "working_revision_no": working.revision_no if working is not None else None,
        "module_count": len(active_payload.modules) if active_payload is not None else 0,
        "permission": "sales_trainer.manage_modules",
        "audit_carrier": "SalesTrainerOperationLog",
    }


def _ai_coach_overview(
    *,
    active: SalesTrainerAssetRevision | None,
    working: SalesTrainerAssetRevision | None,
) -> dict[str, Any]:
    active_payload = payload_from_revision(active) if active is not None else None
    modules = active_payload.modules if active_payload is not None else []
    return {
        "logical_id": "business_skills_ai_coach",
        "backing_store": "SalesTrainerAssetRevision.path.modules.ai_coach",
        "active_revision_id": str(active.revision_id) if active is not None else None,
        "working_revision_id": str(working.revision_id) if working is not None else None,
        "configured_module_count": sum(1 for module in modules if module.ai_coach is not None),
        "high_risk_permission": "sales_trainer.manage_prompts",
        "audit_carrier": "SalesTrainerOperationLog",
    }


def _prompt_template_version(row: PromptTemplateRow) -> ConfigVersionSnapshot:
    variables: list[Any] = row.variables if isinstance(row.variables, list) else []
    snapshot = {
        "template_id": str(row.id),
        "name": row.name,
        "prompt_type": row.prompt_type,
        "business_purpose": row.business_purpose,
        "category": row.category,
        "variables": deepcopy(variables),
        "is_active": bool(row.is_active),
        "is_default": bool(row.is_default),
        "is_system": bool(row.is_system),
    }
    return ConfigVersionSnapshot(
        source_config_id=str(row.id),
        version=None,
        version_label=str(row.name),
        status="published" if row.is_active else "disabled",
        snapshot=snapshot,
        created_at=_datetime_or_none(row.created_at),
        updated_at=_datetime_or_none(row.updated_at),
    )


def _prompt_template_overview(
    versions: list[ConfigVersionSnapshot],
) -> dict[str, Any]:
    return {
        "backing_store": "PromptTemplate",
        "template_count": len(versions),
        "active_template_count": sum(1 for item in versions if item.status == "published"),
        "default_template_count": sum(
            1 for item in versions if item.snapshot.get("is_default") is True
        ),
        "prompt_types": sorted(
            {
                str(item.snapshot.get("prompt_type"))
                for item in versions
                if item.snapshot.get("prompt_type")
            }
        ),
        "audit_carrier": "SystemLog",
    }


def _datetime_or_none(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None
