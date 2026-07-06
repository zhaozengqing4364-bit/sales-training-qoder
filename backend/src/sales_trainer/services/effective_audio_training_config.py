from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.models import SalesTrainerUnit
from sales_trainer.schemas import SalesTrainerPathConfig
from sales_trainer.services.path_config_models import path_config


class EffectiveAudioContext(TypedDict):
    path_key: str | None
    path_revision_id: str | None
    path_revision_no: int | None
    module_key: str | None
    module_type: str | None
    legacy_snapshot_only: bool


@dataclass(frozen=True, slots=True)
class EffectiveAudioTrainingConfig:
    unit: SalesTrainerUnit
    config: dict[str, Any]
    context: EffectiveAudioContext
    source: Literal["active_path_revision", "legacy_unit_config"]


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
        self,
        unit: SalesTrainerUnit,
        *,
        allow_legacy: bool = True,
    ) -> EffectiveAudioTrainingConfig:
        from sales_trainer.services.path_config_service import (
            SalesTrainerPathConfigService,
        )

        projection = await SalesTrainerPathConfigService(self._db).active_projection()
        if projection is not None:
            for item in projection.items:
                config = item.path_config
                unit_config = unit.config if isinstance(unit.config, dict) else None
                if str(item.unit.unit_id) != str(unit.unit_id) and (
                    config.target_unit_id != str(unit.unit_id)
                ):
                    continue
                return EffectiveAudioTrainingConfig(
                    unit=unit,
                    config=merge_audio_path_config(unit_config, config),
                    context={
                        "path_key": projection.path_key,
                        "path_revision_id": projection.revision_id,
                        "path_revision_no": projection.revision_no,
                        "module_key": config.module_key,
                        "module_type": config.module_type,
                        "legacy_snapshot_only": False,
                    },
                    source="active_path_revision",
                )
            if not allow_legacy:
                raise EffectiveAudioTrainingConfigError(
                    "[SALES_TRAINER_UNIT_NOT_FOUND]",
                    "训练单元不存在或未开放。",
                    status_code=404,
                )
        if not allow_legacy:
            raise EffectiveAudioTrainingConfigError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "新人训练路径尚未发布有效版本，无法使用旧单元配置创建新的正式录音训练。",
                status_code=409,
            )
        return EffectiveAudioTrainingConfig(
            unit=unit,
            config=_base_config(unit.config if isinstance(unit.config, dict) else None),
            context={
                "path_key": None,
                "path_revision_id": None,
                "path_revision_no": None,
                "module_key": _legacy_unit_module_key(unit),
                "module_type": None,
                "legacy_snapshot_only": True,
            },
            source="legacy_unit_config",
        )


def merge_audio_path_config(
    unit_config: dict[str, Any] | None,
    path: SalesTrainerPathConfig,
) -> dict[str, Any]:
    config = _base_config(unit_config)
    if path.scoring_prompt_id:
        audio = _dict_value(config.get("audio"))
        audio["scoring_prompt_id"] = path.scoring_prompt_id
        config["audio"] = audio
    if path.material_id:
        materials = _dict_value(config.get("materials"))
        binding: dict[str, Any] = {
            "material_id": path.material_id,
            "required": True,
            "confirmation_required": True,
            "display_order": 1,
            "version_policy": "current_published",
        }
        if path.material_version_id:
            binding["version_policy"] = "locked_version"
            binding["locked_version_id"] = path.material_version_id
        materials["bindings"] = [binding]
        config["materials"] = materials
    return config


def _base_config(config: dict[str, Any] | None) -> dict[str, Any]:
    return deepcopy(config) if isinstance(config, dict) else {}


def _dict_value(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _legacy_unit_module_key(unit: SalesTrainerUnit) -> str | None:
    raw_config = unit.config
    config = path_config(raw_config) if isinstance(raw_config, dict) else None
    if config is not None and config.module_key:
        return config.module_key
    return str(unit.unit_id)
