from __future__ import annotations

import pytest
from pydantic import ValidationError

from task_runtime.contracts import (
    TaskCompletion,
    TaskResultItemRef,
    TaskResultKind,
)


def _completion_payload(**updates):
    payload = {
        "structured_payload": {"echoed": "done"},
        "result_kind": TaskResultKind.PARTIAL_SUCCESS,
        "resource_type": "echo_result",
        "resource_id": "result-1",
        "location": "/echo-results/result-1",
    }
    payload.update(updates)
    return payload


def test_result_items_accept_only_bounded_opaque_business_references() -> None:
    completion = TaskCompletion.model_validate(
        _completion_payload(
            saved_items=[{"resource_type": "echo_part", "resource_id": "part-1"}],
            remaining_items=[{"resource_type": "echo_part", "resource_id": "part-2"}],
        )
    )

    assert completion.saved_items == [
        TaskResultItemRef(resource_type="echo_part", resource_id="part-1")
    ]
    assert completion.result_items_payload()["remaining_items"] == [
        {"resource_type": "echo_part", "resource_id": "part-2"}
    ]


@pytest.mark.parametrize(
    "unsafe_item",
    [
        "完整转写正文",
        {"transcript": "完整转写正文"},
        {
            "resource_type": "echo_part",
            "resource_id": "part-1",
            "raw_provider_response": {"secret": "provider payload"},
        },
        {
            "resource_type": "echo_part",
            "resource_id": "这是一段不应进入任务结果引用的完整转写正文",
        },
    ],
)
def test_result_items_reject_legacy_arbitrary_or_sensitive_shapes(
    unsafe_item,
) -> None:
    with pytest.raises(ValidationError):
        TaskCompletion.model_validate(_completion_payload(saved_items=[unsafe_item]))


def test_result_items_reject_more_than_100_references() -> None:
    items = [
        {"resource_type": "echo_part", "resource_id": f"part-{index}"}
        for index in range(101)
    ]

    with pytest.raises(ValidationError, match="100"):
        TaskCompletion.model_validate(_completion_payload(saved_items=items))


def test_result_items_reject_aggregate_payload_over_16_kib() -> None:
    items = [
        {
            "resource_type": "echo_part",
            "resource_id": f"item-{index:03d}-" + ("x" * 150),
        }
        for index in range(100)
    ]

    with pytest.raises(ValidationError, match="超过允许大小"):
        TaskCompletion.model_validate(_completion_payload(saved_items=items))
