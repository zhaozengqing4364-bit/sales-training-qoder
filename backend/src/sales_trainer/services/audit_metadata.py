from __future__ import annotations

from decimal import Decimal
from typing import Any

from sales_trainer.models import (
    SalesTrainerExamPaper,
    SalesTrainerUnit,
    SalesTrainerUnitQuestion,
)


def unit_lifecycle_snapshot(
    unit: SalesTrainerUnit,
    questions: list[SalesTrainerUnitQuestion],
) -> dict[str, Any]:
    return {
        "unit_id": unit.unit_id,
        "name": unit.name,
        "description": unit.description,
        "unit_type": unit.unit_type,
        "status": unit.status,
        "config": unit.config or {},
        "question_ids": [str(item.question_id) for item in questions],
        "questions": [
            {
                "question_id": str(item.question_id),
                "order_index": int(item.order_index),
                "points": _number(item.points),
            }
            for item in questions
        ],
    }


def unit_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    metadata = _change_metadata(
        previous,
        next_snapshot,
        comparable_fields=("name", "description", "config", "questions", "status"),
    )
    metadata["path"] = {
        "previous_path_key": _path_value(previous, "path_key"),
        "next_path_key": _path_value(next_snapshot, "path_key"),
        "previous_module_key": _path_value(previous, "module_key"),
        "next_module_key": _path_value(next_snapshot, "module_key"),
    }
    return metadata


def paper_lifecycle_snapshot(
    paper: SalesTrainerExamPaper,
    questions: list[SalesTrainerUnitQuestion],
    *,
    unit_status: str | None,
) -> dict[str, Any]:
    return {
        "paper_id": paper.paper_id,
        "paper_key": paper.paper_key,
        "title": paper.title,
        "description": paper.description,
        "module_key": paper.module_key,
        "unit_id": paper.unit_id,
        "unit_status": unit_status,
        "status": paper.status,
        "pass_threshold": _number(paper.pass_threshold),
        "question_ids": [str(item.question_id) for item in questions],
        "questions": [
            {
                "question_id": str(item.question_id),
                "order_index": int(item.order_index),
                "points": _number(item.points),
            }
            for item in questions
        ],
    }


def paper_lifecycle_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
) -> dict[str, Any]:
    metadata = _change_metadata(
        previous,
        next_snapshot,
        comparable_fields=(
            "paper_key",
            "title",
            "description",
            "module_key",
            "pass_threshold",
            "questions",
            "status",
            "unit_status",
        ),
    )
    metadata["paper_key"] = next_snapshot["paper_key"]
    metadata["module_key"] = next_snapshot["module_key"]
    metadata["unit_id"] = next_snapshot["unit_id"]
    metadata["previous_unit_status"] = previous.get("unit_status")
    metadata["next_unit_status"] = next_snapshot.get("unit_status")
    return metadata


def _change_metadata(
    previous: dict[str, Any],
    next_snapshot: dict[str, Any],
    *,
    comparable_fields: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "previous": previous,
        "next": next_snapshot,
        "changed_fields": [
            field
            for field in comparable_fields
            if previous.get(field) != next_snapshot.get(field)
        ],
        "previous_status": previous.get("status"),
        "next_status": next_snapshot.get("status"),
    }


def _path_value(snapshot: dict[str, Any], key: str) -> Any:
    config = snapshot.get("config")
    if not isinstance(config, dict):
        return None
    path = config.get("path")
    if not isinstance(path, dict):
        return None
    return path.get(key)


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return float(str(value))
