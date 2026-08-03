"""Public application errors for the structured AI Coach."""

from __future__ import annotations

from typing import Any


class AICoachError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


__all__ = ["AICoachError"]
