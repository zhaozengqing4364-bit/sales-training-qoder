"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    UserDetailStats,
    UserSessionItem,
    UserSessionsResponse,
    UserProgressResponse,
} from "@/lib/api/types";
import {
    formatGoalTypeLabel,
    formatIssueTypeLabel,
    formatNotEvaluableReason,
} from "@/lib/session-evidence";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import {
    ArrowLeft,
    Calendar,
    Clock,
    Target,
    TrendingUp,
    TrendingDown,
    Award,
    BarChart3,
    Activity,
    RefreshCw,
    AlertTriangle,
    Lightbulb,
    CircleHelp,
    type LucideIcon,
} from "lucide-react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

type TimeRange = "7d" | "30d" | "90d" | "all_time";
type ProgressLoadState = "loading" | "success" | "empty" | "error";

type ProgressOverview = {
    title: string;
    subtitle: string;
    valueClassName: string;
    iconBgClassName: string;
    iconClassName: string;
    Icon: LucideIcon;
};

const EMPTY_SESSIONS: UserSessionsResponse = {
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
    has_more: false,
};

function hasEvaluableProgress(progress: UserProgressResponse | null): progress is UserProgressResponse {
    return Boolean(progress && progress.evaluable_session_count > 0 && progress.trend_data.length > 0);
}

function getProgressRecommendationLabel(progress?: UserProgressResponse | null): string {
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

function getTrendSummary(improvementRate: number): {
    title: string;
    valueClassName: string;
    iconBgClassName: string;
    iconClassName: string;
    Icon: LucideIcon;
} {
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

function buildProgressOverview(
    progressState: ProgressLoadState,
    progress: UserProgressResponse | null,
    progressError: string | null,
): ProgressOverview {
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

    if (hasEvaluableProgress(progress)) {
        const trendSummary = getTrendSummary(progress.improvement_rate);
        return {
            title: getProgressRecommendationLabel(progress),
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

export default function UserDetailPage() {
    const params = useParams();
    const router = useRouter();
    const userId = params.id as string;

    const [timeRange, setTimeRange] = useState<TimeRange>("30d");
    const [stats, setStats] = useState<UserDetailStats | null>(null);
    const [sessions, setSessions] = useState<UserSessionsResponse>(EMPTY_SESSIONS);
    const [progress, setProgress] = useState<UserProgressResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [pageError, setPageError] = useState<string | null>(null);
    const [sessionsError, setSessionsError] = useState<string | null>(null);
    const [progressError, setProgressError] = useState<string | null>(null);
    const [progressState, setProgressState] = useState<ProgressLoadState>("loading");
    const [sessionsPage, setSessionsPage] = useState(1);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        setPageError(null);
        setSessionsError(null);
        setProgressError(null);
        setProgressState("loading");

        const [statsResult, sessionsResult, progressResult] = await Promise.allSettled([
            api.admin.getUserStats(userId, { time_range: timeRange }),
            api.admin.getUserSessions(userId, { page: 1, page_size: 10 }),
            api.admin.getUserProgress(userId, { time_range: timeRange }),
        ]);

        if (statsResult.status === "fulfilled") {
            setStats(statsResult.value);
        } else {
            setStats(null);
            setPageError(getApiErrorMessage(statsResult.reason));
        }

        if (sessionsResult.status === "fulfilled") {
            setSessions(sessionsResult.value);
            setSessionsPage(1);
        } else {
            setSessions(EMPTY_SESSIONS);
            setSessionsError(`练习记录加载失败：${getApiErrorMessage(sessionsResult.reason)}`);
        }

        if (progressResult.status === "fulfilled") {
            setProgress(progressResult.value);
            setProgressState(hasEvaluableProgress(progressResult.value) ? "success" : "empty");
        } else {
            setProgress(null);
            setProgressError(`连续变化视图加载失败：${getApiErrorMessage(progressResult.reason)}`);
            setProgressState("error");
        }

        setIsLoading(false);
    }, [timeRange, userId]);

    const loadMoreSessions = async () => {
        if (!sessions.has_more) return;

        try {
            const nextPage = sessionsPage + 1;
            const data = await api.admin.getUserSessions(userId, {
                page: nextPage,
                page_size: 10,
            });

            setSessions({
                ...data,
                items: [...sessions.items, ...data.items],
            });
            setSessionsPage(nextPage);
        } catch (err) {
            setSessionsError(`练习记录加载失败：${getApiErrorMessage(err)}`);
        }
    };

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const timeRangeOptions: { value: TimeRange; label: string }[] = [
        { value: "7d", label: "7天" },
        { value: "30d", label: "30天" },
        { value: "90d", label: "90天" },
        { value: "all_time", label: "全部" },
    ];

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return "-";
        return new Date(dateStr).toLocaleString("zh-CN", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "completed":
                return "bg-green-50 text-green-600";
            case "in_progress":
                return "bg-blue-50 text-blue-600";
            case "scoring":
                return "bg-amber-50 text-amber-600";
            default:
                return "bg-slate-50 text-slate-600";
        }
    };

    const getScoreColor = (score: number | null) => {
        if (score === null) return "text-slate-400";
        if (score >= 90) return "text-green-600";
        if (score >= 70) return "text-blue-600";
        if (score >= 50) return "text-amber-600";
        return "text-red-600";
    };

    const getOverallResultLabel = (session: UserSessionItem) => {
        if (session.evaluable === false) return "不可评估";
        if (session.overall_result === "strong_pass") return "Strong Pass";
        if (session.overall_result === "pass") return "Pass";
        if (session.overall_result === "fail") return "Fail";
        return "进行中";
    };

    const getOverallResultTone = (session: UserSessionItem) => {
        if (session.evaluable === false) return "bg-amber-50 text-amber-700";
        if (session.overall_result === "strong_pass") return "bg-emerald-50 text-emerald-700";
        if (session.overall_result === "pass") return "bg-blue-50 text-blue-700";
        if (session.overall_result === "fail") return "bg-rose-50 text-rose-700";
        return "bg-slate-50 text-slate-500";
    };

    const getSessionPreview = (session: UserSessionItem) => {
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
    };

    if (isLoading) {
        return (
            <div className="space-y-8 animate-in fade-in">
                <div className="flex items-center gap-4">
                    <div className="h-10 w-10 bg-slate-200 rounded-full animate-pulse" />
                    <div className="h-8 w-48 bg-slate-200 rounded-lg animate-pulse" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    {[1, 2, 3, 4].map((i) => (
                        <GlassCard key={i} className="p-6 h-32 animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    if (!stats) {
        return (
            <div className="flex flex-col items-center justify-center py-20">
                <p className="text-slate-500">{pageError || "用户不存在或加载失败"}</p>
                <Button onClick={() => void loadData()} className="mt-4 rounded-full">
                    重试
                </Button>
            </div>
        );
    }

    const { user, statistics } = stats;
    const progressOverview = buildProgressOverview(progressState, progress, progressError);
    const strongestIssue = progress?.repeated_main_issues?.[0] ?? null;
    const strongestGoal = progress?.repeated_next_goals?.[0] ?? null;
    const trendSummary = hasEvaluableProgress(progress)
        ? getTrendSummary(progress.improvement_rate)
        : null;
    const latestTrendPoint = hasEvaluableProgress(progress)
        ? progress.trend_data[progress.trend_data.length - 1]
        : null;

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.back()}
                        className="rounded-full"
                        aria-label="返回上一页"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg">
                            {(user.display_name || user.email || "U").charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <h1 className="text-2xl font-black text-slate-900 text-balance">
                                {user.display_name || user.email || "未知用户"}
                            </h1>
                            <p className="text-slate-500 text-sm text-pretty">
                                {user.department || "未设置部门"} · {user.email}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex flex-wrap gap-3">
                    <div className="flex bg-slate-100 rounded-full p-1">
                        {timeRangeOptions.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => setTimeRange(option.value)}
                                className={`px-4 py-2 text-sm font-medium rounded-full transition-all ${
                                    timeRange === option.value
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                    <Button
                        variant="outline"
                        onClick={() => void loadData()}
                        className="rounded-full"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        刷新
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-blue-50 flex items-center justify-center">
                            <Target className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">练习次数</p>
                            <p className="text-2xl font-black text-slate-900 tabular-nums">
                                {statistics.total_sessions}
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2 text-pretty">
                        完成 {statistics.completed_sessions} 次 ({statistics.completion_rate}%)
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-green-50 flex items-center justify-center">
                            <Award className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">平均分</p>
                            <p className={`text-2xl font-black tabular-nums ${getScoreColor(statistics.average_score)}`}>
                                {statistics.average_score}
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2 text-pretty">
                        最高 {statistics.best_score} / 最低 {statistics.worst_score}
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className="size-10 rounded-xl bg-purple-50 flex items-center justify-center">
                            <Clock className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">练习时长</p>
                            <p className="text-2xl font-black text-slate-900 tabular-nums">
                                {Math.round(statistics.total_duration_minutes)} 分钟
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2 text-pretty">
                        最近: {formatDate(statistics.last_practice)}
                    </p>
                </GlassCard>

                <GlassCard className="p-5">
                    <div className="flex items-center gap-3">
                        <div className={`size-10 rounded-xl flex items-center justify-center ${progressOverview.iconBgClassName}`}>
                            <progressOverview.Icon className={`w-5 h-5 ${progressOverview.iconClassName}`} />
                        </div>
                        <div>
                            <p className="text-sm text-slate-500">训练建议</p>
                            <p className={`text-lg font-black leading-tight text-balance ${progressOverview.valueClassName}`}>
                                {progressOverview.title}
                            </p>
                        </div>
                    </div>
                    <p className="text-xs text-slate-400 mt-2 text-pretty">
                        {progressOverview.subtitle}
                    </p>
                </GlassCard>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GlassCard className="p-6">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2 text-balance">
                                <Activity className="w-5 h-5 text-blue-600" />
                                连续变化判断
                            </h2>
                            <p className="mt-2 text-sm text-slate-500 text-pretty">
                                基于统一训练证据，直接回答最近有没有进步、总卡在哪，以及下一轮要不要换重点。
                            </p>
                        </div>
                        {progress ? (
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                                {progress.granularity === "week" ? "按周聚合" : "按日聚合"}
                            </span>
                        ) : null}
                    </div>

                    {progressState === "error" ? (
                        <div role="alert" className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-5">
                            <p className="text-sm font-semibold text-rose-900">连续变化视图加载失败</p>
                            <p className="mt-2 text-sm text-rose-700 text-pretty">{progressError}</p>
                            <Button
                                variant="outline"
                                onClick={() => void loadData()}
                                className="mt-4 rounded-full"
                            >
                                重试连续变化
                            </Button>
                        </div>
                    ) : progressState === "empty" && progress ? (
                        <div role="status" className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5 space-y-3">
                            <p className="text-sm font-semibold text-amber-900">暂无可评估训练数据</p>
                            <p className="text-sm text-amber-800 text-pretty">
                                {progress.completed_session_count > 0
                                    ? `最近 ${progress.not_evaluable_session_count} 次已完成训练仍证据不足，暂时不能回答是否进步。`
                                    : "当前时间范围内还没有已完成训练，暂时不能判断是否进步。"}
                            </p>
                            <p className="text-sm text-amber-800 text-pretty">{progress.recommendation.summary}</p>
                        </div>
                    ) : hasEvaluableProgress(progress) && trendSummary && latestTrendPoint ? (
                        <div className="mt-6 space-y-5">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                    <p className="text-sm font-semibold text-slate-900">最近趋势</p>
                                    <div className="mt-3 flex items-center gap-3">
                                        <div className={`size-10 rounded-xl flex items-center justify-center ${trendSummary.iconBgClassName}`}>
                                            <trendSummary.Icon className={`w-5 h-5 ${trendSummary.iconClassName}`} />
                                        </div>
                                        <div>
                                            <p className={`text-base font-semibold ${trendSummary.valueClassName}`}>
                                                {trendSummary.title}
                                            </p>
                                            <p className="text-sm text-slate-600 tabular-nums text-pretty">
                                                最近 {progress.total_data_points} 个时间段的可评估训练平均分变化
                                                {progress.improvement_rate > 0 ? "+" : ""}
                                                {progress.improvement_rate}%
                                            </p>
                                        </div>
                                    </div>
                                    <p className="mt-3 text-xs text-slate-500 text-pretty">
                                        最新趋势点：{latestTrendPoint.average_score} 分，纳入 {latestTrendPoint.evaluable_session_count} 次可评估训练。
                                    </p>
                                </div>

                                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                    <p className="text-sm font-semibold text-slate-900">训练建议</p>
                                    <p className={`mt-3 text-base font-semibold ${progress.should_switch_focus ? "text-amber-700" : "text-slate-900"}`}>
                                        {getProgressRecommendationLabel(progress)}
                                    </p>
                                    <p className="mt-2 text-sm text-slate-600 text-pretty">
                                        {progress.recommendation.summary}
                                    </p>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="rounded-2xl border border-slate-200 p-4">
                                    <p className="text-sm font-semibold text-slate-900">反复卡点</p>
                                    {strongestIssue ? (
                                        <>
                                            {formatIssueTypeLabel(strongestIssue.issue_type) ? (
                                                <span className="mt-3 inline-flex rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">
                                                    {formatIssueTypeLabel(strongestIssue.issue_type)}
                                                </span>
                                            ) : null}
                                            <p className="mt-3 text-base font-medium text-slate-900 text-pretty">
                                                {strongestIssue.issue_text}
                                            </p>
                                            <p className="mt-2 text-sm text-slate-600 tabular-nums text-pretty">
                                                最近 {strongestIssue.count} 次可评估训练反复出现同一问题。
                                            </p>
                                        </>
                                    ) : (
                                        <p className="mt-3 text-sm text-slate-500 text-pretty">
                                            最近没有形成稳定重复的主问题，先继续观察下一轮表现。
                                        </p>
                                    )}
                                </div>

                                <div className="rounded-2xl border border-slate-200 p-4">
                                    <p className="text-sm font-semibold text-slate-900">重复下一轮重点</p>
                                    {strongestGoal ? (
                                        <>
                                            {formatGoalTypeLabel(strongestGoal.goal_type) ? (
                                                <span className="mt-3 inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                                                    {formatGoalTypeLabel(strongestGoal.goal_type)}
                                                </span>
                                            ) : null}
                                            <p className="mt-3 text-base font-medium text-slate-900 text-pretty">
                                                {strongestGoal.goal_text}
                                            </p>
                                            <p className="mt-2 text-sm text-slate-600 tabular-nums text-pretty">
                                                最近 {strongestGoal.count} 次都指向同一训练动作。
                                            </p>
                                        </>
                                    ) : (
                                        <p className="mt-3 text-sm text-slate-500 text-pretty">
                                            最近没有稳定重复的下一轮重点，说明当前训练目标还在变化。
                                        </p>
                                    )}
                                </div>
                            </div>

                            {(progress.not_evaluable_session_count > 0 || progress.non_completed_session_count > 0) ? (
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                    <p className="text-sm font-semibold text-slate-900">证据不足 / 未纳入趋势</p>
                                    <p className="mt-2 text-sm text-slate-600 text-pretty">
                                        {progress.not_evaluable_session_count > 0
                                            ? `已完成训练里有 ${progress.not_evaluable_session_count} 次仍证据不足，判断趋势时没有把它算进分数线。`
                                            : "当前已完成训练都已纳入连续变化判断。"}
                                        {progress.non_completed_session_count > 0
                                            ? ` 另外还有 ${progress.non_completed_session_count} 次未完成训练暂不纳入连续变化判断。`
                                            : ""}
                                    </p>
                                </div>
                            ) : null}

                            <div className="rounded-2xl border border-slate-200 p-4">
                                <p className="text-sm font-semibold text-slate-900">辅助趋势</p>
                                <p className="mt-1 text-xs text-slate-500 text-pretty">
                                    折线只作为辅助判断，真正的主管决策以上面的重复卡点、重复目标和建议为准。
                                </p>
                                <div className="mt-4 h-64">
                                    <ResponsiveContainer width="100%" height={240}>
                                        <LineChart data={progress.trend_data}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                            <XAxis
                                                dataKey="date"
                                                tick={{ fontSize: 12, fill: "#64748b" }}
                                                tickFormatter={(value) => String(value).slice(5, 10)}
                                            />
                                            <YAxis
                                                domain={[0, 100]}
                                                tick={{ fontSize: 12, fill: "#64748b" }}
                                            />
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: "white",
                                                    border: "none",
                                                    borderRadius: "12px",
                                                    boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
                                                }}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="average_score"
                                                name="综合分"
                                                stroke="#2563eb"
                                                strokeWidth={2}
                                                dot={{ fill: "#2563eb", r: 4 }}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    ) : null}
                </GlassCard>

                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2 text-balance">
                        <BarChart3 className="w-5 h-5 text-purple-600" />
                        使用统计
                    </h3>
                    <div className="space-y-6">
                        <div>
                            <p className="text-sm font-medium text-slate-600 mb-3">Agent 使用</p>
                            {stats.agent_usage.length > 0 ? (
                                <div className="space-y-2">
                                    {stats.agent_usage.map((item, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-center justify-between p-3 bg-slate-50 rounded-xl"
                                        >
                                            <span className="font-medium text-slate-700">{item.name}</span>
                                            <span className="text-sm text-slate-500 tabular-nums">{item.count} 次</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-400">暂无数据</p>
                            )}
                        </div>

                        <div>
                            <p className="text-sm font-medium text-slate-600 mb-3">Persona 使用</p>
                            {stats.persona_usage.length > 0 ? (
                                <div className="space-y-2">
                                    {stats.persona_usage.map((item, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-center justify-between p-3 bg-slate-50 rounded-xl"
                                        >
                                            <span className="font-medium text-slate-700">{item.name}</span>
                                            <span className="text-sm text-slate-500 tabular-nums">{item.count} 次</span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-400">暂无数据</p>
                            )}
                        </div>
                    </div>
                </GlassCard>
            </div>

            <GlassCard className="p-6">
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2 text-balance">
                    <Calendar className="w-5 h-5 text-blue-600" />
                    练习记录
                </h3>

                {sessionsError ? (
                    <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5">
                        <p className="text-sm text-rose-800 text-pretty">{sessionsError}</p>
                    </div>
                ) : sessions.items.length > 0 ? (
                    <>
                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[980px]">
                                <thead>
                                    <tr className="border-b border-slate-100">
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            时间
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            场景
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            Agent / Persona
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            状态
                                        </th>
                                        <th className="text-left py-3 px-4 text-sm font-medium text-slate-500">
                                            统一预览
                                        </th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-slate-500">
                                            时长
                                        </th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-slate-500">
                                            得分
                                        </th>
                                        <th className="text-right py-3 px-4 text-sm font-medium text-slate-500">
                                            操作
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sessions.items.map((session) => (
                                        <tr
                                            key={session.session_id}
                                            className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors"
                                        >
                                            <td className="py-3 px-4 text-sm text-slate-700 align-top">
                                                {formatDate(session.start_time)}
                                            </td>
                                            <td className="py-3 px-4 align-top">
                                                <span className="text-sm font-medium text-slate-700">
                                                    {session.scenario_name || session.scenario_type || "-"}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-sm text-slate-600 align-top">
                                                {session.agent_name || "-"}
                                                {session.persona_name && ` / ${session.persona_name}`}
                                            </td>
                                            <td className="py-3 px-4 align-top">
                                                <div className="space-y-2">
                                                    <span
                                                        className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(
                                                            session.status
                                                        )}`}
                                                    >
                                                        {session.status === "completed"
                                                            ? "已完成"
                                                            : session.status === "in_progress"
                                                                ? "进行中"
                                                                : session.status}
                                                    </span>
                                                    {session.status === "completed" ? (
                                                        <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${getOverallResultTone(session)}`}>
                                                            {getOverallResultLabel(session)}
                                                        </span>
                                                    ) : null}
                                                </div>
                                            </td>
                                            <td className="py-3 px-4 align-top">
                                                <div className="space-y-1 max-w-sm">
                                                    <p className="text-sm text-slate-700 text-pretty">
                                                        {getSessionPreview(session)}
                                                    </p>
                                                    {session.next_goal?.goal_text ? (
                                                        <p className="text-xs text-slate-500 text-pretty">
                                                            <span className="text-slate-400">下一轮：</span>
                                                            <span>{session.next_goal.goal_text}</span>
                                                        </p>
                                                    ) : null}
                                                </div>
                                            </td>
                                            <td className="py-3 px-4 text-sm text-slate-600 text-right align-top tabular-nums">
                                                {session.duration_minutes.toFixed(1)} 分钟
                                            </td>
                                            <td className="py-3 px-4 text-right align-top">
                                                <span
                                                    className={`text-lg font-bold tabular-nums ${getScoreColor(
                                                        session.scores.overall
                                                    )}`}
                                                >
                                                    {session.scores.overall ?? "-"}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-right align-top">
                                                {session.status === "completed" ? (
                                                    <Button asChild variant="outline" size="sm" className="rounded-full">
                                                        <Link href={`/practice/${session.session_id}/report`}>
                                                            查看报告
                                                        </Link>
                                                    </Button>
                                                ) : (
                                                    <span className="text-xs text-slate-400">完成后可查看</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {sessions.has_more && (
                            <div className="flex justify-center mt-4">
                                <Button
                                    variant="outline"
                                    onClick={loadMoreSessions}
                                    className="rounded-full"
                                >
                                    加载更多
                                </Button>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="py-12 text-center text-slate-400">
                        暂无练习记录
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
