from __future__ import annotations

from sales_trainer.orchestration.activities.base import ActivityProjection
from sales_trainer.orchestration.completion import aggregate_module_progress
from sales_trainer.orchestration.contracts import ModuleConfig


def _projection(activity_id: str, status: str) -> ActivityProjection:
    return ActivityProjection(
        activity_id=activity_id,
        activity_type="assignment",
        status=status,
        completed=status in {"completed", "passed"},
        score=None,
        max_score=None,
        passed=status == "passed" if status in {"passed", "failed"} else None,
        next_action=None,
        message=None,
    )


def _module(mode: str = "all_required", count: int | None = None) -> ModuleConfig:
    return ModuleConfig.model_validate(
        {
            "module_id": "module",
            "title": "产品 A",
            "order_index": 1,
            "completion_policy": {
                "mode": mode,
                "activity_ids": ["lesson", "quiz"] if count else [],
                "count": count,
            },
            "activities": [
                {
                    "activity_id": activity_id,
                    "type": "assignment",
                    "title": activity_id,
                    "order_index": index,
                    "required": required,
                    "config": {
                        "submission_type": "text",
                        "review_mode": "automatic_complete",
                    },
                }
                for index, (activity_id, required) in enumerate(
                    (("lesson", True), ("quiz", True), ("coach", False)), start=1
                )
            ],
        }
    )


def test_should_complete_module_when_all_required_activities_complete() -> None:
    result = aggregate_module_progress(
        _module(),
        {
            "lesson": _projection("lesson", "completed"),
            "quiz": _projection("quiz", "passed"),
            "coach": _projection("coach", "not_started"),
        },
    )
    assert result.completed is True
    assert result.completed_count == 2
    assert result.total_required == 2


def test_should_apply_at_least_count_to_declared_activity_membership() -> None:
    result = aggregate_module_progress(
        _module("at_least_count", 1),
        {"lesson": _projection("lesson", "completed")},
    )
    assert result.completed is True
    assert result.completed_count == 1
