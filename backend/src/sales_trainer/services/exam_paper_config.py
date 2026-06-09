from __future__ import annotations

from decimal import Decimal


class ExamPaperServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def quiz_config(pass_threshold: Decimal | float | None) -> dict[str, object]:
    if pass_threshold is None:
        return {"quiz": {"enabled_question_types": ["single_choice"]}}
    return {
        "quiz": {
            "pass_threshold": float(pass_threshold),
            "enabled_question_types": ["single_choice"],
        }
    }


def decimal_or_none(value: Decimal | float | int | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None
