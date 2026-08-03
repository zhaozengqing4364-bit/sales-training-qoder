"""Foundation learner API exposes only typed, user-safe error envelopes."""

from __future__ import annotations

import json

from foundation_learner_api import _error
from newcomer_training.errors import NewcomerTrainingError
from task_runtime.errors import IdempotencyKeyReusedError, TaskNotFoundError


def _payload(response: object) -> dict[str, object]:
    return json.loads(bytes(getattr(response, "body", b"")))


def test_domain_error_preserves_safe_message_status_and_details() -> None:
    response = _error(
        NewcomerTrainingError(
            "[NEWCOMER_ACTIVITY_LOCKED]",
            "请先完成前一项训练，再继续当前活动。",
            409,
            details={"recovery": "return_to_journey"},
        )
    )

    assert response.status_code == 409
    payload = _payload(response)
    assert payload["error"] == "[NEWCOMER_ACTIVITY_LOCKED]"
    assert payload["message"] == "请先完成前一项训练，再继续当前活动。"
    assert payload["details"] == {"recovery": "return_to_journey"}
    assert payload["trace_id"]


def test_task_errors_use_closed_public_status_mapping() -> None:
    missing = _error(TaskNotFoundError())
    conflict = _error(IdempotencyKeyReusedError())

    assert missing.status_code == 404
    assert _payload(missing)["error"] == "[TASK_NOT_FOUND]"
    assert conflict.status_code == 409
    assert _payload(conflict)["error"] == "[IDEMPOTENCY_KEY_REUSED]"
