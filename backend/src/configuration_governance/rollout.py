"""Fail-closed constructor-time authority selection for configuration governance."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def select_configuration_authority(
    *,
    enabled: bool,
    neutral_factory: Callable[[], T],
    legacy_factory: Callable[[], T],
) -> T:
    """Construct exactly one lifecycle authority for a request scope."""

    return neutral_factory() if enabled else legacy_factory()
