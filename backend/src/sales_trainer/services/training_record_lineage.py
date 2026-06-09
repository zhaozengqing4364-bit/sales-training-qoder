from __future__ import annotations

from typing import Any, TypedDict


class TrainingRecordLineageFields(TypedDict):
    path_key: str | None
    path_revision_id: str | None
    path_revision_no: int | None
    module_key: str | None
    legacy_snapshot_only: bool


def training_record_lineage_fields(
    payload: dict[str, Any] | None,
) -> TrainingRecordLineageFields:
    direct = _lineage_from_mapping(payload)
    if direct is not None:
        return direct
    context = _first_answer_context(payload)
    from_answer = _lineage_from_mapping(context)
    if from_answer is not None:
        return from_answer
    return {
        "path_key": None,
        "path_revision_id": None,
        "path_revision_no": None,
        "module_key": None,
        "legacy_snapshot_only": True,
    }


def _lineage_from_mapping(
    payload: dict[str, Any] | None,
) -> TrainingRecordLineageFields | None:
    if payload is None or "legacy_snapshot_only" not in payload:
        return None
    return {
        "path_key": _string_value(payload.get("path_key")),
        "path_revision_id": _string_value(payload.get("path_revision_id")),
        "path_revision_no": _int_value(payload.get("path_revision_no")),
        "module_key": _string_value(payload.get("module_key")),
        "legacy_snapshot_only": bool(payload.get("legacy_snapshot_only")),
    }


def _first_answer_context(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    answers = payload.get("answers")
    if not isinstance(answers, list) or not answers:
        return None
    first = answers[0]
    if not isinstance(first, dict):
        return None
    context = first.get("attempt_context")
    return context if isinstance(context, dict) else None


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _int_value(value: Any) -> int | None:
    return value if isinstance(value, int) else None
