from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

AudioMaterialPolicy = Literal["required_confirmed", "optional", "none"]
AudioRuntimeShape = Literal["single_audio", "duration_option_group"]


@dataclass(frozen=True, slots=True)
class AudioEvaluationScenario:
    scenario_key: str
    purpose_key: str
    module_key: str
    display_name: str
    module_type: Literal["audio_scoring", "audio_scoring_group"]
    material_policy: AudioMaterialPolicy
    prompt_required: bool
    runtime_shape: AudioRuntimeShape
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


PPT_EXPLANATION_SCENARIO_KEY: Final = "ppt_explanation"
COMPANY_PRODUCT_DEMO_SCENARIO_KEY: Final = "company_product_demo"
ELEVATOR_PITCH_SCENARIO_KEY: Final = "elevator_pitch"


AUDIO_EVALUATION_SCENARIOS: Final[dict[str, AudioEvaluationScenario]] = {
    PPT_EXPLANATION_SCENARIO_KEY: AudioEvaluationScenario(
        scenario_key=PPT_EXPLANATION_SCENARIO_KEY,
        purpose_key="ppt_pitch",
        module_key="ppt_explanation",
        display_name="PPT 讲解",
        module_type="audio_scoring",
        material_policy="required_confirmed",
        prompt_required=True,
        runtime_shape="single_audio",
        completion_rule="passed",
        primary_action_label="上传讲解录音",
        default_order_index=1,
        capability_keys=(
            "expression_clarity",
            "structured_presentation",
            "product_understanding",
        ),
        description="学习并讲解当前 PPT 材料，上传录音后由 AI 转写和评分。",
        task_brief_title="PPT 讲解",
        task_brief_purpose="让新人先掌握公司介绍、产品价值和客户沟通结构。",
        task_brief_scenario="面向首次见客户前的内部演练，按最新 PPT 材料完成讲解。",
        material_error_code="[PPT_MATERIAL_BINDING_REQUIRED]",
    ),
    COMPANY_PRODUCT_DEMO_SCENARIO_KEY: AudioEvaluationScenario(
        scenario_key=COMPANY_PRODUCT_DEMO_SCENARIO_KEY,
        purpose_key="company_product_demo",
        module_key="company_product_demo",
        display_name="公司产品 Demo",
        module_type="audio_scoring",
        material_policy="required_confirmed",
        prompt_required=True,
        runtime_shape="single_audio",
        completion_rule="passed",
        primary_action_label="上传 Demo 讲解录音",
        default_order_index=2,
        capability_keys=(
            "expression_clarity",
            "structured_presentation",
            "product_understanding",
        ),
        description="围绕公司产品资料或 Demo 脚本完成讲解录音，由 AI 判断表达、结构和产品理解。",
        task_brief_title="公司产品 Demo",
        task_brief_purpose="训练新人把产品价值、关键功能和客户收益讲清楚。",
        task_brief_scenario="面向客户产品演示前的内部演练，按后台绑定的产品资料或 Demo 脚本完成讲解。",
    ),
    ELEVATOR_PITCH_SCENARIO_KEY: AudioEvaluationScenario(
        scenario_key=ELEVATOR_PITCH_SCENARIO_KEY,
        purpose_key="elevator_pitch",
        module_key="elevator_pitch",
        display_name="金字塔演讲",
        module_type="audio_scoring_group",
        material_policy="optional",
        prompt_required=True,
        runtime_shape="duration_option_group",
        completion_rule="passed",
        primary_action_label="上传金字塔演讲录音",
        default_order_index=3,
        capability_keys=(
            "expression_clarity",
            "structured_presentation",
            "customer_perspective",
        ),
        description="配置多个录音时长选项，学员选择时长后上传演讲录音。",
        task_brief_title="金字塔演讲",
        task_brief_purpose="训练新人用短时间讲清公司、产品价值和下一步邀约。",
        task_brief_scenario="客户给你一段有限时间介绍机会，需要按金字塔结构完成清晰、有重点的价值说明。",
    ),
}

_SCENARIO_BY_MODULE_KEY: Final = {
    scenario.module_key: scenario for scenario in AUDIO_EVALUATION_SCENARIOS.values()
}
_SCENARIO_BY_PURPOSE_KEY: Final = {
    scenario.purpose_key: scenario for scenario in AUDIO_EVALUATION_SCENARIOS.values()
}
_LEGACY_PURPOSE_TO_SCENARIO: Final = {
    "pyramid_speech": ELEVATOR_PITCH_SCENARIO_KEY,
}


def get_audio_evaluation_scenario(
    scenario_key: str | None,
) -> AudioEvaluationScenario | None:
    return AUDIO_EVALUATION_SCENARIOS.get(str(scenario_key)) if scenario_key else None


def resolve_audio_evaluation_scenario(
    *,
    scenario_key: str | None = None,
    module_key: str | None = None,
    purpose_key: str | None = None,
) -> AudioEvaluationScenario | None:
    scenario = get_audio_evaluation_scenario(scenario_key)
    if scenario is not None:
        return scenario
    if module_key:
        scenario = _SCENARIO_BY_MODULE_KEY.get(str(module_key))
        if scenario is not None:
            return scenario
    if purpose_key:
        purpose = str(purpose_key)
        scenario = _SCENARIO_BY_PURPOSE_KEY.get(purpose)
        if scenario is not None:
            return scenario
        for prefix, legacy_scenario_key in _LEGACY_PURPOSE_TO_SCENARIO.items():
            if purpose.startswith(prefix):
                return AUDIO_EVALUATION_SCENARIOS[legacy_scenario_key]
    return None


def resolve_audio_evaluation_scenario_from_config(
    config: dict[str, Any] | None,
    *,
    scenario_key: str | None = None,
    module_key: str | None = None,
    purpose_key: str | None = None,
) -> AudioEvaluationScenario | None:
    raw_config = config if isinstance(config, dict) else {}
    audio = raw_config.get("audio")
    path = raw_config.get("path")
    config_scenario_key = (
        audio.get("scenario_key")
        if isinstance(audio, dict)
        else None
    ) or (
        path.get("scenario_key")
        if isinstance(path, dict)
        else None
    )
    config_module_key = path.get("module_key") if isinstance(path, dict) else None
    config_purpose_key = audio.get("purpose") if isinstance(audio, dict) else None
    return resolve_audio_evaluation_scenario(
        scenario_key=scenario_key or _string_or_none(config_scenario_key),
        module_key=module_key or _string_or_none(config_module_key),
        purpose_key=purpose_key or _string_or_none(config_purpose_key),
    )


def _string_or_none(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value.strip() else None
