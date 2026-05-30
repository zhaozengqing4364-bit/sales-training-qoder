from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.models import Persona
from curriculum_practice.models import CaseItem, PracticeTemplate


def _as_dict(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _none_if_blank(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _template_situation_code(timeout_config: dict[str, Any]) -> str | None:
    roleplay = _as_dict(timeout_config.get("roleplay"))
    return _none_if_blank(roleplay.get("situation_code"))


def _case_situation_code(allowed_disclosure_policy: dict[str, Any]) -> str | None:
    return _none_if_blank(
        _as_dict(allowed_disclosure_policy.get("roleplay")).get("situation_code")
    )


def _persona_situation_code(persona_policy: dict[str, Any]) -> str | None:
    return _none_if_blank(
        _as_dict(persona_policy.get("roleplay_defaults")).get("situation_code")
    )


def _template_reference_payload(template: PracticeTemplate) -> dict[str, Any]:
    return {
        "asset_type": "practice_template",
        "asset_id": str(template.template_id),
        "name": template.name,
        "status": template.status,
        "version": template.version,
        "content_hash": template.content_hash,
    }


def _case_item_reference_payload(case_item: CaseItem) -> dict[str, Any]:
    return {
        "asset_type": "case_item",
        "asset_id": str(case_item.case_item_id),
        "label": f"{case_item.industry} / {case_item.customer_role}",
        "status": case_item.status,
        "version": case_item.version,
        "content_hash": case_item.content_hash,
    }


def _persona_reference_payload(persona: Persona) -> dict[str, Any]:
    return {
        "asset_type": "persona",
        "asset_id": str(persona.id),
        "name": persona.name,
        "status": persona.status,
        "category": persona.category,
    }


class SituationPackReferenceQuery:
    """Read-side query for assets referencing a SituationPack by code."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_references(self, code: str) -> dict[str, Any]:
        templates_result = await self._db.execute(
            select(PracticeTemplate).order_by(PracticeTemplate.updated_at.desc())
        )
        case_items_result = await self._db.execute(
            select(CaseItem).order_by(CaseItem.updated_at.desc())
        )
        personas_result = await self._db.execute(
            select(Persona).order_by(Persona.updated_at.desc())
        )
        templates = [
            _template_reference_payload(template)
            for template in templates_result.scalars().all()
            if _template_situation_code(_as_dict(template.timeout_config)) == code
        ]
        case_items = [
            _case_item_reference_payload(case_item)
            for case_item in case_items_result.scalars().all()
            if _case_situation_code(_as_dict(case_item.allowed_disclosure_policy))
            == code
        ]
        personas = [
            _persona_reference_payload(persona)
            for persona in personas_result.scalars().all()
            if _persona_situation_code(_as_dict(persona.persona_policy)) == code
        ]
        return {
            "practice_templates": templates,
            "case_items": case_items,
            "personas": personas,
            "total": len(templates) + len(case_items) + len(personas),
        }
