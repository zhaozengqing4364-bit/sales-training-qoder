from __future__ import annotations

from typing import Any, Final, TypedDict

from sales_trainer.services.path_attempt_context_service import (
    PathRuntimeContextPayload,
)

SUBMISSION_CONTEXT_KEY: Final = "submission_context"


class AudioSubmissionLineageFields(TypedDict):
    path_key: str | None
    path_revision_id: str | None
    path_revision_no: int | None
    module_key: str | None
    legacy_snapshot_only: bool


def freeze_submission_context(
    task_brief_snapshot: dict[str, Any] | None,
    context: PathRuntimeContextPayload,
) -> dict[str, Any]:
    snapshot = dict(task_brief_snapshot or {})
    snapshot[SUBMISSION_CONTEXT_KEY] = context
    return snapshot


def submission_lineage_fields(
    task_brief_snapshot: dict[str, Any] | None,
) -> AudioSubmissionLineageFields:
    context = _submission_context(task_brief_snapshot)
    if context is None:
        return {
            "path_key": None,
            "path_revision_id": None,
            "path_revision_no": None,
            "module_key": None,
            "legacy_snapshot_only": True,
        }
    return {
        "path_key": _string_value(context.get("path_key")),
        "path_revision_id": _string_value(context.get("path_revision_id")),
        "path_revision_no": _int_value(context.get("path_revision_no")),
        "module_key": _string_value(context.get("module_key")),
        "legacy_snapshot_only": bool(context.get("legacy_snapshot_only")),
    }


def _submission_context(
    task_brief_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if task_brief_snapshot is None:
        return None
    context = task_brief_snapshot.get(SUBMISSION_CONTEXT_KEY)
    return context if isinstance(context, dict) else None


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _int_value(value: Any) -> int | None:
    return value if isinstance(value, int) else None
