"""Deprecated import facade over the canonical ``task_runtime`` contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from task_runtime.contracts import TaskPolicy, TaskState
from task_runtime.errors import TaskTransitionError
from task_runtime.retry_policy import retry_backoff_seconds
from task_runtime.state_machine import (
    ALLOWED_TASK_TRANSITIONS,
    TERMINAL_TASK_STATES,
    require_task_transition,
)


class PersistentTaskType(str, Enum):
    """First task kinds that should move off process-local scheduling."""

    SALES_TRAINER_AUDIO_SUBMISSION_PROCESS = "sales_trainer.audio_submission.process"
    KNOWLEDGE_DOCUMENT_PROCESS = "knowledge.document.process"
    PRACTICE_REPORT_GENERATE = "practice_report.generate"
    AUDIO_ARCHIVE_BATCH = "audio_archive.batch"


# Backward-compatible import surface. TaskState is the only lifecycle authority.
PersistentTaskStatus: TypeAlias = TaskState


PERSISTENT_TASK_TABLE_NAME = "durable_tasks"

PERSISTENT_TASK_REQUIRED_COLUMNS: tuple[str, ...] = (
    "task_id",
    "task_type",
    "schema_version",
    "organization_id",
    "actor_id",
    "resource_type",
    "resource_id",
    "idempotency_key_hash",
    "idempotency_fingerprint",
    "input_artifact_id",
    "state",
    "priority",
    "attempt_count",
    "max_attempts",
    "timeout_seconds",
    "retry_policy_json",
    "next_run_at",
    "deadline_at",
    "correlation_id",
    "causation_id",
    "last_error_code",
    "last_error_message",
    "fence_generation",
    "version",
    "trace_id",
    "created_at",
    "updated_at",
    "completed_at",
)


TERMINAL_STATUSES = TERMINAL_TASK_STATES
ALLOWED_STATUS_TRANSITIONS = ALLOWED_TASK_TRANSITIONS


class PersistentTaskTransitionError(ValueError):
    """Raised when a durable task transition violates the contract."""

    def __init__(
        self,
        from_status: PersistentTaskStatus,
        to_status: PersistentTaskStatus,
    ) -> None:
        super().__init__(
            f"Invalid persistent task transition: {from_status.value}"
            f" -> {to_status.value}"
        )
        self.from_status = from_status
        self.to_status = to_status


@dataclass(frozen=True)
class TaskRetryPolicy:
    """Retry policy stored with each durable task row."""

    max_attempts: int = 3
    initial_delay_seconds: int = 30
    max_delay_seconds: int = 900
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        self.as_task_policy()

    def as_task_policy(self) -> TaskPolicy:
        return TaskPolicy(
            max_attempts=self.max_attempts,
            initial_backoff_seconds=self.initial_delay_seconds,
            max_backoff_seconds=self.max_delay_seconds,
            backoff_multiplier=self.backoff_multiplier,
        )


DEFAULT_TASK_RETRY_POLICY = TaskRetryPolicy()


@dataclass(frozen=True)
class TaskFailureDecision:
    """Result of classifying one failed task attempt."""

    status: PersistentTaskStatus
    retry_delay_seconds: int | None
    reason: str

    @property
    def is_dead_letter(self) -> bool:
        return self.status == PersistentTaskStatus.DEAD_LETTER


def is_terminal_status(status: PersistentTaskStatus | str) -> bool:
    """Return whether the task status is terminal."""

    return coerce_task_status(status) in TERMINAL_STATUSES


def coerce_task_status(status: PersistentTaskStatus | str) -> PersistentTaskStatus:
    """Normalize stored status values to the contract enum."""

    if isinstance(status, PersistentTaskStatus):
        return status
    try:
        return PersistentTaskStatus(str(status))
    except ValueError as exc:
        raise ValueError(f"Unsupported persistent task status: {status}") from exc


def can_transition(
    from_status: PersistentTaskStatus | str,
    to_status: PersistentTaskStatus | str,
) -> bool:
    """Return whether a status transition is allowed."""

    source = coerce_task_status(from_status)
    target = coerce_task_status(to_status)
    return target in ALLOWED_TASK_TRANSITIONS[source]


def require_transition(
    from_status: PersistentTaskStatus | str,
    to_status: PersistentTaskStatus | str,
) -> None:
    """Raise when a status transition is not allowed."""

    source = coerce_task_status(from_status)
    target = coerce_task_status(to_status)
    try:
        require_task_transition(source, target)
    except TaskTransitionError as exc:
        raise PersistentTaskTransitionError(source, target) from exc


def retry_delay_seconds(
    failed_attempt_count: int,
    policy: TaskRetryPolicy = DEFAULT_TASK_RETRY_POLICY,
) -> int:
    """Return deterministic exponential backoff for a failed attempt count."""

    return retry_backoff_seconds(failed_attempt_count, policy.as_task_policy())


def classify_failed_attempt(
    *,
    attempt_count_after_failure: int,
    retryable: bool,
    policy: TaskRetryPolicy = DEFAULT_TASK_RETRY_POLICY,
) -> TaskFailureDecision:
    """Classify a failed task attempt as retry-wait or dead-letter."""

    if attempt_count_after_failure < 1:
        raise ValueError("attempt_count_after_failure must be >= 1")

    if not retryable:
        return TaskFailureDecision(
            status=PersistentTaskStatus.DEAD_LETTER,
            retry_delay_seconds=None,
            reason="terminal_failure",
        )

    if attempt_count_after_failure >= policy.max_attempts:
        return TaskFailureDecision(
            status=PersistentTaskStatus.DEAD_LETTER,
            retry_delay_seconds=None,
            reason="retry_exhausted",
        )

    return TaskFailureDecision(
        status=PersistentTaskStatus.RETRY_WAIT,
        retry_delay_seconds=retry_delay_seconds(attempt_count_after_failure, policy),
        reason="retry_scheduled",
    )
