"""Constructor-time Roleplay authority selection without importing adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def select_roleplay_authority(
    *,
    enabled: bool,
    neutral_factory: Callable[..., T],
    legacy_factory: Callable[..., T],
) -> Callable[..., T]:
    """Return exactly one compiler factory for the lifetime of its caller."""

    return neutral_factory if enabled else legacy_factory
