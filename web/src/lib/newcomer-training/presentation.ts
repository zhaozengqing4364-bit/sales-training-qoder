import type { ActivityType, JourneyActivityProgress, JourneyPhaseProgress } from "@/lib/api/types/newcomer-training";

const ACTIVITY_ACTION_LABELS: Record<ActivityType, string> = {
    lesson: "开始内容学习",
    quiz: "开始做题",
    audio_assessment: "开始录音讲解",
    realtime_roleplay: "开始实时对练",
    ai_coach: "开始 AI 辅导",
    assignment: "开始完成作业",
};

export function activityActionLabel(type: ActivityType): string {
    return ACTIVITY_ACTION_LABELS[type];
}

export function progressLabel(completed: number, total: number): string {
    return total > 0 ? `已完成 ${completed}/${total}` : "暂无必修任务";
}

export function activityStatusLabel(activity: JourneyActivityProgress): string {
    if (activity.locked) return "尚未解锁";
    if (activity.completed) return activity.passed === false ? "需要补练" : "已完成";
    if (activity.status === "in_progress") return "进行中";
    return "待开始";
}

export function shouldCollapsePhase(phase: JourneyPhaseProgress): boolean {
    return phase.completed;
}
