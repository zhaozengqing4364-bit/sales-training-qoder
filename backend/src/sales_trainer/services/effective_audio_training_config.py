"""Generic unit audio config; newcomer activity config is resolved elsewhere."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerUnit


class EffectiveAudioContext(TypedDict):
    path_key: str | None
    path_revision_id: str | None
    path_revision_no: int | None
    module_key: str | None
    scenario_key: str | None
    module_type: str | None
    legacy_snapshot_only: bool


@dataclass(frozen=True, slots=True)
class EffectiveAudioTrainingConfig:
    unit: SalesTrainerUnit
    config: dict[str, Any]
    context: EffectiveAudioContext
    source: Literal["generic_unit_config"]


class EffectiveAudioTrainingConfigError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class EffectiveAudioTrainingConfigResolver:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def resolve_for_unit(
        self, unit: SalesTrainerUnit, *, allow_legacy: bool = True
    ) -> EffectiveAudioTrainingConfig:
        del allow_legacy
        _ = self._db
        config: dict[str, Any] = (
            deepcopy(unit.config) if isinstance(unit.config, dict) else {}
        )
        return EffectiveAudioTrainingConfig(
            unit=unit,
            config=config,
            context={
                "path_key": None,
                "path_revision_id": None,
                "path_revision_no": None,
                "module_key": str(unit.unit_id),
                "scenario_key": _scenario_key(config),
                "module_type": str(unit.unit_type),
                "legacy_snapshot_only": True,
            },
            source="generic_unit_config",
        )


def _scenario_key(config: dict[str, Any]) -> str | None:
    audio = config.get("audio")
    if isinstance(audio, dict) and audio.get("scenario_key"):
        return str(audio["scenario_key"])
    return None


__all__ = [
    "EffectiveAudioTrainingConfig",
    "EffectiveAudioTrainingConfigError",
    "EffectiveAudioTrainingConfigResolver",
]
