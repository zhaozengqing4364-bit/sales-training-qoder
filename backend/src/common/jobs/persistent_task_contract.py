"""Shared contract for the planned durable background task table.

This module intentionally contains no database or scheduler implementation. It
locks the state machine and retry semantics that the first durable-task
migration and worker must follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PersistentTaskType(str, Enum):
    """First task kinds that should move off process-local scheduling."""

    SALES_TRAINER_AUDIO_SUBMISSION_PROCESS = "sales_trainer.audio_submission.process"
    KNOWLEDGE_DOCUMENT_PROCESS = "knowledge.document.process"
    PRACTICE_REPORT_GENERATE = "practice_report.generate"
    AUDIO_ARCHIVE_BATCH = "audio_archive.batch"


class PersistentTaskStatus(str, Enum):
    """Durable task lifecycle statuses."""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


PERSISTENT_TASK_TABLE_NAME = "persistent_tasks"

PERSISTENT_TASK_REQUIRED_COLUMNS: tuple[str, ...] = (
    "task_id",
    "task_type",
    "business_key",
    "target_type",
    "target_id",
    "idempotency_key",
    "payload_json",
    "status",
    "priority",
    "attempt_count",
    "max_attempts",
    "next_run_at",
    "lease_owner",
    "lease_expires_at",
    "last_error_code",
    "last_error_message",
    "dead_letter_reason",
    "trace_id",
    "created_at",
    "updated_at",
    "started_at",
    "completed_at",
)


TERMINAL_STATUSES = frozenset(
    {
        PersistentTaskStatus.SUCCEEDED,
        PersistentTaskStatus.DEAD_LETTER,
        PersistentTaskStatus.CANCELLED,
    }
)

ALLOWED_STATUS_TRANSITIONS: dict[
    PersistentTaskStatus, frozenset[PersistentTaskStatus]
] = {
    PersistentTaskStatus.QUEUED: frozenset(
        {PersistentTaskStatus.RUNNING, PersistentTaskStatus.CANCELLED}
    ),
    PersistentTaskStatus.RUNNING: frozenset(
        {
            PersistentTaskStatus.SUCCEEDED,
            PersistentTaskStatus.RETRY_WAIT,
            PersistentTaskStatus.DEAD_LETTER,
            PersistentTaskStatus.CANCELLED,
        }
    ),
    PersistentTaskStatus.RETRY_WAIT: frozenset(
        {
            PersistentTaskStatus.QUEUED,
            PersistentTaskStatus.DEAD_LETTER,
            PersistentTaskStatus.CANCELLED,
        }
    ),
    PersistentTaskStatus.SUCCEEDED: frozenset(),
    PersistentTaskStatus.DEAD_LETTER: frozenset(),
    PersistentTaskStatus.CANCELLED: frozenset(),
}


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
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds < 1:
            raise ValueError("initial_delay_seconds must be >= 1")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be >= initial_delay_seconds")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")


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
    return target in ALLOWED_STATUS_TRANSITIONS[source]


def require_transition(
    from_status: PersistentTaskStatus | str,
    to_status: PersistentTaskStatus | str,
) -> None:
    """Raise when a status transition is not allowed."""

    source = coerce_task_status(from_status)
    target = coerce_task_status(to_status)
    if not can_transition(source, target):
        raise PersistentTaskTransitionError(source, target)


def retry_delay_seconds(
    failed_attempt_count: int,
    policy: TaskRetryPolicy = DEFAULT_TASK_RETRY_POLICY,
) -> int:
    """Return deterministic exponential backoff for a failed attempt count."""

    if failed_attempt_count < 1:
        raise ValueError("failed_attempt_count must be >= 1")
    multiplier = policy.backoff_multiplier ** (failed_attempt_count - 1)
    return min(
        policy.max_delay_seconds,
        int(policy.initial_delay_seconds * multiplier),
    )


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
