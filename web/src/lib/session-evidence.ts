import type {
    PresentationReview,
    SessionEvidenceCompleteness,
    SessionEvidenceStage,
    SessionNotEvaluableReason,
} from "@/lib/api/types";

const STAGE_LABELS: Record<string, string> = {
    opening: "开场破冰",
    discovery: "需求挖掘",
    objection: "异议处理",
    closing: "促成成交",
};

const NOT_EVALUABLE_REASON_LABELS: Record<string, string> = {
    INSUFFICIENT_TURN_DATA: "对话轮次不足，暂无法形成稳定评估。",
    INSUFFICIENT_SESSION_METRICS: "当前会话缺少稳定指标，暂无法形成评估。",
};

const MISSING_FIELD_LABELS: Record<string, string> = {
    closing_stage: "成交阶段证据",
    stage_summary: "阶段汇总",
    effectiveness_snapshot: "会话结果快照",
    session_scores: "会话评分",
    messages: "对话消息",
};

const ISSUE_TYPE_LABELS: Record<string, string> = {
    objection_response: "异议回应",
    value_gap: "价值表达",
    value_translation_gap: "价值翻译",
    evidence_gap: "证据支撑",
    objection_handling_gap: "异议处理",
    next_step_gap: "推进下一步",
    main_capability_not_passed: "核心能力",
    insufficient_turns: "轮次不足",
    insufficient_turn_data: "证据不足",
    insufficient_sales_evidence: "销售证据不足",
};

const GOAL_TYPE_LABELS: Record<string, string> = {
    objection_response_drill: "异议回应训练",
    objection_progress: "异议推进",
    value_to_benefit_translation: "收益翻译",
    evidence_backing: "证据补强",
    objection_reframe: "重构异议回应",
    next_step_commitment: "下一步承诺",
    single_next_goal: "下一轮重点",
    collect_more_evidence: "补齐有效互动",
    collect_sales_evidence: "补齐销售证据",
};

const PRESENTATION_ISSUE_LABELS: Record<string, string> = {
    forbidden_word: "禁用词提醒",
    missing_point: "遗漏要点",
    vague_response: "表达模糊",
};

const PRESENTATION_DEGRADED_REASON_LABELS: Record<string, string> = {
    missing_page_metadata: "当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。",
};

export function formatSessionStageLabel(stage?: SessionEvidenceStage | null): string {
    if (!stage) {
        return "未分阶段";
    }
    return STAGE_LABELS[String(stage)] || String(stage);
}

export function formatNotEvaluableReason(
    reason?: SessionNotEvaluableReason | null,
): string {
    if (!reason) {
        return "当前证据不足，暂无法形成稳定评估。";
    }
    return NOT_EVALUABLE_REASON_LABELS[String(reason)] || `当前会话暂不可评估（${String(reason)}）。`;
}

export function formatEvidenceCompletenessNote(
    completeness?: SessionEvidenceCompleteness | null,
): string | null {
    if (!completeness || completeness.complete !== false) {
        return null;
    }

    const missingFields = Array.isArray(completeness.missing_fields)
        ? completeness.missing_fields.filter(Boolean)
        : [];

    if (missingFields.length === 0) {
        return "当前证据仍不完整，部分诊断会在更多事实到齐后更新。";
    }

    const labels = missingFields.map((field) => MISSING_FIELD_LABELS[field] || field);
    return `当前证据仍不完整：${labels.join("、")}。`;
}

export function formatIssueTypeLabel(issueType?: string | null): string | null {
    if (!issueType) {
        return null;
    }
    return ISSUE_TYPE_LABELS[String(issueType)] || null;
}

export function formatGoalTypeLabel(goalType?: string | null): string | null {
    if (!goalType) {
        return null;
    }
    return GOAL_TYPE_LABELS[String(goalType)] || null;
}

export function formatPresentationIssueLabel(issueType?: string | null): string | null {
    if (!issueType) {
        return null;
    }
    return PRESENTATION_ISSUE_LABELS[String(issueType)] || null;
}

export function formatPresentationDegradedNote(
    review?: PresentationReview | null,
    completeness?: SessionEvidenceCompleteness | null,
): string | null {
    const reasons = [
        ...(review?.diagnostics?.degraded_reasons || []),
        ...(completeness?.degraded_reasons || []),
    ].filter(Boolean);

    const uniqueReasons = Array.from(new Set(reasons));
    if (uniqueReasons.length === 0) {
        if (review?.coverage_status === "degraded" || completeness?.page_metadata_complete === false) {
            return "当前 PPT 证据不完整，逐页总结和要点覆盖仅展示已确认部分。";
        }
        return null;
    }

    return uniqueReasons
        .map((reason) => PRESENTATION_DEGRADED_REASON_LABELS[reason] || `当前 PPT 证据存在降级原因：${reason}。`)
        .join(" ");
}
