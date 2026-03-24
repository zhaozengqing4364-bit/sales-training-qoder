import type {
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
    main_capability_not_passed: "核心能力",
    insufficient_turns: "轮次不足",
    insufficient_turn_data: "证据不足",
};

const GOAL_TYPE_LABELS: Record<string, string> = {
    objection_response_drill: "异议回应训练",
    objection_progress: "异议推进",
    single_next_goal: "下一轮重点",
    collect_more_evidence: "补齐有效互动",
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
