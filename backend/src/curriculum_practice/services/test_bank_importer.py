from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from pydantic import ValidationError

from curriculum_practice.schemas import QuestionItemCreate

ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
IMPORT_MAX_BYTES = 10 * 1024 * 1024
REQUIRED_FIELDS = (
    "category_id",
    "title",
    "stem",
    "difficulty",
    "scoring_criteria",
    "scoring_dimensions",
)


@dataclass(frozen=True)
class ImportRowError:
    row: int
    field: str
    message: str


@dataclass(frozen=True)
class ImportParseResult:
    items: list[QuestionItemCreate] = field(default_factory=list)
    errors: list[ImportRowError] = field(default_factory=list)

    @property
    def imported(self) -> int:
        return len(self.items)

    @property
    def failed(self) -> int:
        return len({error.row for error in self.errors})

    def to_result_payload(self) -> dict[str, object]:
        return {
            "imported": self.imported,
            "failed": self.failed,
            "errors": [
                {"row": error.row, "field": error.field, "message": error.message}
                for error in self.errors
            ],
        }


class TestBankImporter:
    __test__ = False

    def __init__(self, *, known_category_ids: set[str]) -> None:
        self._known_category_ids = known_category_ids

    def parse(self, raw: bytes, *, filename: str) -> ImportParseResult:
        if len(raw) > IMPORT_MAX_BYTES:
            return ImportParseResult(
                errors=[ImportRowError(row=0, field="file", message="file too large")]
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ImportParseResult(
                errors=[ImportRowError(row=0, field="file", message="file must be UTF-8")]
            )

        suffix = filename.rsplit(".", 1)[-1].lower()
        if suffix == "csv":
            return self._parse_csv(text)
        if suffix == "jsonl":
            return self._parse_jsonl(text)
        return ImportParseResult(
            errors=[ImportRowError(row=0, field="file", message="unsupported import format")]
        )

    def _parse_csv(self, text: str) -> ImportParseResult:
        try:
            reader = csv.DictReader(StringIO(text))
            rows = list(reader)
        except csv.Error as exc:
            return ImportParseResult(
                errors=[ImportRowError(row=0, field="file", message=str(exc))]
            )
        return self._validate_rows(rows, first_data_row=2)

    def _parse_jsonl(self, text: str) -> ImportParseResult:
        rows: list[dict[str, Any]] = []
        errors: list[ImportRowError] = []
        for row_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(
                    ImportRowError(row=row_number, field="file", message=f"invalid JSONL: {exc.msg}")
                )
                continue
            if not isinstance(payload, dict):
                errors.append(
                    ImportRowError(row=row_number, field="file", message="JSONL row must be an object")
                )
                continue
            rows.append(payload)
        validated = self._validate_rows(rows, first_data_row=1)
        return ImportParseResult(items=validated.items, errors=errors + validated.errors)

    def _validate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        first_data_row: int,
    ) -> ImportParseResult:
        items: list[QuestionItemCreate] = []
        errors: list[ImportRowError] = []
        for offset, row in enumerate(rows):
            row_number = first_data_row + offset
            normalized = _normalize_row(row)
            row_errors = self._validate_row(normalized, row_number=row_number)
            if row_errors:
                errors.extend(row_errors)
                continue
            try:
                items.append(QuestionItemCreate(**normalized))
            except ValidationError as exc:
                errors.append(_validation_error(row_number, exc))
        return ImportParseResult(items=items, errors=errors)

    def _validate_row(self, row: dict[str, Any], *, row_number: int) -> list[ImportRowError]:
        errors: list[ImportRowError] = []
        for field_name in REQUIRED_FIELDS:
            value = row.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(
                    ImportRowError(row=row_number, field=field_name, message="required field is missing")
                )

        category_id = str(row.get("category_id") or "").strip()
        if category_id and category_id not in self._known_category_ids:
            errors.append(
                ImportRowError(row=row_number, field="category_id", message="unknown category")
            )

        difficulty = str(row.get("difficulty") or "").strip()
        if difficulty and difficulty not in ALLOWED_DIFFICULTIES:
            errors.append(
                ImportRowError(row=row_number, field="difficulty", message="invalid difficulty")
            )

        criteria = row.get("scoring_criteria")
        dimensions = row.get("scoring_dimensions")
        criteria_names = _criteria_dimension_names(criteria)
        if not criteria_names:
            errors.append(
                ImportRowError(
                    row=row_number,
                    field="scoring_criteria",
                    message="scoring_criteria.dimensions must be non-empty",
                )
            )
        if not _is_non_empty_string_list(dimensions):
            errors.append(
                ImportRowError(
                    row=row_number,
                    field="scoring_dimensions",
                    message="scoring_dimensions must be a non-empty list",
                )
            )
        elif (
            criteria_names
            and isinstance(dimensions, list)
            and not {str(item) for item in dimensions}.issubset(criteria_names)
        ):
            errors.append(
                ImportRowError(
                    row=row_number,
                    field="scoring_dimensions",
                    message="scoring_dimensions must match scoring_criteria.dimensions",
                )
            )
        return errors


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {str(key).strip(): value for key, value in row.items() if key is not None}
    for field_name in ("scoring_criteria", "scoring_dimensions", "tags"):
        normalized[field_name] = _json_or_value(normalized.get(field_name))
    for field_name in ("category_id", "title", "stem", "reference_answer", "difficulty", "department"):
        value = normalized.get(field_name)
        if isinstance(value, str):
            normalized[field_name] = value.strip()
    return normalized


def _json_or_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]
        return text


def _criteria_dimension_names(criteria: Any) -> set[str]:
    if not isinstance(criteria, dict):
        return set()
    dimensions = criteria.get("dimensions")
    if not isinstance(dimensions, list):
        return set()
    names: set[str] = set()
    for item in dimensions:
        if isinstance(item, str) and item.strip():
            names.add(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
            names.add(item["name"].strip())
    return names


def _is_non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def _validation_error(row_number: int, exc: ValidationError) -> ImportRowError:
    first_error = exc.errors()[0]
    location = first_error.get("loc") or ("file",)
    field_name = str(location[0])
    return ImportRowError(row=row_number, field=field_name, message=str(first_error.get("msg")))
