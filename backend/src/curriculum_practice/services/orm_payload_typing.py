from __future__ import annotations

from datetime import datetime
from typing import Any


def set_orm_field(row: object, name: str, value: object) -> None:
    setattr(row, name, value)


def orm_str(value: object, *, default: str = "") -> str:
    return value if isinstance(value, str) else default


def orm_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def orm_int(value: object, *, default: int = 1) -> int:
    return value if isinstance(value, int) else default


def orm_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def orm_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def orm_datetime(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None
