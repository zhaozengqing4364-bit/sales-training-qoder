import {
    Activity,
    AlertTriangle,
    CircleHelp,
    Lightbulb,
    TrendingDown,
    TrendingUp,
    type LucideIcon,
} from "lucide-react";

import type {
    AdminOperatingPackIssueBucket,
    AdminOperatingPackReasonBucket,
    AdminOperatingPackResponse,
    ManagerInterventionItem,
    ManagerInterventionResultItem,
    ManagerLiteListsResponse,
    UserProgressResponse,
    UserSessionItem,
    UserSessionsResponse,
} from "@/lib/api/types";
import { formatNotEvaluableReason } from "@/lib/session-evidence";

export type AdminProgressLoadState = "loading" | "success" | "empty" | "error";

export interface AdminTrendSummary {
    title: string;
    valueClassName: string;
    iconBgClassName: string;
    iconClassName: string;
    Icon: LucideIcon;
}

export interface AdminProgressOverview {
    title: string;
    subtitle: string;
    valueClassName: string;
    iconBgClassName: string;
    iconClassName: string;
    Icon: LucideIcon;
}

export interface AdminOperatingPackReadModel {
    operatingSummary: AdminOperatingPackResponse["weekly_summary"];
    managerLite: ManagerLiteListsResponse;
    repeatedBlockerFamilies: AdminOperatingPackIssueBucket[];
    departmentIssueBuckets: AdminOperatingPackResponse["department_issue_buckets"];
    topBlockerFamily: AdminOperatingPackIssueBucket | null;
    topDegradedReason: AdminOperatingPackReasonBucket | null;
}

export const EMPTY_ADMIN_MANAGER_LITE_LISTS: ManagerLiteListsResponse = {
    not_passed: [],
    inactive_streak: [],
    improving: [],
};

export const EMPTY_ADMIN_OPERATING_PACK: AdminOperatingPackResponse = {
    score_basis: "session_evidence_projection_evaluable_only",
    weekly_summary: {
        window_days: 7,
        window_start: null,
        window_end: null,
        completed_sessions: 0,
        evaluable_sessions: 0,
        not_evaluable_sessions: 0,
        degraded_sessions: 0,
        active_departments: 0,
        at_risk_users: 0,
        improving_users: 0,
        top_issue_family: null,
        top_blocker_family: null,
        top_not_evaluable_reason: null,
        top_degraded_reason: null,
    },
    cohort_issue_buckets: [],
    department_issue_buckets: [],
    repeated_blocker_families: [],
    degradation_breakdown: {
        not_evaluable_reasons: [],
        degraded_reasons: [],
    },
    manager_lists: EMPTY_ADMIN_MANAGER_LITE_LISTS,
};

export const EMPTY_ADMIN_USER_SESSIONS: UserSessionsResponse = {
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
    has_more: false,
    manager_intervention_results: [],
};

export const EMPTY_ADMIN_MANAGER_INTERVENTIONS: ManagerInterventionItem[] = [];

const SCORE_BASIS_LABELS: Record<string, string> = {
    session_evidence_projection_evaluable_only: "统一训练证据 · 仅统计可评估的已完成训练",
};

const DEGRADED_REASON_LABELS: Record<string, string> = {
    message_scores: "消息级评分缺失",
    stage_evidence: "阶段证据缺失",
    page_metadata: "页码证据缺失",
    page_summary: "页级总结缺失",
};

const ADMIN_USER_STATUS_LABELS: Record<string, string> = {
    active: "活跃",
    inactive: "停用",
    offline: "离线",
    suspended: "已停用",
};

const ADMIN_USER_ROLE_LABELS: Record<string, string> = {
    admin: "管理员",
    support: "支持角色",
    user: "普通用户",
    manager: "经理",
    editor: "编辑",
    viewer: "访客",
};

export function formatAdminScoreBasisLabel(scoreBasis?: string | null): string {
    if (!scoreBasis) {
        return "统一训练证据口径";
    }
    return SCORE_BASIS_LABELS[scoreBasis] || scoreBasis;
}

export function formatAdminDegradedReasonLabel(reason?: string | null): string {
    if (!reason) {
        return "暂无降级原因";
    }
    return DEGRADED_REASON_LABELS[reason] || reason;
}

export function formatAdminUserStatusLabel(status?: string | null): string {
    if (!status) {
        return "未知状态";
    }
    return ADMIN_USER_STATUS_LABELS[status] || status;
}

export function formatAdminUserRoleLabel(role?: string | null): string {
    if (!role) {
        return "未分配角色";
    }
    return ADMIN_USER_ROLE_LABELS[role] || role;
}

export function formatAdminRelativeTime(dateString?: string | null): string {
    if (!dateString) return "从未";
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) return "刚刚";
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}分钟前`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}小时前`;
    if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)}天前`;
    return date.toLocaleDateString();
}

export function buildOperatingPackReadModel(
    operatingPack: AdminOperatingPackResponse | null | undefined,
): AdminOperatingPackReadModel {
    const resolvedOperatingPack = operatingPack || EMPTY_ADMIN_OPERATING_PACK;
    const operatingSummary = resolvedOperatingPack.weekly_summary;

    return {
        operatingSummary,
        managerLite: resolvedOperatingPack.manager_lists || EMPTY_ADMIN_MANAGER_LITE_LISTS,
        repeatedBlockerFamilies: resolvedOperatingPack.repeated_blocker_families.length > 0
            ? resolvedOperatingPack.repeated_blocker_families
            : resolvedOperatingPack.cohort_issue_buckets,
        departmentIssueBuckets: resolvedOperatingPack.department_issue_buckets,
        topBlockerFamily: operatingSummary.top_blocker_family ?? operatingSummary.top_issue_family ?? null,
        topDegradedReason: operatingSummary.top_degraded_reason
            ?? resolvedOperatingPack.degradation_breakdown.degraded_reasons[0]
            ?? null,
    };
}

export function hasEvaluableUserProgress(
    progress: UserProgressResponse | null | undefined,
): progress is UserProgressResponse {
    return Boolean(progress && progress.evaluable_session_count > 0 && progress.trend_data.length > 0);
}

export function getUserProgressRecommendationLabel(progress?: UserProgressResponse | null): string {
    if (!progress) {
        return "等待连续变化数据";
    }
    if (progress.should_switch_focus) {
        return "建议切换训练重点";
    }
    switch (progress.recommendation.reason) {
        case "repeat_focus_until_stable":
            return "继续补同一重点";
        case "insufficient_evaluable_history":
            return "先补齐有效互动";
        default:
            return "继续观察当前重点";
    }
}

export function getAdminTrendSummary(improvementRate: number): AdminTrendSummary {
    if (improvementRate > 5) {
        return {
            title: "最近有明显进步",
            valueClassName: "text-emerald-700",
            iconBgClassName: "bg-emerald-50",
            iconClassName: "text-emerald-600",
            Icon: TrendingUp,
        };
    }
    if (improvementRate > 0) {
        return {
            title: "最近在改善",
            valueClassName: "text-blue-700",
            iconBgClassName: "bg-blue-50",
            iconClassName: "text-blue-600",
            Icon: TrendingUp,
        };
    }
    if (improvementRate < 0) {
        return {
            title: "最近在回落",
            valueClassName: "text-rose-700",
            iconBgClassName: "bg-rose-50",
            iconClassName: "text-rose-600",
            Icon: TrendingDown,
        };
    }
    return {
        title: "最近基本持平",
        valueClassName: "text-slate-700",
        iconBgClassName: "bg-slate-100",
        iconClassName: "text-slate-600",
        Icon: Activity,
    };
}

export function buildUserProgressOverview(
    progressState: AdminProgressLoadState,
    progress: UserProgressResponse | null,
    progressError: string | null,
): AdminProgressOverview {
    if (progressState === "error") {
        return {
            title: "加载失败",
            subtitle: progressError || "连续变化视图暂时不可用。",
            valueClassName: "text-rose-700",
            iconBgClassName: "bg-rose-50",
            iconClassName: "text-rose-600",
            Icon: AlertTriangle,
        };
    }

    if (progressState === "empty" && progress) {
        return {
            title: "证据不足",
            subtitle: progress.completed_session_count > 0
                ? `最近 ${progress.not_evaluable_session_count} 次已完成训练暂不可评估。`
                : "当前时间范围内还没有已完成训练。",
            valueClassName: "text-amber-700",
            iconBgClassName: "bg-amber-50",
            iconClassName: "text-amber-600",
            Icon: CircleHelp,
        };
    }

    if (hasEvaluableUserProgress(progress)) {
        const trendSummary = getAdminTrendSummary(progress.improvement_rate);
        return {
            title: getUserProgressRecommendationLabel(progress),
            subtitle: `${trendSummary.title} · ${progress.evaluable_session_count} 次可评估训练`,
            valueClassName: progress.should_switch_focus ? "text-amber-700" : "text-slate-900",
            iconBgClassName: progress.should_switch_focus ? "bg-amber-50" : trendSummary.iconBgClassName,
            iconClassName: progress.should_switch_focus ? "text-amber-600" : trendSummary.iconClassName,
            Icon: progress.should_switch_focus ? Lightbulb : trendSummary.Icon,
        };
    }

    return {
        title: "等待连续变化数据",
        subtitle: "完成训练后这里会更新主管判断。",
        valueClassName: "text-slate-700",
        iconBgClassName: "bg-slate-100",
        iconClassName: "text-slate-600",
        Icon: Activity,
    };
}

export function getUserSessionOverallResultLabel(session: UserSessionItem): string {
    if (session.evaluable === false) return "不可评估";
    if (session.overall_result === "strong_pass") return "Strong Pass";
    if (session.overall_result === "pass") return "Pass";
    if (session.overall_result === "fail") return "Fail";
    return "进行中";
}

export function getUserSessionOverallResultTone(session: UserSessionItem): string {
    if (session.evaluable === false) return "bg-amber-50 text-amber-700";
    if (session.overall_result === "strong_pass") return "bg-emerald-50 text-emerald-700";
    if (session.overall_result === "pass") return "bg-blue-50 text-blue-700";
    if (session.overall_result === "fail") return "bg-rose-50 text-rose-700";
    return "bg-slate-50 text-slate-500";
}

export function getUserSessionPreview(session: UserSessionItem): string {
    if (session.status !== "completed") {
        return "练习完成后会显示统一报告预览。";
    }
    if (session.evaluable === false) {
        return formatNotEvaluableReason(session.not_evaluable_reason);
    }
    return session.feedback_summary
        || session.main_issue?.issue_text
        || session.next_goal?.goal_text
        || "统一训练证据已生成，可进入报告页查看详情。";
}

export function buildInterventionResultById(
    sessions: Pick<UserSessionsResponse, "manager_intervention_results"> | null | undefined,
): Map<string, ManagerInterventionResultItem> {
    return new Map((sessions?.manager_intervention_results || []).map((item) => [item.intervention_id, item]));
}
