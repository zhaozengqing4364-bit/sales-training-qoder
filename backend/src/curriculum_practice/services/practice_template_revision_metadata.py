from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Any, Final

from curriculum_practice.services.sales_trainer_revision_adapter import AssetChangeClass

PRACTICE_TEMPLATE_RESOURCE_TYPE: Final = "curriculum_practice_template"
PRACTICE_TEMPLATE_TARGET_TYPE: Final = "curriculum_practice_template"


def template_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if _binding_fields_changed(previous, next_snapshot):
        return "binding"
    if _semantic_fields_changed(previous, next_snapshot):
        return "semantic"
    return "non_semantic"


def template_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "before": _summary(previous),
        "after": _summary(next_snapshot),
        "before_hash": template_payload_hash(previous),
        "after_hash": template_payload_hash(next_snapshot),
        "changed_fields": [
            field
            for field in _tracked_fields()
            if previous.get(field) != next_snapshot.get(field)
        ],
    }


def template_payload_hash(payload: dict[str, Any]) -> str:
    hash_payload = {
        field: payload.get(field)
        for field in _tracked_fields()
        if field != "published_asset_refs"
    }
    return "sha256:" + sha256(
        dumps(
            hash_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "template_id": payload.get("template_id"),
        "name": payload.get("name"),
        "description": payload.get("description"),
        "status": payload.get("status"),
        "version": payload.get("version"),
        "mode": payload.get("mode"),
        "scenario_type": payload.get("scenario_type"),
    }


def _tracked_fields() -> tuple[str, ...]:
    return (
        "name",
        "description",
        "scenario_type",
        "mode",
        "agent_id",
        "persona_id",
        "runtime_profile_id",
        "voice_mode",
        "scoring_ruleset_id",
        "knowledge_base_refs",
        "case_item_id",
        "role_profile_id",
        "learning_content_id",
        "examiner_agent_id",
        "target_learner_level",
        "timeout_config",
        "curriculum_plan",
        "max_stage_duration_seconds",
        "situation_pack_code",
        "published_asset_refs",
        "version",
    )


def _binding_fields_changed(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> bool:
    return any(
        previous.get(field) != next_snapshot.get(field)
        for field in (
            "agent_id",
            "persona_id",
            "runtime_profile_id",
            "scoring_ruleset_id",
            "knowledge_base_refs",
            "case_item_id",
            "role_profile_id",
            "learning_content_id",
            "examiner_agent_id",
            "curriculum_plan",
        )
    )


def _semantic_fields_changed(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> bool:
    return any(
        previous.get(field) != next_snapshot.get(field)
        for field in _tracked_fields()
    )
