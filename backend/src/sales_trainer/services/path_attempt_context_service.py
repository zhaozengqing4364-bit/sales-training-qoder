from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerExamPaper, SalesTrainerUnit
from sales_trainer.services.path_config_models import path_config
from sales_trainer.services.path_config_service import SalesTrainerPathConfigService


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

    def with_paper_revision(self, paper_revision_id: str | None) -> PathAttemptContextPayload:
        return {
            **self.to_payload(),
            "paper_revision_id": paper_revision_id,
        }


class PathAttemptContextService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve_for_paper(
        self,
        paper: SalesTrainerExamPaper,
    ) -> PathAttemptContext:
        projection = await SalesTrainerPathConfigService(self._db).active_projection()
        if projection is None:
            return _legacy_context(module_key=str(paper.module_key))
        for item in projection.items:
            config = item.path_config
            if config.exam_paper_id == str(paper.paper_id) or str(item.unit.unit_id) == str(
                paper.unit_id
            ):
                return PathAttemptContext(
                    path_key=projection.path_key,
                    path_revision_id=projection.revision_id,
                    path_revision_no=projection.revision_no,
                    module_key=config.module_key,
                    module_type=config.module_type,
                    legacy_snapshot_only=False,
                )
        return _legacy_context(module_key=str(paper.module_key))

    async def resolve_for_unit(
        self,
        unit: SalesTrainerUnit,
    ) -> PathAttemptContext:
        projection = await SalesTrainerPathConfigService(self._db).active_projection()
        if projection is None:
            return _legacy_context(module_key=_legacy_unit_module_key(unit))
        for item in projection.items:
            config = item.path_config
            if str(item.unit.unit_id) == str(unit.unit_id) or config.target_unit_id == str(
                unit.unit_id
            ):
                return PathAttemptContext(
                    path_key=projection.path_key,
                    path_revision_id=projection.revision_id,
                    path_revision_no=projection.revision_no,
                    module_key=config.module_key,
                    module_type=config.module_type,
                    legacy_snapshot_only=False,
                )
        return _legacy_context(module_key=_legacy_unit_module_key(unit))


def _legacy_context(module_key: str | None) -> PathAttemptContext:
    return PathAttemptContext(
        path_key=None,
        path_revision_id=None,
        path_revision_no=None,
        module_key=module_key,
        module_type=None,
        legacy_snapshot_only=True,
    )


def _legacy_unit_module_key(unit: SalesTrainerUnit) -> str | None:
    config = path_config(unit.config or {})
    if config is not None and config.module_key:
        return config.module_key
    return str(unit.unit_id)
