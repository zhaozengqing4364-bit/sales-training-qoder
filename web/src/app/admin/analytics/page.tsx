"use client";

import Link from "next/link";
import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "@/lib/api/client";
import {
    AnalyticsOverview,
    AnalyticsTrends,
    AnalyticsAgents,
    AnalyticsLeaderboard,
    AdminOperatingPackResponse,
    ManagerLiteListsResponse,
    OpenAnalyticsDashboard,
    SupportRuntimeFaultItem,
} from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { MetricsCards } from "@/components/analytics/MetricsCards";
import { TrendsChart } from "@/components/analytics/TrendsChart";
import { ScoreDistributionChart } from "@/components/analytics/ScoreDistributionChart";
import { AgentRankingChart } from "@/components/analytics/AgentRankingChart";
import { LeaderboardTable } from "@/components/analytics/LeaderboardTable";
import { ManagerLitePanel } from "@/components/admin/manager-lite-panel";
import {
    formatGoalTypeLabel,
    formatIssueTypeLabel,
    formatNotEvaluableReason,
} from "@/lib/session-evidence";
import {
    extractLinkedAssetChanges,
    formatLinkedAssetHealthStatusLabel,
    formatLinkedAssetImpactLevelLabel,
    formatLinkedAssetLabel,
    formatLinkedAssetLink,
} from "@/lib/admin/linked-assets";
import {
    Download,
    RefreshCw,
    Filter,
    Info,
    ShieldAlert,
    Target,
} from "lucide-react";

type TimeRange = "7d" | "30d" | "90d" | "all_time";
type CoreEffectiveness = NonNullable<OpenAnalyticsDashboard["effectiveness"]>;

const DEFAULT_EFFECTIVENESS: CoreEffectiveness = {
    pass_rate_3min_flow: 0,
    pass_rate_5turn_defense: 0,
    pass_rate_4step_structure: 0,
    next_day_retry_rate: 0,
};

const EMPTY_MANAGER_LITE: ManagerLiteListsResponse = {
    not_passed: [],
    inactive_streak: [],
    improving: [],
};

const EMPTY_OPERATING_PACK: AdminOperatingPackResponse = {
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
    manager_lists: EMPTY_MANAGER_LITE,
};

const SCORE_BASIS_LABELS: Record<string, string> = {
    session_evidence_projection_evaluable_only: "统一训练证据 · 仅统计可评估的已完成训练",
};

const DEGRADED_REASON_LABELS: Record<string, string> = {
    message_scores: "消息级评分缺失",
    stage_evidence: "阶段证据缺失",
    page_metadata: "页码证据缺失",
    page_summary: "页级总结缺失",
};

function formatScoreBasisLabel(scoreBasis?: string | null): string {
    if (!scoreBasis) {
        return "统一训练证据口径";
    }
    return SCORE_BASIS_LABELS[scoreBasis] || scoreBasis;
}

function formatDegradedReasonLabel(reason?: string | null): string {
    if (!reason) {
        return "暂无降级原因";
    }
    return DEGRADED_REASON_LABELS[reason] || reason;
}

function formatBucketLabel(count: number): string {
    return `Top ${Math.max(count, 0)}`;
}

function resolveWindowDays(timeRange: TimeRange): number {
    if (timeRange === "7d") return 7;
    if (timeRange === "90d") return 90;
    if (timeRange === "all_time") return 365;
    return 30;
}

export default function AnalyticsPage() {
    const [timeRange, setTimeRange] = useState<TimeRange>("30d");
    const [scenarioType, setScenarioType] = useState<string | null>(null);

    const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
    const [trends, setTrends] = useState<AnalyticsTrends | null>(null);
    const [agents, setAgents] = useState<AnalyticsAgents | null>(null);
    const [leaderboard, setLeaderboard] = useState<AnalyticsLeaderboard | null>(null);
    const [operatingPack, setOperatingPack] = useState<AdminOperatingPackResponse>(EMPTY_OPERATING_PACK);
    const [effectiveness, setEffectiveness] = useState<CoreEffectiveness>(DEFAULT_EFFECTIVENESS);
    const [runtimeFaults, setRuntimeFaults] = useState<SupportRuntimeFaultItem[]>([]);

    const [isLoading, setIsLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        const params = {
            time_range: timeRange,
            scenario_type: scenarioType || undefined,
        };

        const [overviewResult, trendsResult, agentsResult, leaderboardResult, operatingPackResult, effectivenessResult, runtimeFaultsResult] = await Promise.allSettled([
            api.analytics.getOverview(params),
            api.analytics.getTrends({ time_range: timeRange }),
            api.analytics.getAgents({ time_range: timeRange }),
            api.analytics.getLeaderboard({ time_range: timeRange, limit: 50 }),
            api.analytics.getOperatingPack({
                time_range: "7d",
                scenario_type: scenarioType || undefined,
                limit: 10,
                inactive_days: 7,
            }),
            api.analyticsOpen.getDashboard({
                scenario_type: scenarioType || undefined,
                days: resolveWindowDays(timeRange),
            }),
            api.supportRuntime.getFaults({ limit: 8 }),
        ]);

        if (overviewResult.status === "fulfilled") {
            setOverview(overviewResult.value);
        } else {
            console.error("Failed to load analytics overview:", overviewResult.reason);
            setOverview(null);
        }

        if (trendsResult.status === "fulfilled") {
            setTrends(trendsResult.value);
        } else {
            console.error("Failed to load analytics trends:", trendsResult.reason);
            setTrends(null);
        }

        if (agentsResult.status === "fulfilled") {
            setAgents(agentsResult.value);
        } else {
            console.error("Failed to load analytics agents:", agentsResult.reason);
            setAgents(null);
        }

        if (leaderboardResult.status === "fulfilled") {
            setLeaderboard(leaderboardResult.value);
        } else {
            console.error("Failed to load analytics leaderboard:", leaderboardResult.reason);
            setLeaderboard(null);
        }

        if (operatingPackResult.status === "fulfilled") {
            setOperatingPack(operatingPackResult.value);
        } else {
            console.error("Failed to load analytics operating pack:", operatingPackResult.reason);
            setOperatingPack(EMPTY_OPERATING_PACK);
        }

        if (effectivenessResult.status === "fulfilled") {
            setEffectiveness(effectivenessResult.value.effectiveness || DEFAULT_EFFECTIVENESS);
        } else {
            console.error("Failed to load effectiveness metrics:", effectivenessResult.reason);
            setEffectiveness(DEFAULT_EFFECTIVENESS);
        }

        if (runtimeFaultsResult.status === "fulfilled") {
            setRuntimeFaults(runtimeFaultsResult.value.items || []);
        } else {
            console.error("Failed to load support runtime faults:", runtimeFaultsResult.reason);
            setRuntimeFaults([]);
        }

        setIsLoading(false);
    }, [timeRange, scenarioType]);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const handleExport = async () => {
        setIsExporting(true);
        try {
            await api.analytics.exportReport({ time_range: timeRange, format: "csv" });
        } catch (err) {
            console.error("Export failed:", err);
        } finally {
            setIsExporting(false);
        }
    };

    const handleManagerRemind = async (userId: string) => {
        try {
            await api.analytics.remindFromManagerLite({
                user_id: userId,
                note: "请按本周训练目标完成一次练习并提交结果。",
            });
            await loadData();
        } catch (err) {
            console.error("Manager remind failed:", err);
        }
    };

    const projectionSummary = trends?.projection_summary;
    const operatingSummary = operatingPack.weekly_summary;
    const managerLite = operatingPack.manager_lists;
    const repeatedBlockerFamilies = operatingPack.repeated_blocker_families.length > 0
        ? operatingPack.repeated_blocker_families
        : operatingPack.cohort_issue_buckets;
    const departmentIssueBuckets = operatingPack.department_issue_buckets;
    const evaluableSessions = overview?.evaluable_sessions ?? projectionSummary?.evaluable_sessions ?? 0;
    const notEvaluableSessions = overview?.not_evaluable_sessions ?? projectionSummary?.not_evaluable_sessions ?? 0;
    const scoreBasis = overview?.score_basis ?? projectionSummary?.score_basis ?? null;

    const topIssueFamily = useMemo(() => {
        return overview?.top_issue_families?.[0] ?? projectionSummary?.issue_family_distribution?.[0] ?? null;
    }, [overview, projectionSummary]);

    const topReason = useMemo(() => {
        return overview?.not_evaluable_reasons?.[0] ?? projectionSummary?.not_evaluable_reasons?.[0] ?? null;
    }, [overview, projectionSummary]);

    const topBlockerFamily = operatingSummary.top_blocker_family ?? operatingSummary.top_issue_family ?? null;
    const topDegradedReason = operatingSummary.top_degraded_reason ?? operatingPack.degradation_breakdown.degraded_reasons[0] ?? null;
    const repeatedGoal = projectionSummary?.repeated_next_goals?.[0] ?? null;
    const leaderboardLeader = leaderboard?.leaderboard?.[0] ?? null;
    const linkedRuntimeFaults = useMemo(() => {
        return runtimeFaults
            .map((fault) => ({
                fault,
                assetChanges: extractLinkedAssetChanges(fault),
            }))
            .filter((entry) => entry.assetChanges.length > 0)
            .slice(0, 3);
    }, [runtimeFaults]);

    const topIssueLabel = topIssueFamily
        ? (formatIssueTypeLabel(topIssueFamily.issue_type) || topIssueFamily.issue_type)
        : null;
    const topReasonLabel = topReason
        ? formatNotEvaluableReason(topReason.reason)
        : null;
    const topBlockerLabel = topBlockerFamily
        ? (formatIssueTypeLabel(topBlockerFamily.issue_type) || topBlockerFamily.issue_type || topBlockerFamily.issue_family)
        : null;
    const topDegradedReasonLabel = topDegradedReason
        ? formatDegradedReasonLabel(topDegradedReason.reason)
        : null;
    const repeatedGoalLabel = repeatedGoal
        ? (formatGoalTypeLabel(repeatedGoal.goal_type) || repeatedGoal.goal_type)
        : null;
    const leaderIssueLabel = leaderboardLeader?.primary_issue_type
        ? (formatIssueTypeLabel(leaderboardLeader.primary_issue_type) || leaderboardLeader.primary_issue_type)
        : null;
    const leaderGoalLabel = leaderboardLeader?.primary_next_goal_type
        ? (formatGoalTypeLabel(leaderboardLeader.primary_next_goal_type) || leaderboardLeader.primary_next_goal_type)
        : null;

    const timeRangeOptions: { value: TimeRange; label: string }[] = [
        { value: "7d", label: "7天" },
        { value: "30d", label: "30天" },
        { value: "90d", label: "90天" },
        { value: "all_time", label: "全部" },
    ];

    const scenarioOptions = [
        { value: null, label: "全部场景" },
        { value: "sales", label: "销售对练" },
        { value: "presentation", label: "PPT演练" },
    ];

    if (isLoading) {
        return (
            <div className="space-y-8 animate-in fade-in">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <div className="h-8 w-48 bg-slate-200 rounded-lg animate-pulse" />
                        <div className="h-4 w-72 bg-slate-100 rounded mt-2 animate-pulse" />
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {[1, 2, 3, 4].map((i) => (
                        <GlassCard key={i} className="p-6 h-32 animate-pulse">
                            <div className="h-4 w-20 bg-slate-200 rounded mb-3" />
                            <div className="h-8 w-24 bg-slate-200 rounded" />
                        </GlassCard>
                    ))}
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <GlassCard className="col-span-2 p-6 h-80 animate-pulse" />
                    <GlassCard className="p-6 h-80 animate-pulse" />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">数据分析</h1>
                    <p className="text-slate-500 mt-1 text-pretty">
                        当前页直接展示统一训练证据：综合分只纳入可评估训练，证据不足会话单独记账，不再混进平均分。
                    </p>
                </div>
                <div className="flex flex-wrap gap-3">
                    <div className="flex bg-slate-100 rounded-full p-1">
                        {timeRangeOptions.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => setTimeRange(option.value)}
                                className={`px-4 py-2 text-sm font-medium rounded-full transition-all ${timeRange === option.value
                                        ? "bg-white text-slate-900 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700"
                                    }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>

                    <div className="relative">
                        <select
                            value={scenarioType || ""}
                            onChange={(e) => setScenarioType(e.target.value || null)}
                            className="appearance-none bg-white border border-slate-200 rounded-full px-4 py-2 pr-10 text-sm font-medium text-slate-700 cursor-pointer hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            {scenarioOptions.map((option) => (
                                <option key={option.value || "all"} value={option.value || ""}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                        <Filter className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    </div>

                    <Button
                        variant="outline"
                        onClick={() => void loadData()}
                        className="rounded-full border-slate-200"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        刷新
                    </Button>

                    <Button
                        onClick={handleExport}
                        disabled={isExporting}
                        className="rounded-full bg-slate-900 text-white hover:bg-slate-800"
                    >
                        <Download className="w-4 h-4 mr-2" />
                        {isExporting ? "导出中..." : "导出报表"}
                    </Button>
                </div>
            </div>

            {(overview || projectionSummary) && (
                <GlassCard className="p-6 border border-sky-100 bg-sky-50/70">
                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                        <div>
                            <p className="text-sm font-semibold text-sky-900 flex items-center gap-2">
                                <Info className="w-4 h-4" />
                                当前看板口径
                            </p>
                            <p className="mt-2 text-sm text-sky-800 text-pretty">
                                综合分、分布和排行榜只纳入 {evaluableSessions} 次可评估的已完成训练；
                                {notEvaluableSessions} 次证据不足会话会被单独记账，不再混入平均分或分数桶。
                            </p>
                        </div>
                        <div className="rounded-2xl border border-sky-100 bg-white/90 p-4 lg:max-w-sm">
                            <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">分数口径</p>
                            <p className="mt-2 text-base font-semibold text-slate-900 text-pretty">
                                {formatScoreBasisLabel(scoreBasis)}
                            </p>
                            <p className="mt-2 text-sm text-slate-600 text-pretty">
                                当前平均分 {overview?.average_score?.toFixed(1) ?? "0.0"} 来自统一训练证据，不再沿用旧的加权 SQL 语义。
                            </p>
                        </div>
                    </div>
                </GlassCard>
            )}

            {overview && <MetricsCards data={overview} />}

            <GlassCard className="p-6 border border-slate-200 bg-white/95">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                        <h2 className="text-xl font-black text-slate-900">本周经营节奏包</h2>
                        <p className="mt-2 text-sm text-slate-600 text-pretty">
                            本周已完成 {operatingSummary.completed_sessions} 次训练，其中 {operatingSummary.evaluable_sessions} 次可评估，{operatingSummary.not_evaluable_sessions} 次证据不足；当前有 {operatingSummary.at_risk_users} 位风险成员、{operatingSummary.improving_users} 位显著回升成员。
                        </p>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        固定观察窗 {operatingSummary.window_days || 7} 天
                    </span>
                </div>

                <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-2xl border border-rose-100 bg-rose-50/70 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">风险成员</p>
                        <p className="mt-2 text-3xl font-black text-slate-900">{operatingSummary.at_risk_users}</p>
                        <p className="mt-1 text-xs text-slate-600">未通过 + 连续未练，按最新可评估证据对齐。</p>
                    </div>
                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">显著回升</p>
                        <p className="mt-2 text-3xl font-black text-slate-900">{operatingSummary.improving_users}</p>
                        <p className="mt-1 text-xs text-slate-600">最近一周通过率明显抬升的成员。</p>
                    </div>
                    <div className="rounded-2xl border border-amber-100 bg-amber-50/70 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">证据不足 / 降级</p>
                        <p className="mt-2 text-3xl font-black text-slate-900">{operatingSummary.not_evaluable_sessions + operatingSummary.degraded_sessions}</p>
                        <p className="mt-1 text-xs text-slate-600">{topDegradedReasonLabel || topReasonLabel || "当前没有明显降级信号"}</p>
                    </div>
                    <div className="rounded-2xl border border-sky-100 bg-sky-50/70 p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">活跃部门</p>
                        <p className="mt-2 text-3xl font-black text-slate-900">{operatingSummary.active_departments}</p>
                        <p className="mt-1 text-xs text-slate-600">本周至少产生一次已完成训练的部门数。</p>
                    </div>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                    <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <h3 className="text-base font-bold text-slate-900">反复卡点 {formatBucketLabel(repeatedBlockerFamilies.length)}</h3>
                                <p className="mt-1 text-sm text-slate-500 text-pretty">
                                    优先看本周重复出现的问题家族，而不是把注意力放回旧的均分波动。
                                </p>
                            </div>
                            {topBlockerLabel ? (
                                <span className="inline-flex rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700">
                                    当前最重：{topBlockerLabel}
                                </span>
                            ) : null}
                        </div>
                        <div className="mt-4 space-y-3">
                            {repeatedBlockerFamilies.length > 0 ? repeatedBlockerFamilies.map((bucket) => {
                                const issueLabel = formatIssueTypeLabel(bucket.issue_type) || bucket.issue_type || bucket.issue_family;
                                return (
                                    <div key={`${bucket.issue_family}-${bucket.issue_text || "empty"}`} className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                                        <div className="flex flex-wrap items-center justify-between gap-3">
                                            <div>
                                                <p className="text-sm font-semibold text-slate-900">{bucket.issue_text || issueLabel}</p>
                                                <p className="mt-1 text-xs text-slate-500">{issueLabel}</p>
                                            </div>
                                            <div className="text-right text-xs text-slate-500">
                                                <p>{bucket.count} 次命中</p>
                                                <p>{bucket.user_count} 人 / {bucket.department_count ?? 0} 部门</p>
                                            </div>
                                        </div>
                                    </div>
                                );
                            }) : (
                                <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
                                    本周还没有形成稳定重复的 blocker family。
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5">
                        <h3 className="text-base font-bold text-slate-900">本周首要处理点</h3>
                        <div className="mt-4 space-y-3">
                            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                                <p className="text-xs font-medium text-slate-500">重复卡点</p>
                                <p className="mt-2 text-sm font-semibold text-slate-900 text-pretty">
                                    {topBlockerFamily?.issue_text || "当前还没有稳定重复卡点"}
                                </p>
                            </div>
                            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                                <p className="text-xs font-medium text-slate-500">证据不足主因</p>
                                <p className="mt-2 text-sm font-semibold text-slate-900 text-pretty">
                                    {operatingSummary.top_not_evaluable_reason
                                        ? formatNotEvaluableReason(operatingSummary.top_not_evaluable_reason.reason)
                                        : "当前没有证据不足主因"}
                                </p>
                            </div>
                            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                                <p className="text-xs font-medium text-slate-500">降级主因</p>
                                <p className="mt-2 text-sm font-semibold text-slate-900 text-pretty">
                                    {topDegradedReasonLabel || "当前没有降级主因"}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </GlassCard>

            <GlassCard className="p-6 border border-slate-200 bg-white/95">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">部门问题面</h3>
                        <p className="mt-1 text-sm text-slate-500 text-pretty">
                            把部门维度的 blocker、证据不足与降级原因放在一屏里，方便周会上直接分派动作。
                        </p>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        {departmentIssueBuckets.length > 0 ? `${departmentIssueBuckets.length} 个部门有已完成训练` : "本周暂无部门样本"}
                    </span>
                </div>

                {departmentIssueBuckets.length > 0 ? (
                    <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
                        {departmentIssueBuckets.map((bucket) => (
                            <article key={bucket.department} className="rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
                                <div className="flex items-start justify-between gap-4">
                                    <div>
                                        <h4 className="text-lg font-bold text-slate-900">{bucket.department}</h4>
                                        <p className="mt-1 text-sm text-slate-500 tabular-nums">
                                            本周 {bucket.session_count} 次训练 · {bucket.evaluable_sessions} 次可评估 · {bucket.not_evaluable_sessions} 次证据不足
                                        </p>
                                    </div>
                                </div>

                                <div className="mt-4 space-y-3">
                                    {bucket.issue_buckets.length > 0 ? bucket.issue_buckets.map((issueBucket) => {
                                        const issueLabel = formatIssueTypeLabel(issueBucket.issue_type) || issueBucket.issue_type || issueBucket.issue_family;
                                        return (
                                            <div key={`${bucket.department}-${issueBucket.issue_family}`} className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                                                <div className="flex items-start justify-between gap-4">
                                                    <div>
                                                        <p className="text-sm font-semibold text-slate-900 text-pretty">{issueBucket.issue_text || issueLabel}</p>
                                                        <p className="mt-1 text-xs text-slate-500">{issueLabel}</p>
                                                    </div>
                                                    <span className="text-xs font-medium text-slate-500">{issueBucket.count} 次 / {issueBucket.user_count} 人</span>
                                                </div>
                                            </div>
                                        );
                                    }) : (
                                        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-5 text-sm text-slate-500">
                                            当前部门本周还没有形成 blocker family。
                                        </div>
                                    )}
                                </div>

                                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                                    <div className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                                        <p className="text-xs font-medium text-slate-500">证据不足原因</p>
                                        <div className="mt-2 space-y-1 text-sm text-slate-700">
                                            {bucket.degradation_breakdown.not_evaluable_reasons.length > 0 ? bucket.degradation_breakdown.not_evaluable_reasons.map((reason) => (
                                                <p key={`${bucket.department}-${reason.reason}`}>{formatNotEvaluableReason(reason.reason)} · {reason.count} 次</p>
                                            )) : <p>当前无证据不足原因</p>}
                                        </div>
                                    </div>
                                    <div className="rounded-2xl border border-white/80 bg-white px-4 py-3">
                                        <p className="text-xs font-medium text-slate-500">降级原因</p>
                                        <div className="mt-2 space-y-1 text-sm text-slate-700">
                                            {bucket.degradation_breakdown.degraded_reasons.length > 0 ? bucket.degradation_breakdown.degraded_reasons.map((reason) => (
                                                <p key={`${bucket.department}-degraded-${reason.reason}`}>{formatDegradedReasonLabel(reason.reason)} · {reason.count} 次</p>
                                            )) : <p>当前无降级原因</p>}
                                        </div>
                                    </div>
                                </div>
                            </article>
                        ))}
                    </div>
                ) : (
                    <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500">
                        本周还没有可用于部门问题面的完成训练样本。
                    </div>
                )}
            </GlassCard>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <GlassCard className="p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-2xl bg-rose-50 flex items-center justify-center">
                            <ShieldAlert className="w-5 h-5 text-rose-600" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-slate-900">反复问题家族</h3>
                            <p className="text-xs text-slate-500">管理员先看卡在哪，不先看旧平均分。</p>
                        </div>
                    </div>
                    {topIssueFamily ? (
                        <>
                            {topIssueLabel ? (
                                <span className="inline-flex rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">
                                    {topIssueLabel}
                                </span>
                            ) : null}
                            <p className="mt-4 text-base font-semibold text-slate-900 text-pretty">
                                {topIssueFamily.issue_text}
                            </p>
                            <p className="mt-2 text-sm text-slate-600 tabular-nums">
                                当前时间范围内出现 {topIssueFamily.count} 次。
                            </p>
                        </>
                    ) : (
                        <p className="text-sm text-slate-500 text-pretty">
                            当前时间范围内还没有形成稳定重复的问题家族。
                        </p>
                    )}
                </GlassCard>

                <GlassCard className="p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-2xl bg-amber-50 flex items-center justify-center">
                            <Info className="w-5 h-5 text-amber-600" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-slate-900">证据不足 / 降级</h3>
                            <p className="text-xs text-slate-500">这些会话会保留记录，但不会被纳入分数线。</p>
                        </div>
                    </div>
                    {topReason ? (
                        <>
                            <p className="text-base font-semibold text-slate-900 text-pretty">
                                {topReasonLabel}
                            </p>
                            <p className="mt-2 text-sm text-slate-600 tabular-nums">
                                当前时间范围内出现 {topReason.count} 次。
                            </p>
                        </>
                    ) : (
                        <p className="text-sm text-slate-500 text-pretty">
                            当前时间范围内没有证据不足会话，所有已完成训练都纳入统一分数口径。
                        </p>
                    )}
                </GlassCard>

                <GlassCard className="p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-2xl bg-blue-50 flex items-center justify-center">
                            <Target className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-slate-900">重复下一轮重点</h3>
                            <p className="text-xs text-slate-500">主管要看的不是热闹，而是系统持续指向的训练动作。</p>
                        </div>
                    </div>
                    {repeatedGoal ? (
                        <>
                            {repeatedGoalLabel ? (
                                <span className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                                    {repeatedGoalLabel}
                                </span>
                            ) : null}
                            <p className="mt-4 text-base font-semibold text-slate-900 text-pretty">
                                {repeatedGoal.goal_text}
                            </p>
                            <p className="mt-2 text-sm text-slate-600 tabular-nums">
                                当前时间范围内重复出现 {repeatedGoal.count} 次。
                            </p>
                        </>
                    ) : (
                        <p className="text-sm text-slate-500 text-pretty">
                            当前时间范围内还没有形成稳定重复的下一轮重点。
                        </p>
                    )}
                </GlassCard>
            </div>

            <GlassCard className="p-6">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">能力通过率（仅可评估训练）</h3>
                        <p className="text-sm text-slate-500 text-pretty">
                            这些通过率沿用统一训练证据里的 pass flags，只把已完成且可评估的训练纳入分母。
                        </p>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        当前纳入 {evaluableSessions} 次可评估训练
                    </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs text-slate-500">3分钟连续表达通过率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {effectiveness.pass_rate_3min_flow.toFixed(1)}%
                        </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs text-slate-500">5轮追问稳定通过率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {effectiveness.pass_rate_5turn_defense.toFixed(1)}%
                        </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs text-slate-500">四段结构完整率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {effectiveness.pass_rate_4step_structure.toFixed(1)}%
                        </p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <p className="text-xs text-slate-500">次日复练率</p>
                        <p className="text-2xl font-black text-slate-900 mt-2">
                            {effectiveness.next_day_retry_rate.toFixed(1)}%
                        </p>
                    </div>
                </div>
            </GlassCard>

            <ManagerLitePanel data={managerLite} onRemind={handleManagerRemind} />

            <GlassCard className="p-6">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">异常关联资产变更</h3>
                        <p className="mt-1 text-sm text-slate-500 text-pretty">
                            把 support/runtime 里的 blocking / warning 直接连回当前资产治理链，先看异常是否刚好落在最近变更之后。
                        </p>
                    </div>
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                        {linkedRuntimeFaults.length > 0 ? `已命中 ${linkedRuntimeFaults.length} 条异常` : "当前无命中"}
                    </span>
                </div>

                {linkedRuntimeFaults.length > 0 ? (
                    <div className="mt-5 space-y-4">
                        {linkedRuntimeFaults.map(({ fault, assetChanges }, index) => (
                            <article
                                key={`${fault.kind}-${fault.session_id ?? index}`}
                                className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
                            >
                                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                    <span className={`inline-flex rounded-full px-2.5 py-1 font-medium ${fault.severity === "blocking" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
                                        {fault.severity === "blocking" ? "blocking" : "warning"}
                                    </span>
                                    <span>{fault.scenario_type || "-"} · {fault.session_status || "-"}</span>
                                    {fault.session_id ? (
                                        <Link href={`/practice/${fault.session_id}/report`} className="font-medium text-blue-600 hover:text-blue-700">
                                            查看对应报告
                                        </Link>
                                    ) : null}
                                </div>
                                <p className="mt-3 text-sm font-medium text-slate-900 text-pretty">{fault.summary}</p>
                                <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
                                    {assetChanges.map((change) => (
                                        <div key={`${fault.kind}-${change.asset_type}-${change.asset_id}`} className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Link href={formatLinkedAssetLink(change)} className="text-sm font-semibold text-slate-900 hover:text-blue-600">
                                                    {formatLinkedAssetLabel(change)} · {change.asset_name}
                                                </Link>
                                                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                                                    {formatLinkedAssetImpactLevelLabel(change.impact_level)}
                                                </span>
                                                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                                                    {formatLinkedAssetHealthStatusLabel(change.health_status)}
                                                </span>
                                            </div>
                                            <p className="mt-2 text-sm text-slate-700 text-pretty">{change.latest_change_label}</p>
                                            <p className="mt-1 text-xs text-slate-500 text-pretty">
                                                近 7 天 {change.change_count_7d || 0} 次变更
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </article>
                        ))}
                    </div>
                ) : (
                    <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500 text-pretty">
                        当前 blocking / warning 异常还没有指向最近资产变更。
                    </div>
                )}
            </GlassCard>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <GlassCard className="lg:col-span-2 p-6">
                    <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
                        <div>
                            <h3 className="text-lg font-bold text-slate-900">统一证据趋势</h3>
                            <p className="mt-1 text-sm text-slate-500 text-pretty">
                                每个时间桶里的平均分只纳入可评估训练；证据不足会话会单独计数，不会抹平趋势线。
                            </p>
                        </div>
                        {projectionSummary ? (
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                                {projectionSummary.evaluable_sessions} 次可评估训练 / {projectionSummary.not_evaluable_sessions} 次证据不足
                            </span>
                        ) : null}
                    </div>
                    {trends && <TrendsChart data={trends.trend_data} />}
                </GlassCard>

                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-1">可评估训练分数分布</h3>
                    <p className="text-sm text-slate-500 text-pretty mb-4">
                        证据不足的 {notEvaluableSessions} 次会话不会被混进优秀/良好/及格/待提升桶。
                    </p>
                    {trends && <ScoreDistributionChart data={trends.score_distribution} />}
                </GlassCard>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-1">Agent 使用排名（统一证据口径）</h3>
                    <p className="text-sm text-slate-500 text-pretty mb-4">
                        使用量看全部训练，平均分与完成率沿用同一条统一训练证据口径。
                    </p>
                    {agents && <AgentRankingChart data={agents} />}
                </GlassCard>

                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-1">用户排行榜（可评估训练优先）</h3>
                    <p className="text-sm text-slate-500 text-pretty mb-4">
                        排序先看可评估训练量，再看平均分和最佳分，避免证据不足会话把排名语义带偏。
                    </p>
                    {leaderboardLeader ? (
                        <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                            <p className="text-sm font-semibold text-slate-900">
                                当前榜首：{leaderboardLeader.username}
                            </p>
                            <p className="mt-1 text-sm text-slate-600 tabular-nums">
                                已纳入 {leaderboardLeader.evaluable_sessions ?? 0} 次可评估训练，平均分 {leaderboardLeader.average_score.toFixed(1)}。
                            </p>
                            {(leaderIssueLabel || leaderGoalLabel) ? (
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {leaderIssueLabel ? (
                                        <span className="inline-flex rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">
                                            最近主问题：{leaderIssueLabel}
                                        </span>
                                    ) : null}
                                    {leaderGoalLabel ? (
                                        <span className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                                            下一轮重点：{leaderGoalLabel}
                                        </span>
                                    ) : null}
                                </div>
                            ) : null}
                        </div>
                    ) : null}
                    {leaderboard && <LeaderboardTable data={leaderboard.leaderboard} />}
                </GlassCard>
            </div>

            {agents && Object.keys(agents.scenario_distribution || {}).length > 0 && (
                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-1">场景分布</h3>
                    <p className="text-sm text-slate-500 text-pretty mb-4">
                        这里展示的是训练体量，不代表统一分数口径；综合分仍以上面的可评估训练为准。
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(agents.scenario_distribution).map(([type, count]) => {
                            const total = Object.values(agents.scenario_distribution).reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((count / total) * 100).toFixed(1) : "0.0";
                            const label = type === "sales" ? "销售对练" : type === "presentation" ? "PPT演练" : type;

                            return (
                                <div
                                    key={type}
                                    className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl"
                                >
                                    <div>
                                        <p className="font-bold text-slate-900">{label}</p>
                                        <p className="text-sm text-slate-500">{count} 次训练</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-2xl font-black text-slate-900">{percentage}%</p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </GlassCard>
            )}
        </div>
    );
}
