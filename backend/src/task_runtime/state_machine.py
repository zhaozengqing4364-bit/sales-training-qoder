"""Centralized canonical durable-task lifecycle."""

from __future__ import annotations

from task_runtime.contracts import TaskState
from task_runtime.errors import TaskTransitionError

TERMINAL_TASK_STATES = frozenset(
    {TaskState.CANCELLED, TaskState.SUCCEEDED, TaskState.DEAD_LETTER}
)

ALLOWED_TASK_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset(
        {TaskState.RUNNING, TaskState.CANCEL_REQUESTED, TaskState.DEAD_LETTER}
    ),
    TaskState.RUNNING: frozenset(
        {
            TaskState.SUCCEEDED,
            TaskState.RETRY_WAIT,
            TaskState.CANCEL_REQUESTED,
            TaskState.DEAD_LETTER,
        }
    ),
    TaskState.RETRY_WAIT: frozenset(
        {TaskState.QUEUED, TaskState.CANCEL_REQUESTED, TaskState.DEAD_LETTER}
    ),
    TaskState.CANCEL_REQUESTED: frozenset(
        {TaskState.CANCELLED, TaskState.SUCCEEDED, TaskState.DEAD_LETTER}
    ),
    TaskState.CANCELLED: frozenset(),
    TaskState.SUCCEEDED: frozenset(),
    TaskState.DEAD_LETTER: frozenset(),
}


def require_task_transition(source: TaskState, target: TaskState) -> None:
    if target not in ALLOWED_TASK_TRANSITIONS[source]:
        raise TaskTransitionError(source.value, target.value)
