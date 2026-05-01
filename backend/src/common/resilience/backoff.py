"""Shared jittered backoff helpers."""

from __future__ import annotations

import random


def compute_jitter_backoff_seconds(
    *,
    attempt: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
    jitter_ratio: float = 0.2,
) -> float:
    """Compute exponential backoff with bounded jitter.

    The delay is capped at `max_delay_seconds` and then randomized inside a
    bounded window to avoid synchronized retries across workers.
    """

    normalized_attempt = max(1, int(attempt))
    normalized_base = max(0.0, float(base_delay_seconds))
    normalized_cap = max(normalized_base, float(max_delay_seconds))
    capped_delay = min(
        normalized_cap, normalized_base * (2 ** (normalized_attempt - 1))
    )

    if capped_delay <= 0:
        return 0.0

    jitter_window = capped_delay * max(0.0, float(jitter_ratio))
    lower_bound = max(0.0, capped_delay - jitter_window)
    upper_bound = min(normalized_cap, capped_delay + jitter_window)
    if upper_bound <= lower_bound:
        return round(lower_bound, 6)

    return round(random.uniform(lower_bound, upper_bound), 6)
