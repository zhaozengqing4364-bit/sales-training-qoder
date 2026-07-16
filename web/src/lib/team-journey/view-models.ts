import type { AdminJourneyItem, JourneyActivityProgress, JourneyResponse } from "@/lib/api/types/newcomer-training";

export function activityStatusLabel(activity: JourneyActivityProgress): string {
    if (activity.locked) return "未解锁";
    if (activity.completed && activity.passed !== false) return "已完成";
    if (activity.passed === false || activity.status === "failed") return "需补练";
    if (["processing", "transcribing", "scoring"].includes(activity.status)) return "处理中";
    if (activity.status === "in_progress") return "进行中";
    return "未开始";
}

export function journeyRiskActivities(journey: JourneyResponse): JourneyActivityProgress[] {
    return journey.phases.flatMap((phase) => phase.modules).flatMap((moduleConfig) => moduleConfig.activities).filter((activity) => activity.passed === false || ["failed", "needs_review", "error"].includes(activity.status));
}

export interface TeamJourneyRow {
    learnerId: string;
    learnerName: string;
    currentPhase: string;
    progressPercent: number;
    completedCount: number;
    totalRequired: number;
    riskLabels: string[];
}

export function toTeamJourneyRow(item: AdminJourneyItem): TeamJourneyRow {
    const summary = item.summary;
    const current = summary.current_phase;
    return {
        learnerId: item.learner_id,
        learnerName: item.learner_name.trim() || "未命名学员",
        currentPhase: current?.title ?? (summary.progress.completed ? "已完成" : "尚未开始"),
        progressPercent: Math.round(summary.progress.percent),
        completedCount: summary.progress.completed_count,
        totalRequired: summary.progress.total_required,
        riskLabels: summary.risk_labels.slice(0, 2),
    };
}
