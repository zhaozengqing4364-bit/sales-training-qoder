from __future__ import annotations

from typing import Any

from sales_trainer.schemas import BusinessEtiquetteTrainingUnitConfig


def default_business_etiquette_learning_units() -> list[
    BusinessEtiquetteTrainingUnitConfig
]:
    return [
        _unit(
            1,
            "trust_foundation",
            "职业信任底座",
            "尊重分寸、第一印象、职业形象、TPO。",
            [1, 2],
            ["respect_boundaries", "professional_image"],
            [],
        ),
        _unit(
            2,
            "first_meeting_social",
            "初次见面社交",
            "称呼、介绍、握手、名片、目光微笑。",
            [3],
            ["meeting_social_actions"],
            ["trust_foundation"],
        ),
        _unit(
            3,
            "business_communication",
            "商务沟通专业感",
            "电话、当面沟通、拒绝/道歉/赞美、书面沟通。",
            [4],
            ["business_communication"],
            ["first_meeting_social"],
        ),
        _unit(
            4,
            "reception_visit_execution",
            "接待与拜访执行",
            "信息准备、引导、座次、茶水、送别、拜访跟进。",
            [5],
            ["reception_visit_execution"],
            ["business_communication"],
        ),
        _unit(
            5,
            "meeting_negotiation_order",
            "会议洽谈秩序",
            "会议纪律、商务洽谈、发言边界、座次、线上会议。",
            [6],
            ["meeting_negotiation_order"],
            ["reception_visit_execution"],
        ),
        _unit(
            6,
            "dining_social_boundary",
            "餐饮应酬边界",
            "中餐、西餐、敬酒、买单、酒桌边界。",
            [7],
            ["dining_social_boundary"],
            ["meeting_negotiation_order"],
        ),
        _unit(
            7,
            "integration_repair",
            "综合内化与补救",
            "综合场景、跨文化、失误补救、复盘内化。",
            [8],
            ["repair_reflection_internalization"],
            ["dining_social_boundary"],
        ),
    ]


def default_business_etiquette_learning_units_payload() -> list[dict[str, Any]]:
    return [
        unit.model_dump(mode="json")
        for unit in default_business_etiquette_learning_units()
    ]


def _unit(
    order_index: int,
    unit_key: str,
    title: str,
    description: str,
    source_chapter_orders: list[int],
    capability_keys: list[str],
    unlock_after_unit_keys: list[str],
) -> BusinessEtiquetteTrainingUnitConfig:
    return BusinessEtiquetteTrainingUnitConfig(
        unit_key=unit_key,
        title=title,
        description=description,
        order_index=order_index,
        enabled=True,
        source_chapter_orders=source_chapter_orders,
        capability_keys=capability_keys,
        unlock_after_unit_keys=unlock_after_unit_keys,
        require_reading=True,
        require_quiz=True,
        require_ai_coach=True,
        ai_coach_required_capability_keys=capability_keys,
        ai_coach_pass_mastery_level_key="basic_mastery",
        ai_coach_ready_mastery_level_key="field_ready",
        ai_coach_max_remediation_attempts=3,
        ai_coach_manual_review_after_max_attempts=True,
        ai_coach_block_next_until_passed=True,
        ai_coach_remediation_chapter_orders=source_chapter_orders,
        quiz_question_count=5,
        quiz_pass_threshold=None,
        quiz_allow_retake=True,
        quiz_max_attempts=None,
        quiz_question_type_weights={},
        allow_skip_reading=False,
        block_next_until_complete=True,
        empty_state_message=None,
    )
