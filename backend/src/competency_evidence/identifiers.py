"""Stable launch competency identifiers and immutable public definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StandardCompetencyDefinition:
    stable_key: str
    title: str
    description: str
    observable_behaviors: tuple[str, ...]
    evidence_types: tuple[str, ...]
    evidence_roles: tuple[str, ...]
    minimum_valid_evidence: int = 1
    minimum_confidence: float = 0.6


STANDARD_COMPETENCIES: tuple[StandardCompetencyDefinition, ...] = (
    StandardCompetencyDefinition(
        stable_key="product_knowledge",
        title="产品知识",
        description="准确说明产品解决的问题、适用条件、关键价值和能力边界。",
        observable_behaviors=(
            "从客户问题出发说明产品能力",
            "给出可追溯依据并明确适用边界",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application", "expression"),
    ),
    StandardCompetencyDefinition(
        stable_key="customer_understanding",
        title="客户理解",
        description="识别客户角色、目标、约束和决策关注点，不用假设替代确认。",
        observable_behaviors=(
            "区分使用者、影响者和决策者",
            "确认目标、约束和判断标准",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application"),
    ),
    StandardCompetencyDefinition(
        stable_key="needs_discovery",
        title="需求发现",
        description="通过有层次的问题发现现状、影响、期望和优先级。",
        observable_behaviors=(
            "围绕现状、问题和影响连续追问",
            "复述并确认需求优先级",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application"),
    ),
    StandardCompetencyDefinition(
        stable_key="value_expression",
        title="价值表达",
        description="把产品能力连接到客户目标、预期变化和可验证结果。",
        observable_behaviors=(
            "把能力与客户目标建立清晰联系",
            "说明预期变化和验证方式",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application", "expression"),
    ),
    StandardCompetencyDefinition(
        stable_key="objection_handling",
        title="异议处理",
        description="先理解异议依据，再用证据回应并约定下一步。",
        observable_behaviors=(
            "先接住并澄清异议",
            "用适用证据回应并确认是否解决",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application"),
    ),
    StandardCompetencyDefinition(
        stable_key="process_compliance",
        title="流程与合规",
        description="遵守授权、记录和承诺边界，对不确定事项明确待确认。",
        observable_behaviors=(
            "关键承诺前核对依据和权限",
            "记录待确认事项且不作越权承诺",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application"),
    ),
    StandardCompetencyDefinition(
        stable_key="communication_structure",
        title="沟通结构",
        description="用清晰结构表达结论、依据、影响和下一步。",
        observable_behaviors=(
            "先给结论再说明依据",
            "明确共识、负责人、动作和时间",
        ),
        evidence_types=("lesson", "quiz", "audio_assessment", "ai_coach", "assignment"),
        evidence_roles=("knowledge", "application", "expression"),
    ),
)

STANDARD_COMPETENCY_KEYS: tuple[str, ...] = tuple(
    item.stable_key for item in STANDARD_COMPETENCIES
)

__all__ = [
    "STANDARD_COMPETENCIES",
    "STANDARD_COMPETENCY_KEYS",
    "StandardCompetencyDefinition",
]
