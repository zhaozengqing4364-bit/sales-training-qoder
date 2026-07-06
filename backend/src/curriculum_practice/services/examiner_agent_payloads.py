from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from json import dumps
from typing import Any, Protocol, runtime_checkable

from curriculum_practice.models import ExaminerAgent
from curriculum_practice.schemas import (
    ExaminerAgentCreate,
    ExaminerAgentResponse,
    ExaminerAgentUpdate,
)
from curriculum_practice.services.orm_payload_typing import orm_int, set_orm_field

HASH_EXCLUDED_FIELDS = {
    "examiner_agent_id",
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


def serialize_examiner_agent(agent: ExaminerAgent) -> ExaminerAgentResponse:
    return ExaminerAgentResponse.model_validate(
        examiner_agent_lifecycle_snapshot(agent)
    )


def examiner_agent_ref(agent: ExaminerAgent) -> dict[str, object]:
    return {
        "asset_type": "examiner_agent",
        "asset_id": str(agent.examiner_agent_id),
        "version": int(agent.version),
        "hash": str(agent.content_hash or examiner_agent_content_hash(agent)),
        "snapshot_label": "published",
    }


def examiner_agent_content_hash(payload: object) -> str:
    return _content_hash(_without_hash_excluded_fields(_to_dict(payload)))


def examiner_agent_payload(agent: ExaminerAgent) -> dict[str, object]:
    return {
        "name": agent.name,
        "description": agent.description,
        "question_source_ids": list(agent.question_source_ids or []),
        "learner_level_strategy": dict(agent.learner_level_strategy or {}),
        "scoring_policy_id": agent.scoring_policy_id,
        "timeout_config": dict(agent.timeout_config or {}),
        "safety_config": dict(agent.safety_config or {}),
        "prompt_config": dict(agent.prompt_config or {}),
        "simulation_config": dict(agent.simulation_config or {}),
    }


def examiner_agent_lifecycle_snapshot(agent: ExaminerAgent) -> dict[str, Any]:
    return {
        **examiner_agent_payload(agent),
        "examiner_agent_id": str(agent.examiner_agent_id),
        "version": int(agent.version or 1),
        "content_hash": agent.content_hash,
        "status": agent.status,
        "published_at": _datetime_value(agent.published_at),
        "created_at": _datetime_value(agent.created_at),
        "updated_at": _datetime_value(agent.updated_at),
    }


def examiner_agent_create_data(payload: ExaminerAgentCreate) -> dict[str, Any]:
    return payload.model_dump(mode="json")


def examiner_agent_revision_payload_from_update(
    agent: ExaminerAgent,
    payload: ExaminerAgentUpdate,
) -> dict[str, Any]:
    next_snapshot = examiner_agent_lifecycle_snapshot(agent)
    next_snapshot.update(payload.model_dump(exclude_unset=True, mode="json"))
    next_snapshot["status"] = "published"
    next_snapshot["version"] = int(agent.version or 1) + 1
    next_snapshot["content_hash"] = examiner_agent_content_hash(next_snapshot)
    return next_snapshot


def apply_examiner_agent_revision_payload(
    agent: ExaminerAgent,
    payload: dict[str, Any],
    *,
    actor_id: str,
    published_at: datetime,
) -> None:
    set_orm_field(agent, "name", _required_str(payload, "name"))
    set_orm_field(agent, "description", _optional_str(payload, "description"))
    set_orm_field(
        agent,
        "question_source_ids",
        _list_value(payload, "question_source_ids"),
    )
    set_orm_field(
        agent,
        "learner_level_strategy",
        _dict_value(payload, "learner_level_strategy"),
    )
    set_orm_field(
        agent, "scoring_policy_id", _required_str(payload, "scoring_policy_id")
    )
    set_orm_field(agent, "timeout_config", _dict_value(payload, "timeout_config"))
    set_orm_field(agent, "safety_config", _dict_value(payload, "safety_config"))
    set_orm_field(agent, "prompt_config", _dict_value(payload, "prompt_config"))
    set_orm_field(agent, "simulation_config", _dict_value(payload, "simulation_config"))
    set_orm_field(agent, "status", "published")
    set_orm_field(
        agent, "version", _int_value(payload, "version", fallback=agent.version)
    )
    set_orm_field(agent, "content_hash", examiner_agent_content_hash(payload))
    set_orm_field(agent, "published_by", actor_id)
    set_orm_field(agent, "published_at", published_at)
    set_orm_field(agent, "updated_by", actor_id)


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


def _dict_value(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    return dict(value) if isinstance(value, dict) else {}


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


def _int_value(payload: dict[str, Any], field_name: str, *, fallback: object) -> int:
    value = payload.get(field_name)
    return value if isinstance(value, int) else orm_int(fallback)


def _datetime_value(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None
