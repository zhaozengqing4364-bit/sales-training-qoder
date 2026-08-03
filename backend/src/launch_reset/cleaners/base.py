"""Common cleaner contract."""

from __future__ import annotations

from typing import Any, Protocol


class ScopedCleaner(Protocol):
    name: str

    async def inspect(self) -> dict[str, Any]: ...

    async def apply(self) -> dict[str, Any]: ...

    async def verify(self) -> dict[str, Any]: ...


__all__ = ["ScopedCleaner"]
