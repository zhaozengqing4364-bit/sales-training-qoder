import type { FoundationAdminLearnerListItem } from "@/lib/api/types/foundation-admin";
import type { FoundationJourneyActivity, FoundationJourneyProjection } from "@/lib/api/types/newcomer-training";

export function activityStatusLabel(activity: FoundationJourneyActivity): string {
    return activity.status_label;
}

export function journeyRiskActivities(journey: FoundationJourneyProjection): FoundationJourneyActivity[] {
    return journey.stages
        .flatMap((stage) => stage.activities)
        .filter((activity) => ["needs_remediation", "retryable", "invalidated"].includes(activity.status));
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

export function toTeamJourneyRow(item: FoundationAdminLearnerListItem): TeamJourneyRow {
    const current = item.current_activity;
    const riskLabels = current && ["needs_remediation", "retryable", "invalidated"].includes(current.status)
        ? [current.title]
        : item.status === "blocked" ? [item.status_label] : [];
    return {
        learnerId: item.learner.learner_id,
        learnerName: item.learner.name?.trim() || "未命名学员",
        currentPhase: current?.title ?? item.status_label,
        progressPercent: item.progress.percentage,
        completedCount: item.progress.completed_required,
        totalRequired: item.progress.total_required,
        riskLabels,
    };
}
