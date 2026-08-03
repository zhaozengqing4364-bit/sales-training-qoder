"""Typed readiness application failures."""

from __future__ import annotations

from typing import Any


class ReadinessError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 409,
        *,
        details: dict[str, Any] | None = None,
        audit_persisted: bool = False,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.audit_persisted = audit_persisted
        super().__init__(message)


__all__ = ["ReadinessError"]
