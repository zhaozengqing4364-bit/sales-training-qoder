from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal, assert_never

from pydantic import ValidationError

from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerUnit
from sales_trainer.schemas import (
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
    SalesTrainerPathConfig,
    SalesTrainerPathModuleType,
)
from sales_trainer.services.asset_revision_service import AssetChangeClass
from sales_trainer.services.path_config_audio_refs import audio_refs_from_unit

PathModuleBindingRef = tuple[
    str,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
]

NEWCOMER_PATH_RESOURCE_TYPE = "newcomer_training_path"
NEWCOMER_PATH_LOGICAL_ID = "newcomer_training_path_v1"
LEGACY_NEWCOMER_PATH_KEYS = {"new_seller_modules_v1"}
CANONICAL_NEWCOMER_MODULE_KEYS: Final = frozenset(
    {
        "ppt_explanation",
        "business_skills",
        "elevator_pitch",
        "realtime_roleplay_placeholder",
    }
)
LEGACY_NEWCOMER_MODULE_KEY_MAP: Final = {
    "ppt_explain": "ppt_explanation",
    "pyramid_speech": "elevator_pitch",
    "realtime_placeholder": "realtime_roleplay_placeholder",
}


@dataclass(frozen=True, slots=True)
class PathUnitProjection:
    unit: SalesTrainerUnit
    path_config: SalesTrainerPathConfig


@dataclass(frozen=True, slots=True)
class PathBackfillUnit:
    unit: SalesTrainerUnit
    path_config: SalesTrainerPathConfig
    module_key: str
    selection_priority: int


@dataclass(frozen=True, slots=True)
class PathProjection:
    source: Literal["active_revision"]
    path_key: str
    revision_id: str
    revision_no: int
    items: tuple[PathUnitProjection, ...]


class SalesTrainerPathConfigError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def path_config(config: dict[str, Any]) -> SalesTrainerPathConfig | None:
    raw_path = config.get("path")
    if not isinstance(raw_path, dict):
        return None
    try:
        return SalesTrainerPathConfig.model_validate(raw_path)
    except ValidationError:
        return None


def module_from_unit(
    unit: SalesTrainerUnit,
    config: SalesTrainerPathConfig,
    *,
    module_key: str | None = None,
) -> NewcomerPathModuleConfig:
    audio_refs = audio_refs_from_unit(unit)
    return NewcomerPathModuleConfig(
        module_key=module_key or config.module_key or str(unit.unit_id),
        module_type=config.module_type or "audio_scoring",
        enabled=config.enabled,
        order_index=config.order_index,
        title=config.level_title or str(unit.name),
        description=config.level_description or unit.description,
        target_unit_id=config.target_unit_id or str(unit.unit_id),
        learning_content_id=config.learning_content_id,
        exam_paper_id=config.exam_paper_id,
        material_id=config.material_id or audio_refs.material_id,
        material_version_id=config.material_version_id or audio_refs.material_version_id,
        scoring_prompt_id=config.scoring_prompt_id or audio_refs.scoring_prompt_id,
        disabled_reason=config.disabled_reason,
        unlock_after_unit_ids=config.unlock_after_unit_ids,
        completion_rule=config.completion_rule,
        primary_action_label=config.primary_action_label,
        retry_action_label=config.retry_action_label,
        review_action_label=config.review_action_label,
        guidance_templates=config.guidance_templates,
        ai_coach=config.ai_coach,
    )


def canonical_path_module_key(
    unit: SalesTrainerUnit,
    config: SalesTrainerPathConfig,
) -> tuple[str, int] | None:
    raw_module_key = config.module_key
    if raw_module_key in CANONICAL_NEWCOMER_MODULE_KEYS:
        return raw_module_key, 0
    if raw_module_key in LEGACY_NEWCOMER_MODULE_KEY_MAP:
        return LEGACY_NEWCOMER_MODULE_KEY_MAP[raw_module_key], 1
    inferred = _infer_module_key(unit, config.module_type)
    if inferred is None:
        return None
    return inferred, 2


def path_config_from_module(
    payload: NewcomerPathConfigPayload,
    module: NewcomerPathModuleConfig,
) -> SalesTrainerPathConfig:
    return SalesTrainerPathConfig(
        enabled=module.enabled,
        path_key=payload.path_key,
        module_key=module.module_key,
        module_type=module.module_type,
        path_title=payload.title,
        goal_title=payload.goal_title,
        level_title=module.title,
        level_description=module.description,
        order_index=module.order_index,
        target_unit_id=module.target_unit_id,
        learning_content_id=module.learning_content_id,
        exam_paper_id=module.exam_paper_id,
        material_id=module.material_id,
        material_version_id=module.material_version_id,
        scoring_prompt_id=module.scoring_prompt_id,
        disabled_reason=module.disabled_reason,
        unlock_after_unit_ids=module.unlock_after_unit_ids,
        completion_rule=module.completion_rule,
        primary_action_label=module.primary_action_label,
        retry_action_label=module.retry_action_label,
        review_action_label=module.review_action_label,
        guidance_templates=module.guidance_templates,
        ai_coach=module.ai_coach.model_dump(mode="json") if module.ai_coach else None,
    )


def payload_from_revision(
    revision: SalesTrainerAssetRevision,
) -> NewcomerPathConfigPayload:
    try:
        return NewcomerPathConfigPayload.model_validate(revision.payload_json)
    except ValidationError as exc:
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_PATH_REVISION_INVALID]",
            "新人训练路径历史版本内容无法读取。",
            500,
        ) from exc


def classify_change(
    active: SalesTrainerAssetRevision | None,
    payload: NewcomerPathConfigPayload,
) -> AssetChangeClass:
    if active is None:
        return "binding"
    previous = payload_from_revision(active)
    if _module_refs(previous) != _module_refs(payload):
        return "binding"
    return "semantic"


def revision_summary(
    revision: SalesTrainerAssetRevision,
    active_revision_id: str | None,
) -> dict[str, Any]:
    payload = payload_from_revision(revision)
    revision_id = str(revision.revision_id)
    return {
        "revision_id": revision_id,
        "revision_no": revision.revision_no,
        "status": revision.status,
        "change_class": revision.change_class,
        "title": payload.title,
        "module_count": len(payload.modules),
        "is_active": revision_id == active_revision_id,
        "is_working": str(revision.status) == "working",
        "source_revision_id": revision.source_revision_id,
        "payload_hash": revision.payload_hash,
        "reason": revision.reason,
        "trace_id": revision.trace_id,
        "created_by": revision.created_by,
        "published_by": revision.published_by,
        "created_at": revision.created_at,
        "published_at": revision.published_at,
    }


def _module_refs(payload: NewcomerPathConfigPayload) -> list[PathModuleBindingRef]:
    return [
        (
            module.module_key,
            module.target_unit_id,
            module.learning_content_id,
            module.exam_paper_id,
            module.material_id,
            module.material_version_id,
            module.scoring_prompt_id,
        )
        for module in sorted(payload.modules, key=lambda item: item.order_index)
    ]



def _infer_module_key(
    unit: SalesTrainerUnit,
    module_type: SalesTrainerPathModuleType | None,
) -> str | None:
    match module_type:
        case "article_exam":
            return "business_skills"
        case "audio_scoring_group":
            return "elevator_pitch"
        case "realtime_placeholder":
            return "realtime_roleplay_placeholder"
        case "audio_scoring" | None:
            return _infer_audio_module_key(unit)
        case unreachable:
            assert_never(unreachable)


def _infer_audio_module_key(unit: SalesTrainerUnit) -> str | None:
    config = unit.config or {}
    if not isinstance(config, dict):
        return None
    audio = config.get("audio")
    if not isinstance(audio, dict):
        return None
    purpose = audio.get("purpose")
    if not isinstance(purpose, str):
        return None
    if purpose == "ppt_pitch":
        return "ppt_explanation"
    if purpose.startswith(("pyramid_speech", "elevator_pitch")):
        return "elevator_pitch"
    return None
