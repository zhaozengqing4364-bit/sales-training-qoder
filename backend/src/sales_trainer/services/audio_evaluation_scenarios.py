"""Generic audio scenario metadata for non-orchestrated unit callers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AudioMaterialPolicy = Literal["required_confirmed", "optional", "none"]


@dataclass(frozen=True, slots=True)
class AudioEvaluationScenario:
    scenario_key: str
    purpose_key: str
    module_key: str
    display_name: str
    module_type: Literal["audio_scoring", "audio_scoring_group"]
    material_policy: AudioMaterialPolicy
    prompt_required: bool
    runtime_shape: Literal["single_audio", "duration_option_group"]
    completion_rule: Literal["passed", "scored", "submitted"]
    primary_action_label: str
    default_order_index: int
    capability_keys: tuple[str, ...]
    description: str
    task_brief_title: str
    task_brief_purpose: str
    task_brief_scenario: str
    material_error_code: str = "[AUDIO_EVALUATION_MATERIAL_BINDING_REQUIRED]"

    @property
    def requires_confirmed_material(self) -> bool:
        return self.material_policy == "required_confirmed"


def get_audio_evaluation_scenario(
    scenario_key: str | None,
) -> AudioEvaluationScenario | None:
    del scenario_key
    return None


def resolve_audio_evaluation_scenario(
    *,
    scenario_key: str | None = None,
    module_key: str | None = None,
    purpose_key: str | None = None,
) -> AudioEvaluationScenario | None:
    del scenario_key, module_key, purpose_key
    return None


def resolve_audio_evaluation_scenario_from_config(
    config: dict[str, Any] | None,
    *,
    scenario_key: str | None = None,
    module_key: str | None = None,
    purpose_key: str | None = None,
) -> AudioEvaluationScenario | None:
    raw = config if isinstance(config, dict) else {}
    metadata = raw.get("audio_evaluation")
    if not isinstance(metadata, dict):
        return None
    key = _text(metadata.get("scenario_key")) or scenario_key
    if not key:
        return None
    return AudioEvaluationScenario(
        scenario_key=key,
        purpose_key=_text(metadata.get("purpose_key")) or purpose_key or key,
        module_key=_text(metadata.get("module_key")) or module_key or key,
        display_name=_text(metadata.get("display_name")) or "录音训练",
        module_type="audio_scoring",
        material_policy=(
            "required_confirmed"
            if metadata.get("material_required") is True
            else "optional"
        ),
        prompt_required=metadata.get("prompt_required") is not False,
        runtime_shape="single_audio",
        completion_rule="passed",
        primary_action_label="上传录音",
        default_order_index=1,
        capability_keys=tuple(
            str(item) for item in metadata.get("capability_keys", []) if str(item)
        ),
        description=_text(metadata.get("description")) or "完成录音并获取反馈。",
        task_brief_title=_text(metadata.get("task_brief_title")) or "录音训练",
        task_brief_purpose=_text(metadata.get("task_brief_purpose")) or "完成训练任务。",
        task_brief_scenario=_text(metadata.get("task_brief_scenario")) or "按任务要求完成录音。",
    )


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = [
    "AudioEvaluationScenario",
    "get_audio_evaluation_scenario",
    "resolve_audio_evaluation_scenario",
    "resolve_audio_evaluation_scenario_from_config",
]
