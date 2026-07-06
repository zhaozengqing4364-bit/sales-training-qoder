from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from json import dumps
from typing import Any, Protocol, runtime_checkable

from curriculum_practice.models import CaseItem, RoleProfile
from curriculum_practice.schemas import CaseItemCreate, RoleProfileCreate
from curriculum_practice.services.orm_payload_typing import orm_int, set_orm_field

HASH_EXCLUDED_FIELDS = {
    "case_item_id",
    "role_profile_id",
    "version",
    "content_hash",
    "status",
    "published_at",
    "published_by",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
}


@runtime_checkable
class ModelDumpable(Protocol):
    def model_dump(self) -> dict[str, Any]: ...


def case_item_content_hash(payload: object) -> str:
    return _content_hash(_without_hash_excluded_fields(_to_dict(payload)))


def role_profile_content_hash(payload: object) -> str:
    return _content_hash(_without_hash_excluded_fields(_to_dict(payload)))


def case_item_payload(item: CaseItem) -> dict[str, object]:
    return {
        "industry": item.industry,
        "company_profile": item.company_profile,
        "customer_role": item.customer_role,
        "pain_points": list(item.pain_points or []),
        "objections": list(item.objections or []),
        "hidden_information": item.hidden_information,
        "success_criteria": list(item.success_criteria or []),
        "allowed_disclosure_policy": item.allowed_disclosure_policy or {},
    }


def role_profile_payload(item: RoleProfile) -> dict[str, object]:
    payload: dict[str, object] = {
        "role_type": item.role_type,
        "role_name": item.role_name,
        "persona_ref": item.persona_ref,
        "communication_style": item.communication_style,
        "pressure_level": item.pressure_level,
        "knowledge_boundary": list(item.knowledge_boundary or []),
        "behavior_rules": list(item.behavior_rules or []),
        "voice_style_hint": item.voice_style_hint,
    }
    if item.voice_id:
        payload["voice_id"] = item.voice_id
    if item.voice_sample_url:
        payload["voice_sample_url"] = item.voice_sample_url
    return payload


def case_item_lifecycle_snapshot(item: CaseItem) -> dict[str, Any]:
    return {
        **case_item_payload(item),
        "case_item_id": str(item.case_item_id),
        "version": int(item.version or 1),
        "content_hash": item.content_hash,
        "status": item.status,
        "published_at": _datetime_value(item.published_at),
        "created_at": _datetime_value(item.created_at),
        "updated_at": _datetime_value(item.updated_at),
    }


def role_profile_lifecycle_snapshot(item: RoleProfile) -> dict[str, Any]:
    return {
        **role_profile_payload(item),
        "role_profile_id": str(item.role_profile_id),
        "version": int(item.version or 1),
        "content_hash": item.content_hash,
        "status": item.status,
        "published_at": _datetime_value(item.published_at),
        "created_at": _datetime_value(item.created_at),
        "updated_at": _datetime_value(item.updated_at),
    }


def case_item_revision_payload_from_update(
    item: CaseItem,
    payload: CaseItemCreate,
) -> dict[str, Any]:
    next_snapshot = case_item_lifecycle_snapshot(item)
    next_snapshot.update(payload.model_dump(mode="json"))
    next_snapshot["status"] = "published"
    next_snapshot["version"] = int(item.version or 1) + 1
    next_snapshot["content_hash"] = case_item_content_hash(next_snapshot)
    return next_snapshot


def role_profile_revision_payload_from_update(
    item: RoleProfile,
    payload: RoleProfileCreate,
) -> dict[str, Any]:
    next_snapshot = role_profile_lifecycle_snapshot(item)
    next_snapshot.update(payload.model_dump(mode="json"))
    next_snapshot["status"] = "published"
    next_snapshot["version"] = int(item.version or 1) + 1
    next_snapshot["content_hash"] = role_profile_content_hash(next_snapshot)
    return next_snapshot


def apply_case_item_revision_payload(
    item: CaseItem,
    payload: dict[str, Any],
    *,
    actor_id: str,
    published_at: datetime,
) -> None:
    set_orm_field(item, "industry", _required_str(payload, "industry"))
    set_orm_field(item, "company_profile", _required_str(payload, "company_profile"))
    set_orm_field(item, "customer_role", _required_str(payload, "customer_role"))
    set_orm_field(item, "pain_points", _list_value(payload, "pain_points"))
    set_orm_field(item, "objections", _list_value(payload, "objections"))
    set_orm_field(
        item, "hidden_information", _required_str(payload, "hidden_information")
    )
    set_orm_field(item, "success_criteria", _list_value(payload, "success_criteria"))
    set_orm_field(
        item,
        "allowed_disclosure_policy",
        _dict_value(payload, "allowed_disclosure_policy"),
    )
    set_orm_field(item, "status", "published")
    set_orm_field(
        item, "version", _int_value(payload, "version", fallback=item.version)
    )
    set_orm_field(item, "content_hash", case_item_content_hash(payload))
    set_orm_field(item, "published_by", actor_id)
    set_orm_field(item, "published_at", published_at)
    set_orm_field(item, "updated_by", actor_id)


def apply_role_profile_revision_payload(
    item: RoleProfile,
    payload: dict[str, Any],
    *,
    actor_id: str,
    published_at: datetime,
) -> None:
    set_orm_field(item, "role_type", _required_str(payload, "role_type"))
    set_orm_field(item, "role_name", _required_str(payload, "role_name"))
    set_orm_field(item, "persona_ref", _optional_str(payload, "persona_ref"))
    set_orm_field(
        item,
        "communication_style",
        _required_str(payload, "communication_style"),
    )
    set_orm_field(item, "pressure_level", _required_str(payload, "pressure_level"))
    set_orm_field(
        item, "knowledge_boundary", _list_value(payload, "knowledge_boundary")
    )
    set_orm_field(item, "behavior_rules", _list_value(payload, "behavior_rules"))
    set_orm_field(item, "voice_style_hint", _required_str(payload, "voice_style_hint"))
    set_orm_field(item, "voice_id", _optional_str(payload, "voice_id"))
    set_orm_field(item, "voice_sample_url", _optional_str(payload, "voice_sample_url"))
    set_orm_field(item, "status", "published")
    set_orm_field(
        item, "version", _int_value(payload, "version", fallback=item.version)
    )
    set_orm_field(item, "content_hash", role_profile_content_hash(payload))
    set_orm_field(item, "published_by", actor_id)
    set_orm_field(item, "published_at", published_at)
    set_orm_field(item, "updated_by", actor_id)


def copy_suffix(value: str) -> str:
    suffix = " (副本)"
    trimmed = value.strip()
    if trimmed.endswith(suffix):
        return trimmed
    return f"{trimmed}{suffix}"


def has_disclosure_phase(policy: object) -> bool:
    return (
        isinstance(policy, dict)
        and isinstance(policy.get("phases"), list)
        and bool(policy["phases"])
    )


def _content_hash(payload: object) -> str:
    return (
        "sha256:"
        + sha256(
            dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
    )


def _without_hash_excluded_fields(payload: object) -> object:
    if isinstance(payload, dict):
        return {
            key: _without_hash_excluded_fields(value)
            for key, value in payload.items()
            if key not in HASH_EXCLUDED_FIELDS
            and not (key in {"voice_id", "voice_sample_url"} and value in (None, ""))
        }
    if isinstance(payload, list):
        return [_without_hash_excluded_fields(item) for item in payload]
    return payload


def _to_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, ModelDumpable):
        return value.model_dump()
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }


def _required_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if isinstance(value, str):
        return value
    return ""


def _optional_str(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    return value if isinstance(value, str) else None


def _list_value(payload: dict[str, Any], field_name: str) -> list[Any]:
    value = payload.get(field_name)
    return list(value) if isinstance(value, list) else []


def _dict_value(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    return dict(value) if isinstance(value, dict) else {}


def _int_value(payload: dict[str, Any], field_name: str, *, fallback: object) -> int:
    value = payload.get(field_name)
    return value if isinstance(value, int) else orm_int(fallback)


def _datetime_value(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
