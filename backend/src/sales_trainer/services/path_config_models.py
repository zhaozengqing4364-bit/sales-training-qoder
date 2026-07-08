from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final, Literal, assert_never

from pydantic import ValidationError

from sales_trainer.models import SalesTrainerAssetRevision, SalesTrainerUnit
from sales_trainer.schemas import (
    AiCoachConfig,
    NewcomerPathConfigPayload,
    NewcomerPathModuleConfig,
    NewcomerRealtimeRuntimeBinding,
    SalesTrainerPathConfig,
    SalesTrainerPathModuleType,
)
from sales_trainer.services.asset_revision_service import AssetChangeClass
from sales_trainer.services.audio_evaluation_scenarios import (
    AUDIO_EVALUATION_SCENARIOS,
    COMPANY_PRODUCT_DEMO_SCENARIO_KEY,
    resolve_audio_evaluation_scenario,
    resolve_audio_evaluation_scenario_from_config,
)
from sales_trainer.services.path_config_audio_refs import audio_refs_from_unit
from sales_trainer.services.readiness_state import CAPABILITY_KEYS

PathModuleBindingRef = tuple[Any, ...]

NEWCOMER_PATH_RESOURCE_TYPE = "newcomer_training_path"
NEWCOMER_PATH_LOGICAL_ID = "newcomer_training_path_v1"
LEGACY_NEWCOMER_PATH_KEYS = {"new_seller_modules_v1"}
CANONICAL_NEWCOMER_MODULE_KEYS: Final = frozenset(
    {
        "ppt_explanation",
        "company_product_demo",
        "business_skills",
        "elevator_pitch",
        "realtime_roleplay",
        "realtime_roleplay_placeholder",
    }
)
CANONICAL_NEWCOMER_MODULE_TYPES: Final = {
    "ppt_explanation": "audio_scoring",
    "company_product_demo": "audio_scoring",
    "business_skills": "article_exam",
    "elevator_pitch": "audio_scoring_group",
    "realtime_roleplay": "realtime_roleplay",
    "realtime_roleplay_placeholder": "realtime_placeholder",
}
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


def validate_path_payload_for_write(payload: NewcomerPathConfigPayload) -> None:
    if payload.path_key in LEGACY_NEWCOMER_PATH_KEYS:
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_PATH_CONFIG_ALIAS_READ_ONLY]",
            "新人训练路径兼容路径标识只允许读取，请在新人训练路径配置中心保存当前路径配置。",
            409,
        )
    if payload.path_key != NEWCOMER_PATH_LOGICAL_ID:
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            f"新人训练路径 path_key 必须为 {NEWCOMER_PATH_LOGICAL_ID}。",
            422,
        )
    if not payload.enabled:
        raise SalesTrainerPathConfigError(
            "[NEWCOMER_PATH_CONFIG_INVALID]",
            "新人训练路径顶层 enabled=false 暂不支持，请停用具体模块而不是停用整条路径。",
            422,
        )

    seen_module_keys: set[str] = set()
    seen_order_indexes: set[int] = set()
    for module in payload.modules:
        legacy_module_key = LEGACY_NEWCOMER_MODULE_KEY_MAP.get(module.module_key)
        if legacy_module_key is not None:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                (
                    f"模块 {module.title} 使用了兼容 module_key {module.module_key}，"
                    f"请改用 {legacy_module_key}。"
                ),
                422,
            )
        if module.module_key not in CANONICAL_NEWCOMER_MODULE_KEYS:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                f"模块 {module.title} 使用了不受支持的 module_key：{module.module_key}。",
                422,
            )
        scenario = resolve_audio_evaluation_scenario(
            scenario_key=module.scenario_key,
            module_key=module.module_key,
        )
        if module.scenario_key and scenario is None:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                f"模块 {module.title} 使用了不受支持的录音评测场景：{module.scenario_key}。",
                422,
            )
        if scenario is not None and scenario.module_key != module.module_key:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                (
                    f"模块 {module.title} 的录音评测场景 {scenario.scenario_key} "
                    f"必须绑定 module_key={scenario.module_key}。"
                ),
                422,
            )
        expected_module_type = CANONICAL_NEWCOMER_MODULE_TYPES[module.module_key]
        if module.module_type != expected_module_type:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                (
                    f"模块 {module.title} 的 module_key={module.module_key} "
                    f"必须使用 module_type={expected_module_type}。"
                ),
                422,
            )
        unknown_capability_keys = sorted(set(module.capability_keys) - CAPABILITY_KEYS)
        if unknown_capability_keys:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                (
                    f"模块 {module.title} 使用了未纳入新人达标档案能力模型的能力项："
                    f"{', '.join(unknown_capability_keys)}。"
                ),
                422,
            )
        if module.module_key in seen_module_keys:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                f"新人训练路径存在重复 module_key：{module.module_key}。",
                422,
            )
        seen_module_keys.add(module.module_key)
        if module.order_index in seen_order_indexes:
            raise SalesTrainerPathConfigError(
                "[NEWCOMER_PATH_CONFIG_INVALID]",
                f"新人训练路径存在重复 order_index：{module.order_index}。",
                422,
            )
        seen_order_indexes.add(module.order_index)


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
    scenario = resolve_audio_evaluation_scenario_from_config(
        unit.config if isinstance(unit.config, dict) else None,
        scenario_key=config.scenario_key,
        module_key=module_key or config.module_key,
    )
    return NewcomerPathModuleConfig(
        module_key=module_key or config.module_key or str(unit.unit_id),
        scenario_key=(
            config.scenario_key
            or (scenario.scenario_key if scenario is not None else None)
        ),
        module_type=config.module_type or "audio_scoring",
        enabled=config.enabled,
        order_index=config.order_index,
        title=config.level_title or str(unit.name),
        description=(
            config.level_description
            or (str(unit.description) if unit.description is not None else None)
        ),
        target_unit_id=config.target_unit_id or str(unit.unit_id),
        learning_content_id=config.learning_content_id,
        exam_paper_id=config.exam_paper_id,
        material_id=config.material_id or audio_refs.material_id,
        material_version_id=config.material_version_id or audio_refs.material_version_id,
        scoring_prompt_id=config.scoring_prompt_id or audio_refs.scoring_prompt_id,
        disabled_reason=config.disabled_reason,
        unlock_after_unit_ids=config.unlock_after_unit_ids,
        capability_keys=config.capability_keys,
        learner_level_required=config.learner_level_required,
        completion_rule=config.completion_rule,
        primary_action_label=config.primary_action_label,
        retry_action_label=config.retry_action_label,
        review_action_label=config.review_action_label,
        guidance_templates=config.guidance_templates,
        ai_coach=(
            AiCoachConfig.model_validate(config.ai_coach)
            if config.ai_coach is not None
            else None
        ),
        runtime_binding=(
            NewcomerRealtimeRuntimeBinding.model_validate(config.runtime_binding)
            if config.runtime_binding is not None
            else None
        ),
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
    *,
    target_unit_id: str | None = None,
    level_title: str | None = None,
    order_index: int | None = None,
) -> SalesTrainerPathConfig:
    return SalesTrainerPathConfig(
        enabled=module.enabled,
        path_key=payload.path_key,
        module_key=module.module_key,
        scenario_key=module.scenario_key,
        module_type=module.module_type,
        path_title=payload.title,
        goal_title=payload.goal_title,
        level_title=level_title or module.title,
        level_description=module.description,
        order_index=order_index or module.order_index,
        target_unit_id=target_unit_id or module.target_unit_id,
        learning_content_id=module.learning_content_id,
        exam_paper_id=module.exam_paper_id,
        material_id=module.material_id,
        material_version_id=module.material_version_id,
        scoring_prompt_id=module.scoring_prompt_id,
        disabled_reason=module.disabled_reason,
        unlock_after_unit_ids=module.unlock_after_unit_ids,
        capability_keys=module.capability_keys,
        learner_level_required=module.learner_level_required,
        completion_rule=module.completion_rule,
        primary_action_label=module.primary_action_label,
        retry_action_label=module.retry_action_label,
        review_action_label=module.review_action_label,
        guidance_templates=module.guidance_templates,
        ai_coach=module.ai_coach.model_dump(mode="json") if module.ai_coach else None,
        runtime_binding=(
            module.runtime_binding.model_dump(mode="json")
            if module.runtime_binding
            else None
        ),
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
            tuple(module.capability_keys),
            _stable_runtime_binding(module.runtime_binding),
            tuple(
                (
                    option.option_key,
                    option.target_unit_id,
                    option.duration_minutes,
                    option.display_name,
                    option.order_index,
                )
                for option in sorted(
                    module.duration_options,
                    key=lambda item: (item.order_index, item.option_key),
                )
            ),
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
        case "realtime_roleplay":
            return "realtime_roleplay"
        case "realtime_placeholder":
            return "realtime_roleplay_placeholder"
        case "audio_scoring" | None:
            return _infer_audio_module_key(unit)
        case unreachable:
            assert_never(unreachable)


def _infer_audio_module_key(unit: SalesTrainerUnit) -> str | None:
    raw_config = unit.config
    config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
    if not isinstance(config, dict):
        return None
    audio = config.get("audio")
    if not isinstance(audio, dict):
        return None
    scenario = resolve_audio_evaluation_scenario_from_config(config)
    if scenario is not None:
        return scenario.module_key
    purpose = audio.get("purpose")
    if purpose == "company_product_demo":
        return COMPANY_PRODUCT_DEMO_SCENARIO_KEY
    if isinstance(purpose, str) and purpose in AUDIO_EVALUATION_SCENARIOS:
        return purpose
    return None


def _stable_runtime_binding(binding: Any) -> str | None:
    if binding is None:
        return None
    if hasattr(binding, "model_dump"):
        payload = binding.model_dump(mode="json")
    elif isinstance(binding, dict):
        payload = binding
    else:
        payload = str(binding)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
