from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Any, Final

from curriculum_practice.services.sales_trainer_revision_adapter import AssetChangeClass

CASE_ITEM_RESOURCE_TYPE: Final = "curriculum_case_item"
CASE_ITEM_TARGET_TYPE: Final = "curriculum_case_item"
ROLE_PROFILE_RESOURCE_TYPE: Final = "curriculum_role_profile"
ROLE_PROFILE_TARGET_TYPE: Final = "curriculum_role_profile"


def case_item_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if case_item_payload_hash(previous) == case_item_payload_hash(next_snapshot):
        return "non_semantic"
    return "semantic"


def role_profile_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if role_profile_payload_hash(previous) == role_profile_payload_hash(next_snapshot):
        return "non_semantic"
    return "semantic"


def case_item_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "before": _summary(previous),
        "after": _summary(next_snapshot),
        "before_hash": case_item_payload_hash(previous),
        "after_hash": case_item_payload_hash(next_snapshot),
        "changed_fields": [
            field
            for field in _tracked_fields()
            if previous.get(field) != next_snapshot.get(field)
        ],
    }


def role_profile_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "before": _role_summary(previous),
        "after": _role_summary(next_snapshot),
        "before_hash": role_profile_payload_hash(previous),
        "after_hash": role_profile_payload_hash(next_snapshot),
        "changed_fields": [
            field
            for field in _role_tracked_fields()
            if previous.get(field) != next_snapshot.get(field)
        ],
    }


def case_item_payload_hash(payload: dict[str, Any]) -> str:
    hash_payload = {
        field: payload.get(field)
        for field in _tracked_fields()
        if field != "content_hash"
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


def role_profile_payload_hash(payload: dict[str, Any]) -> str:
    hash_payload = {
        field: payload.get(field)
        for field in _role_tracked_fields()
        if field != "content_hash"
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
        "case_item_id": payload.get("case_item_id"),
        "industry": payload.get("industry"),
        "customer_role": payload.get("customer_role"),
        "status": payload.get("status"),
        "version": payload.get("version"),
    }


def _role_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "role_profile_id": payload.get("role_profile_id"),
        "role_name": payload.get("role_name"),
        "pressure_level": payload.get("pressure_level"),
        "status": payload.get("status"),
        "version": payload.get("version"),
    }


def _tracked_fields() -> tuple[str, ...]:
    return (
        "industry",
        "company_profile",
        "customer_role",
        "pain_points",
        "objections",
        "hidden_information",
        "success_criteria",
        "allowed_disclosure_policy",
        "version",
        "content_hash",
    )


def _role_tracked_fields() -> tuple[str, ...]:
    return (
        "role_type",
        "role_name",
        "persona_ref",
        "communication_style",
        "pressure_level",
        "knowledge_boundary",
        "behavior_rules",
        "voice_style_hint",
        "voice_id",
        "voice_sample_url",
        "version",
        "content_hash",
    )
