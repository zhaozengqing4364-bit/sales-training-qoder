"""Frozen attempt-context value object; newcomer authority lives in orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerExamPaper, SalesTrainerUnit


class PathRuntimeContextPayload(TypedDict):
    path_key: str | None
    path_revision_id: str | None
    path_revision_no: int | None
    module_key: str | None
    module_type: str | None
    legacy_snapshot_only: bool


class PathAttemptContextPayload(PathRuntimeContextPayload):
    paper_revision_id: str | None


@dataclass(frozen=True, slots=True)
class PathAttemptContext:
    path_key: str | None
    path_revision_id: str | None
    path_revision_no: int | None
    module_key: str | None
    module_type: str | None
    legacy_snapshot_only: bool

    def to_payload(self) -> PathRuntimeContextPayload:
        return {
            "path_key": self.path_key,
            "path_revision_id": self.path_revision_id,
            "path_revision_no": self.path_revision_no,
            "module_key": self.module_key,
            "module_type": self.module_type,
            "legacy_snapshot_only": self.legacy_snapshot_only,
        }

    def with_paper_revision(
        self, paper_revision_id: str | None
    ) -> PathAttemptContextPayload:
        return {**self.to_payload(), "paper_revision_id": paper_revision_id}


class PathAttemptContextService:
    """Generic non-newcomer attempts carry no newcomer path authority."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve_for_paper(
        self, paper: SalesTrainerExamPaper
    ) -> PathAttemptContext:
        _ = self._db
        return _generic_context(str(paper.paper_id), "exam_paper")

    async def resolve_for_unit(self, unit: SalesTrainerUnit) -> PathAttemptContext:
        _ = self._db
        return _generic_context(str(unit.unit_id), str(unit.unit_type))


def _generic_context(key: str, kind: str) -> PathAttemptContext:
    return PathAttemptContext(
        path_key=None,
        path_revision_id=None,
        path_revision_no=None,
        module_key=key,
        module_type=kind,
        legacy_snapshot_only=True,
    )


__all__ = [
    "PathAttemptContext",
    "PathAttemptContextPayload",
    "PathAttemptContextService",
    "PathRuntimeContextPayload",
]
