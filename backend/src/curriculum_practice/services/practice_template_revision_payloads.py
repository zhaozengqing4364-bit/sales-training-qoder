from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from curriculum_practice.models import PracticeTemplate
from curriculum_practice.schemas import (
    PracticeTemplatePublishCandidate,
    PracticeTemplateResponse,
    PracticeTemplateUpdate,
    PublishedTemplateRef,
)
from curriculum_practice.services.practice_template_revision_metadata import (
    template_payload_hash,
)


def serialize_template(template: PracticeTemplate) -> PracticeTemplateResponse:
    return PracticeTemplateResponse.model_validate(template_lifecycle_snapshot(template))


def template_lifecycle_snapshot(template: PracticeTemplate) -> dict[str, Any]:
    return {
        "template_id": str(template.template_id),
        "name": template.name,
        "description": template.description,
        "scenario_type": template.scenario_type,
        "mode": template.mode,
        "agent_id": str(template.agent_id),
        "persona_id": str(template.persona_id),
        "runtime_profile_id": str(template.runtime_profile_id),
        "voice_mode": template.voice_mode,
        "scoring_ruleset_id": str(template.scoring_ruleset_id),
        "knowledge_base_refs": list(template.knowledge_base_refs or []),
        "case_item_id": template.case_item_id,
        "role_profile_id": template.role_profile_id,
        "learning_content_id": template.learning_content_id,
        "examiner_agent_id": template.examiner_agent_id,
        "target_learner_level": template.target_learner_level,
        "timeout_config": _dict_or_none(template.timeout_config),
        "curriculum_plan": _dict_or_none(template.curriculum_plan),
        "max_stage_duration_seconds": template.max_stage_duration_seconds,
        "situation_pack_code": template.situation_pack_code,
        "published_asset_refs": dict(template.published_asset_refs or {}),
        "status": template.status,
        "version": int(template.version or 1),
        "content_hash": template.content_hash,
        "published_at": _datetime_value(template.published_at),
        "created_at": _datetime_value(template.created_at),
        "updated_at": _datetime_value(template.updated_at),
    }


def template_revision_payload_from_update(
    template: PracticeTemplate,
    payload: PracticeTemplateUpdate,
) -> dict[str, Any]:
    next_snapshot = template_lifecycle_snapshot(template)
    next_snapshot.update(payload.model_dump(exclude_unset=True, mode="json"))
    next_snapshot["status"] = "published"
    next_snapshot["version"] = int(template.version or 1) + 1
    next_snapshot["published_at"] = datetime.now(UTC).isoformat()
    next_snapshot["content_hash"] = template_payload_hash(next_snapshot)
    return next_snapshot


def apply_template_revision_payload(
    template: PracticeTemplate,
    payload: dict[str, Any],
    *,
    actor_id: str,
    published_asset_refs: dict[str, dict[str, Any]],
    situation_pack_code: str,
    published_at: datetime,
) -> None:
    template.name = _required_str(payload, "name")
    template.description = _optional_str(payload, "description")
    template.scenario_type = _required_str(payload, "scenario_type")
    template.mode = _required_str(payload, "mode")
    template.agent_id = _required_str(payload, "agent_id")
    template.persona_id = _required_str(payload, "persona_id")
    template.runtime_profile_id = _required_str(payload, "runtime_profile_id")
    template.voice_mode = _required_str(payload, "voice_mode")
    template.scoring_ruleset_id = _required_str(payload, "scoring_ruleset_id")
    template.knowledge_base_refs = _list_value(payload, "knowledge_base_refs")
    template.case_item_id = _optional_str(payload, "case_item_id")
    template.role_profile_id = _optional_str(payload, "role_profile_id")
    template.learning_content_id = _optional_str(payload, "learning_content_id")
    template.examiner_agent_id = _optional_str(payload, "examiner_agent_id")
    template.target_learner_level = _optional_str(payload, "target_learner_level")
    template.timeout_config = _dict_or_none(payload.get("timeout_config"))
    template.curriculum_plan = _dict_or_none(payload.get("curriculum_plan"))
    template.max_stage_duration_seconds = _optional_int(
        payload,
        "max_stage_duration_seconds",
    )
    template.situation_pack_code = situation_pack_code
    template.published_asset_refs = published_asset_refs
    template.status = "published"
    template.version = _int_value(payload, "version", fallback=template.version or 1)
    template.content_hash = template_payload_hash(payload)
    template.published_by = actor_id
    template.published_at = published_at
    template.updated_by = actor_id


def template_publish_payload(
    payload: dict[str, Any],
    *,
    published_asset_refs: dict[str, dict[str, Any]],
    situation_pack_code: str,
) -> dict[str, Any]:
    next_payload = dict(payload)
    next_payload["published_asset_refs"] = published_asset_refs
    next_payload["situation_pack_code"] = situation_pack_code
    next_payload["content_hash"] = template_payload_hash(next_payload)
    return next_payload


def candidate_from_template(
    template: PracticeTemplate,
) -> PracticeTemplatePublishCandidate:
    return candidate_from_payload(template_lifecycle_snapshot(template))


def candidate_from_payload(
    payload: dict[str, Any],
) -> PracticeTemplatePublishCandidate:
    return PracticeTemplatePublishCandidate.model_validate(
        {
            "name": _required_str(payload, "name"),
            "scenario_type": _required_str(payload, "scenario_type"),
            "mode": _required_str(payload, "mode"),
            "agent_id": _required_str(payload, "agent_id"),
            "persona_id": _required_str(payload, "persona_id"),
            "runtime_profile_id": _required_str(payload, "runtime_profile_id"),
            "voice_mode": _required_str(payload, "voice_mode"),
            "scoring_ruleset_id": _required_str(payload, "scoring_ruleset_id"),
            "knowledge_base_refs": _list_value(payload, "knowledge_base_refs"),
            "case_item_id": _optional_str(payload, "case_item_id"),
            "role_profile_id": _optional_str(payload, "role_profile_id"),
            "learning_content_id": _optional_str(payload, "learning_content_id"),
            "examiner_agent_id": _optional_str(payload, "examiner_agent_id"),
            "target_learner_level": _optional_str(payload, "target_learner_level"),
            "timeout_config": _dict_or_none(payload.get("timeout_config")),
            "curriculum_plan": _dict_or_none(payload.get("curriculum_plan")),
            "max_stage_duration_seconds": _optional_int(
                payload,
                "max_stage_duration_seconds",
            ),
            "situation_pack_code": _optional_str(payload, "situation_pack_code"),
        }
    )


def published_ref(template: PracticeTemplate) -> PublishedTemplateRef:
    content_hash = template.content_hash or template_payload_hash(
        template_lifecycle_snapshot(template)
    )
    return PublishedTemplateRef(
        asset_id=str(template.template_id),
        version=int(template.version),
        hash=str(content_hash),
    )


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _list_value(payload: dict[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name)
    return list(value) if isinstance(value, list) else []


def _required_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return ""


def _optional_str(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return None


def _optional_int(payload: dict[str, Any], field_name: str) -> int | None:
    value = payload.get(field_name)
    return value if isinstance(value, int) else None


def _int_value(payload: dict[str, Any], field_name: str, *, fallback: int) -> int:
    value = payload.get(field_name)
    return value if isinstance(value, int) else int(fallback)


def _datetime_value(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
