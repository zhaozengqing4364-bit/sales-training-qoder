from __future__ import annotations

from dataclasses import dataclass
from typing import Any

READINESS_DOSSIER_TARGET_TYPE = "sales_trainer_readiness_dossier"
REVIEW_ACTION_CREATED = "sales_trainer_readiness_dossier.review_action_created"
READINESS_CONTRACT_VERSION = "readiness_dossier_v1"


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    capability_key: str
    display_name: str
    description: str


CAPABILITY_DEFINITIONS: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition("expression_clarity", "表达清晰度", "表达是否清楚、可理解。"),
    CapabilityDefinition(
        "structured_presentation", "结构化讲解", "讲解是否有层次和逻辑。"
    ),
    CapabilityDefinition(
        "product_understanding", "产品理解", "是否能准确说明产品价值。"
    ),
    CapabilityDefinition(
        "customer_perspective", "客户视角", "是否能从客户处境组织表达。"
    ),
    CapabilityDefinition("needs_discovery", "需求识别", "是否能识别和追问客户需求。"),
    CapabilityDefinition("objection_handling", "异议回应", "是否能回应疑问和阻力。"),
    CapabilityDefinition(
        "business_etiquette",
        "商务礼仪与职业表达",
        "商务场景中的礼仪、边界和职业表达。",
    ),
)
CAPABILITY_KEYS = frozenset(item.capability_key for item in CAPABILITY_DEFINITIONS)
CAPABILITY_LABELS = {
    item.capability_key: item.display_name for item in CAPABILITY_DEFINITIONS
}


def capability_label(capability_key: str) -> str:
    return CAPABILITY_LABELS.get(capability_key, capability_key)


def module_capability_keys(module: dict[str, Any]) -> list[str]:
    raw_configured = module.get("capability_keys")
    configured = unique_non_empty(
        raw_configured if isinstance(raw_configured, list) else []
    )
    configured_known = [key for key in configured if key in CAPABILITY_KEYS]
    if configured_known:
        return configured_known

    module_key = str(module.get("module_key") or "").lower()
    module_type = str(module.get("module_type") or "").lower()
    kind = str(module.get("kind") or "").lower()
    title = str(module.get("title") or module.get("display_name") or "").lower()
    haystack = f"{module_key} {module_type} {kind} {title}"
    if "business" in haystack or "etiquette" in haystack or "礼仪" in haystack:
        return ["business_etiquette", "customer_perspective"]
    if "pyramid" in haystack or "金字塔" in haystack:
        return ["expression_clarity", "structured_presentation"]
    if kind == "audio_submission":
        return [
            "expression_clarity",
            "structured_presentation",
            "product_understanding",
        ]
    if kind == "quiz_attempt":
        return ["product_understanding", "customer_perspective", "needs_discovery"]
    if kind == "ai_coach":
        return ["business_etiquette", "customer_perspective", "objection_handling"]
    return ["product_understanding"]


def decision_label(decision: str) -> str:
    return {
        "approve": "确认达标",
        "require_retraining": "要求重练",
        "mark_manual_follow_up": "标记需人工跟进",
    }.get(decision, "复核动作")


def unique_non_empty(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
