from __future__ import annotations

from sales_trainer.orchestration.contracts import TrainingPathPayload
from sales_trainer.orchestration.graph import validate_path_graph


def _activity(
    activity_id: str,
    order_index: int,
    *,
    prerequisites: list[str] | None = None,
) -> dict[str, object]:
    return {
        "activity_id": activity_id,
        "type": "lesson",
        "title": activity_id,
        "order_index": order_index,
        "required": True,
        "prerequisites": prerequisites or [],
        "config": {"learning_content_id": f"content-{activity_id}"},
    }


def _module(
    module_id: str,
    order_index: int,
    *,
    activities: list[dict[str, object]],
    completion_policy: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "module_id": module_id,
        "title": module_id,
        "order_index": order_index,
        "required": True,
        "completion_policy": completion_policy or {"mode": "all_required"},
        "activities": activities,
    }


def _payload(*, modules: list[dict[str, object]]) -> TrainingPathPayload:
    return TrainingPathPayload.model_validate(
        {
            "title": "新人训练路径",
            "phases": [
                {
                    "phase_id": "phase-1",
                    "title": "阶段一",
                    "order_index": 1,
                    "required": True,
                    "modules": modules,
                }
            ],
        }
    )


def test_should_report_duplicate_sibling_order_with_field_address() -> None:
    payload = _payload(
        modules=[
            _module("module-a", 1, activities=[_activity("activity-a", 1)]),
            _module("module-b", 1, activities=[_activity("activity-b", 1)]),
        ]
    )

    issues = validate_path_graph(payload)

    assert [(issue.code, issue.object_id, issue.field_path) for issue in issues] == [
        (
            "duplicate_order_index",
            "module-b",
            "phases[0].modules[1].order_index",
        )
    ]


def test_should_report_cycle_for_each_involved_activity() -> None:
    payload = _payload(
        modules=[
            _module(
                "module-a",
                1,
                activities=[
                    _activity("activity-a", 1, prerequisites=["activity-b"]),
                    _activity("activity-b", 2, prerequisites=["activity-a"]),
                ],
            )
        ]
    )

    issues = validate_path_graph(payload)

    assert [(issue.code, issue.object_id) for issue in issues] == [
        ("cyclic_prerequisite", "activity-a"),
        ("cyclic_prerequisite", "activity-b"),
    ]


def test_should_reject_unknown_prerequisite() -> None:
    payload = _payload(
        modules=[
            _module(
                "module-a",
                1,
                activities=[
                    _activity("activity-a", 1, prerequisites=["missing-activity"])
                ],
            )
        ]
    )

    issues = validate_path_graph(payload)

    assert [(issue.code, issue.object_id) for issue in issues] == [
        ("prerequisite_not_found", "activity-a")
    ]


def test_should_reject_invalid_at_least_count_membership() -> None:
    payload = _payload(
        modules=[
            _module(
                "module-a",
                1,
                activities=[_activity("activity-a", 1)],
                completion_policy={
                    "mode": "at_least_count",
                    "activity_ids": ["activity-a", "missing-activity"],
                    "count": 2,
                },
            )
        ]
    )

    issues = validate_path_graph(payload)

    assert [(issue.code, issue.field_path) for issue in issues] == [
        (
            "completion_policy_invalid",
            "phases[0].modules[0].completion_policy.activity_ids",
        )
    ]


def test_should_accept_valid_cross_module_prerequisite_without_issues() -> None:
    payload = _payload(
        modules=[
            _module("module-a", 1, activities=[_activity("activity-a", 1)]),
            {
                **_module(
                    "module-b",
                    2,
                    activities=[
                        _activity("activity-b", 1, prerequisites=["activity-a"])
                    ],
                ),
                "prerequisites": ["module-a"],
            },
        ]
    )

    assert validate_path_graph(payload) == ()
