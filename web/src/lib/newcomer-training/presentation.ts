import type { JourneyActivityProgress, JourneyPhaseProgress } from "@/lib/api/types/newcomer-training";

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
