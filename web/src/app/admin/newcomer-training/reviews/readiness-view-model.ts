import type {
    ReadinessCompetencyStatus,
    ReadinessReviewQueueV1,
} from "@/lib/api/types/newcomer-training";

export const READINESS_STATE_OPTIONS = [
    { value: "", label: "全部状态" },
    { value: "projecting", label: "正在汇总证据" },
    { value: "incomplete", label: "训练证据待补充" },
    { value: "ready_for_review", label: "等待人工复核" },
    { value: "under_review", label: "复核处理中" },
    { value: "decided", label: "已记录结论" },
    { value: "stale", label: "档案需要刷新" },
    { value: "projection_failed", label: "档案汇总失败" },
] as const;

const READINESS_STATES = new Set<string>(
    READINESS_STATE_OPTIONS.map((option) => option.value),
);

export function normalizeReadinessState(value: string | null): string {
    return value && READINESS_STATES.has(value) ? value : "";
}

export function readinessRiskLabel(value: "low" | "medium" | "high"): string {
    return { low: "低风险", medium: "中风险", high: "高风险" }[value];
}

export function readinessCompetencyStatusLabel(
    value: ReadinessCompetencyStatus,
): string {
    return {
        sufficient: "证据充分",
        gap: "存在差距",
        quality_review: "质量待复核",
        missing: "证据缺失",
    }[value];
}

export function readinessEvidenceTypeLabel(value: string): string {
    return {
        lesson: "学习记录",
        quiz: "测验记录",
        audio_assessment: "录音讲解",
        ai_coach: "教练练习",
        assignment: "客户场景录音",
    }[value] ?? "训练证据";
}

export function readinessQueueLearnerName(
    item: ReadinessReviewQueueV1["items"][number],
): string {
    return item.object_summary.learner.name.trim() || "未命名学员";
}
