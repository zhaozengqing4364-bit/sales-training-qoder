"""Contract tests for planned durable background tasks."""

from __future__ import annotations

import pytest

from common.jobs.persistent_task_contract import (
    ALLOWED_STATUS_TRANSITIONS,
    PERSISTENT_TASK_REQUIRED_COLUMNS,
    PERSISTENT_TASK_TABLE_NAME,
    PersistentTaskStatus,
    PersistentTaskTransitionError,
    PersistentTaskType,
    TaskRetryPolicy,
    can_transition,
    classify_failed_attempt,
    coerce_task_status,
    is_terminal_status,
    require_transition,
    retry_delay_seconds,
)
from task_runtime.contracts import TaskState
from task_runtime.state_machine import ALLOWED_TASK_TRANSITIONS


def test_should_define_first_process_local_task_types() -> None:
    assert {item.value for item in PersistentTaskType} == {
        "sales_trainer.audio_submission.process",
        "knowledge.document.process",
        "practice_report.generate",
        "audio_archive.batch",
    }


def test_should_lock_minimum_persistent_task_table_contract() -> None:
    assert PERSISTENT_TASK_TABLE_NAME == "durable_tasks"
    assert {
        "task_id",
        "task_type",
        "organization_id",
        "resource_type",
        "resource_id",
        "idempotency_key_hash",
        "input_artifact_id",
        "state",
        "attempt_count",
        "max_attempts",
        "next_run_at",
        "last_error_code",
        "fence_generation",
        "trace_id",
    }.issubset(set(PERSISTENT_TASK_REQUIRED_COLUMNS))


def test_should_allow_expected_success_path() -> None:
    assert can_transition("queued", "running")
    assert can_transition(PersistentTaskStatus.RUNNING, PersistentTaskStatus.SUCCEEDED)
    assert is_terminal_status("succeeded")


def test_legacy_import_surface_reuses_the_seven_state_canonical_lifecycle() -> None:
    assert PersistentTaskStatus is TaskState
    assert {item.value for item in PersistentTaskStatus} == {
        "queued",
        "running",
        "retry_wait",
        "cancel_requested",
        "cancelled",
        "succeeded",
        "dead_letter",
    }
    assert can_transition("queued", "cancel_requested")
    assert not can_transition("queued", "cancelled")
    assert ALLOWED_STATUS_TRANSITIONS is ALLOWED_TASK_TRANSITIONS


def test_should_reject_transition_out_of_terminal_status() -> None:
    assert not can_transition("succeeded", "queued")

    with pytest.raises(PersistentTaskTransitionError) as exc_info:
        require_transition("succeeded", "queued")

    assert exc_info.value.from_status == PersistentTaskStatus.SUCCEEDED
    assert exc_info.value.to_status == PersistentTaskStatus.QUEUED


def test_should_schedule_retry_before_attempts_are_exhausted() -> None:
    policy = TaskRetryPolicy(
        max_attempts=3,
        initial_delay_seconds=10,
        max_delay_seconds=60,
        backoff_multiplier=2,
    )

    decision = classify_failed_attempt(
        attempt_count_after_failure=2,
        retryable=True,
        policy=policy,
    )

    assert decision.status == PersistentTaskStatus.RETRY_WAIT
    assert decision.retry_delay_seconds == 20
    assert decision.reason == "retry_scheduled"
    assert decision.is_dead_letter is False


def test_should_dead_letter_terminal_or_exhausted_failures() -> None:
    terminal = classify_failed_attempt(attempt_count_after_failure=1, retryable=False)
    exhausted = classify_failed_attempt(
        attempt_count_after_failure=3,
        retryable=True,
        policy=TaskRetryPolicy(max_attempts=3),
    )

    assert terminal.status == PersistentTaskStatus.DEAD_LETTER
    assert terminal.reason == "terminal_failure"
    assert exhausted.status == PersistentTaskStatus.DEAD_LETTER
    assert exhausted.reason == "retry_exhausted"
    assert exhausted.is_dead_letter is True


def test_should_cap_retry_backoff() -> None:
    policy = TaskRetryPolicy(
        max_attempts=10,
        initial_delay_seconds=30,
        max_delay_seconds=90,
        backoff_multiplier=3,
    )

    assert retry_delay_seconds(1, policy) == 30
    assert retry_delay_seconds(2, policy) == 90
    assert retry_delay_seconds(3, policy) == 90


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_delay_seconds": 0},
        {"initial_delay_seconds": 30, "max_delay_seconds": 10},
        {"backoff_multiplier": 0.5},
    ],
)
def test_should_reject_invalid_retry_policy(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        TaskRetryPolicy(**kwargs)


def test_should_reject_unknown_status_or_invalid_attempt_count() -> None:
    with pytest.raises(ValueError, match="Unsupported persistent task status"):
        coerce_task_status("missing")

    with pytest.raises(ValueError, match="failed_attempt_count"):
        retry_delay_seconds(0)

    with pytest.raises(ValueError, match="attempt_count_after_failure"):
        classify_failed_attempt(attempt_count_after_failure=0, retryable=True)
