"""Safe application errors for the audio-assessment boundary."""

from __future__ import annotations

from typing import Any


class AudioAssessmentError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 409,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


__all__ = ["AudioAssessmentError"]
