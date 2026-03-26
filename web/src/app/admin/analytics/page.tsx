"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "@/lib/api/client";
import {
    AnalyticsOverview,
    AnalyticsTrends,
    AnalyticsAgents,
    AnalyticsLeaderboard,
    ManagerLiteListsResponse,
    OpenAnalyticsDashboard,
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

const SCORE_BASIS_LABELS: Record<string, string> = {
    session_evidence_projection_evaluable_only: "统一训练证据 · 仅统计可评估的已完成训练",
};

function formatScoreBasisLabel(scoreBasis?: string | null): string {
    if (!scoreBasis) {
        return "统一训练证据口径";
    }
    return SCORE_BASIS_LABELS[scoreBasis] || scoreBasis;
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
    const [managerLite, setManagerLite] = useState<ManagerLiteListsResponse | null>(null);
    const [effectiveness, setEffectiveness] = useState<CoreEffectiveness>(DEFAULT_EFFECTIVENESS);

    const [isLoading, setIsLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        const params = {
            time_range: timeRange,
            scenario_type: scenarioType || undefined,
        };

        const [overviewResult, trendsResult, agentsResult, leaderboardResult, managerLiteResult, effectivenessResult] = await Promise.allSettled([
            api.analytics.getOverview(params),
            api.analytics.getTrends({ time_range: timeRange }),
            api.analytics.getAgents({ time_range: timeRange }),
            api.analytics.getLeaderboard({ time_range: timeRange, limit: 50 }),
            api.analytics.getManagerLiteLists({ time_range: timeRange, limit: 20, inactive_days: 7 }),
            api.analyticsOpen.getDashboard({
                scenario_type: scenarioType || undefined,
                days: resolveWindowDays(timeRange),
            }),
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

        if (managerLiteResult.status === "fulfilled") {
            setManagerLite(managerLiteResult.value);
        } else {
            console.error("Failed to load manager-lite lists:", managerLiteResult.reason);
            setManagerLite(EMPTY_MANAGER_LITE);
        }

        if (effectivenessResult.status === "fulfilled") {
            setEffectiveness(effectivenessResult.value.effectiveness || DEFAULT_EFFECTIVENESS);
        } else {
            console.error("Failed to load effectiveness metrics:", effectivenessResult.reason);
            setEffectiveness(DEFAULT_EFFECTIVENESS);
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
    const evaluableSessions = overview?.evaluable_sessions ?? projectionSummary?.evaluable_sessions ?? 0;
    const notEvaluableSessions = overview?.not_evaluable_sessions ?? projectionSummary?.not_evaluable_sessions ?? 0;
    const scoreBasis = overview?.score_basis ?? projectionSummary?.score_basis ?? null;

    const topIssueFamily = useMemo(() => {
        return overview?.top_issue_families?.[0] ?? projectionSummary?.issue_family_distribution?.[0] ?? null;
    }, [overview, projectionSummary]);

    const topReason = useMemo(() => {
        return overview?.not_evaluable_reasons?.[0] ?? projectionSummary?.not_evaluable_reasons?.[0] ?? null;
    }, [overview, projectionSummary]);

    const repeatedGoal = projectionSummary?.repeated_next_goals?.[0] ?? null;
    const leaderboardLeader = leaderboard?.leaderboard?.[0] ?? null;

    const topIssueLabel = topIssueFamily
        ? (formatIssueTypeLabel(topIssueFamily.issue_type) || topIssueFamily.issue_type)
        : null;
    const topReasonLabel = topReason
        ? formatNotEvaluableReason(topReason.reason)
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

            {managerLite && (
                <ManagerLitePanel data={managerLite} onRemind={handleManagerRemind} />
            )}

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
