import type { BusinessEtiquetteTrainingUnitConfig } from "@/lib/api/types";

export function defaultBusinessEtiquetteLearningUnits(): BusinessEtiquetteTrainingUnitConfig[] {
    return [
        unit(1, "trust_foundation", "职业信任底座", "尊重分寸、第一印象、职业形象、TPO。", [1, 2], [
            "respect_boundaries",
            "professional_image",
        ], []),
        unit(2, "first_meeting_social", "初次见面社交", "称呼、介绍、握手、名片、目光微笑。", [3], [
            "meeting_social_actions",
        ], ["trust_foundation"]),
        unit(3, "business_communication", "商务沟通专业感", "电话、当面沟通、拒绝/道歉/赞美、书面沟通。", [4], [
            "business_communication",
        ], ["first_meeting_social"]),
        unit(4, "reception_visit_execution", "接待与拜访执行", "信息准备、引导、座次、茶水、送别、拜访跟进。", [5], [
            "reception_visit_execution",
        ], ["business_communication"]),
        unit(5, "meeting_negotiation_order", "会议洽谈秩序", "会议纪律、商务洽谈、发言边界、座次、线上会议。", [6], [
            "meeting_negotiation_order",
        ], ["reception_visit_execution"]),
        unit(6, "dining_social_boundary", "餐饮应酬边界", "中餐、西餐、敬酒、买单、酒桌边界。", [7], [
            "dining_social_boundary",
        ], ["meeting_negotiation_order"]),
        unit(7, "integration_repair", "综合内化与补救", "综合场景、跨文化、失误补救、复盘内化。", [8], [
            "repair_reflection_internalization",
        ], ["dining_social_boundary"]),
    ];
}

export function parseChapterOrders(value: string): number[] {
    return value
        .split(",")
        .map((item) => Number(item.trim()))
        .filter((item) => Number.isInteger(item) && item > 0);
}

export function serializeChapterOrders(value: readonly number[]): string {
    return value.join(", ");
}

function unit(
    orderIndex: number,
    unitKey: string,
    title: string,
    description: string,
    sourceChapterOrders: number[],
    capabilityKeys: string[],
    unlockAfterUnitKeys: string[],
): BusinessEtiquetteTrainingUnitConfig {
    return {
        unit_key: unitKey,
        title,
        description,
        order_index: orderIndex,
        enabled: true,
        source_chapter_orders: sourceChapterOrders,
        capability_keys: capabilityKeys,
        unlock_after_unit_keys: unlockAfterUnitKeys,
        require_reading: true,
        require_quiz: true,
        require_ai_coach: true,
        ai_coach_required_capability_keys: capabilityKeys,
        ai_coach_pass_mastery_level_key: "basic_mastery",
        ai_coach_ready_mastery_level_key: "field_ready",
        ai_coach_max_remediation_attempts: 3,
        ai_coach_manual_review_after_max_attempts: true,
        ai_coach_block_next_until_passed: true,
        ai_coach_remediation_chapter_orders: sourceChapterOrders,
        quiz_question_count: 5,
        quiz_pass_threshold: null,
        quiz_allow_retake: true,
        quiz_max_attempts: null,
        quiz_question_type_weights: {},
        allow_skip_reading: false,
        block_next_until_complete: true,
        empty_state_message: null,
    };
}
