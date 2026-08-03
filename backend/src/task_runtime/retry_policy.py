"""Canonical durable-task retry timing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from task_runtime.contracts import TaskPolicy


def retry_backoff_seconds(
    failed_attempt_count: int,
    policy: TaskPolicy | Mapping[str, Any],
) -> int:
    """Return the bounded deterministic delay after a numbered failed attempt."""

    if failed_attempt_count < 1:
        raise ValueError("failed_attempt_count must be >= 1")
    resolved = (
        policy
        if isinstance(policy, TaskPolicy)
        else TaskPolicy.model_validate(dict(policy))
    )
    multiplier = resolved.backoff_multiplier ** (failed_attempt_count - 1)
    return min(
        resolved.max_backoff_seconds,
        int(resolved.initial_backoff_seconds * multiplier),
    )


__all__ = ["retry_backoff_seconds"]
