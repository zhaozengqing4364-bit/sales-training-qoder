from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.config_bundles.adapters import ConfigBundleSnapshot, ConfigVersionSnapshot
from common.db.models import PromptTemplate as PromptTemplateRow

PROMPT_TEMPLATES_BUNDLE_KEY = "prompt_templates"


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
        "active_template_count": sum(
            1 for item in versions if item.status == "published"
        ),
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
