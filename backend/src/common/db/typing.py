from __future__ import annotations

from typing import Any, Literal, TypeVar, cast, overload

JsonDict = dict[str, Any]
JsonList = list[Any]

T = TypeVar("T")


@overload
def orm_scalar(value: object, expected_type: type[T]) -> T: ...


@overload
def orm_scalar(
    value: object,
    expected_type: type[T],
    *,
    nullable: Literal[True],
) -> T | None: ...


def orm_scalar(
    value: object,
    expected_type: type[T],
    *,
    nullable: bool = False,
) -> T | None:
    """Narrow a loaded ORM attribute from legacy Column[...] model typings."""
    return cast(T | None, value)


def json_dict_value(value: object) -> JsonDict | None:
    """Narrow a JSON ORM value without changing runtime semantics."""
    return cast(JsonDict | None, value)


def json_dict_or_empty(value: object) -> JsonDict:
    """Narrow JSON only for call sites that already treat non-dicts as empty."""
    if not isinstance(value, dict):
        return {}
    return cast(JsonDict, value)


def json_list_or_empty(value: object) -> JsonList:
    """Narrow JSON only for call sites that already treat non-lists as empty."""
    if not isinstance(value, list):
        return []
    return cast(JsonList, value)
