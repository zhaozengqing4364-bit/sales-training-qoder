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
    department: string;
    currentPhase: string;
    progressPercent: number;
    completedCount: number;
    totalRequired: number;
    riskLabels: string[];
}

export function toTeamJourneyRow(item: AdminJourneyItem): TeamJourneyRow {
    const current = item.journey.phases.find((phase) => !phase.completed && !phase.locked);
    return {
        learnerId: item.learner_id,
        learnerName: item.learner_name.trim() || "未命名学员",
        department: item.department.trim() || "未分配部门",
        currentPhase: current?.title ?? (item.journey.progress.completed ? "已完成" : "尚未开始"),
        progressPercent: Math.round(item.journey.progress.percent),
        completedCount: item.journey.progress.completed_count,
        totalRequired: item.journey.progress.total_required,
        riskLabels: journeyRiskActivities(item.journey).slice(0, 2).map((activity) => activity.title),
    };
}
