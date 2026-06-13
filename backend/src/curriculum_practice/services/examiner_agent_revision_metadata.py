from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Any, Final

from curriculum_practice.services.sales_trainer_revision_adapter import AssetChangeClass

EXAMINER_AGENT_RESOURCE_TYPE: Final = "curriculum_examiner_agent"
EXAMINER_AGENT_TARGET_TYPE: Final = "curriculum_examiner_agent"
HIGH_RISK_FIELDS: Final = {
    "question_source_ids",
    "scoring_policy_id",
    "timeout_config",
    "safety_config",
    "prompt_config",
}


def examiner_agent_change_class(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> AssetChangeClass:
    if examiner_agent_payload_hash(previous) == examiner_agent_payload_hash(
        next_snapshot
    ):
        return "non_semantic"
    if HIGH_RISK_FIELDS.intersection(
        {
            field
            for field in _tracked_fields()
            if previous.get(field) != next_snapshot.get(field)
        }
    ):
        return "scoring_high_risk"
    return "semantic"


def examiner_agent_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    return {
        "before": _summary(previous),
        "after": _summary(next_snapshot),
        "before_hash": examiner_agent_payload_hash(previous),
        "after_hash": examiner_agent_payload_hash(next_snapshot),
        "changed_fields": [
            field
            for field in _tracked_fields()
            if previous.get(field) != next_snapshot.get(field)
        ],
    }


def examiner_agent_payload_hash(payload: dict[str, Any]) -> str:
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "examiner_agent_id": payload.get("examiner_agent_id"),
        "name": payload.get("name"),
        "status": payload.get("status"),
        "version": payload.get("version"),
    }


def _tracked_fields() -> tuple[str, ...]:
    return (
        "name",
        "description",
        "question_source_ids",
        "learner_level_strategy",
        "scoring_policy_id",
        "timeout_config",
        "safety_config",
        "prompt_config",
        "simulation_config",
        "version",
        "content_hash",
    )
