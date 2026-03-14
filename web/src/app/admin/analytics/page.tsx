"use client";

import { useEffect, useState, useCallback } from "react";
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
    Download,
    RefreshCw,
    Filter,
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

export default function AnalyticsPage() {
    // Filter states
    const [timeRange, setTimeRange] = useState<TimeRange>("30d");
    const [scenarioType, setScenarioType] = useState<string | null>(null);

    // Data states
    const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
    const [trends, setTrends] = useState<AnalyticsTrends | null>(null);
    const [agents, setAgents] = useState<AnalyticsAgents | null>(null);
    const [leaderboard, setLeaderboard] = useState<AnalyticsLeaderboard | null>(null);
    const [managerLite, setManagerLite] = useState<ManagerLiteListsResponse | null>(null);
    const [effectiveness, setEffectiveness] = useState<CoreEffectiveness>(DEFAULT_EFFECTIVENESS);

    // Loading states
    const [isLoading, setIsLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);

    // Load all analytics data
    const loadData = useCallback(async () => {
        setIsLoading(true);
        const params = {
            time_range: timeRange,
            scenario_type: scenarioType || undefined,
        };

        // Keep page usable even if one endpoint is temporarily unavailable.
        const [overviewResult, trendsResult, agentsResult, leaderboardResult, managerLiteResult, effectivenessResult] = await Promise.allSettled([
            api.analytics.getOverview(params),
            api.analytics.getTrends(params),
            api.analytics.getAgents(params),
            api.analytics.getLeaderboard({ time_range: timeRange, limit: 50 }),
            api.analytics.getManagerLiteLists({ time_range: timeRange, limit: 20, inactive_days: 7 }),
            api.analyticsOpen.getDashboard({
                scenario_type: scenarioType || undefined,
                days: timeRange === "7d"
                    ? 7
                    : timeRange === "90d"
                        ? 90
                        : timeRange === "all_time"
                            ? 365
                            : 30,
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
        loadData();
    }, [loadData]);

    // Handle export
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

    // Time range options
    const timeRangeOptions: { value: TimeRange; label: string }[] = [
        { value: "7d", label: "7天" },
        { value: "30d", label: "30天" },
        { value: "90d", label: "90天" },
        { value: "all_time", label: "全部" },
    ];

    // Scenario type options
    const scenarioOptions = [
        { value: null, label: "全部场景" },
        { value: "sales", label: "销售对练" },
        { value: "presentation", label: "PPT演练" },
    ];

    if (isLoading) {
        return (
            <div className="space-y-8 animate-in fade-in">
                {/* Loading skeleton */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <div className="h-8 w-48 bg-slate-200 rounded-lg animate-pulse" />
                        <div className="h-4 w-64 bg-slate-100 rounded mt-2 animate-pulse" />
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
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">数据分析</h1>
                    <p className="text-slate-500 mt-1">系统使用情况和用户表现统计</p>
                </div>
                <div className="flex flex-wrap gap-3">
                    {/* Time Range Filter */}
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

                    {/* Scenario Filter */}
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

                    {/* Refresh Button */}
                    <Button
                        variant="outline"
                        onClick={loadData}
                        className="rounded-full border-slate-200"
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        刷新
                    </Button>

                    {/* Export Button */}
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

            {/* Core Metrics Cards */}
            {overview && <MetricsCards data={overview} />}

            <GlassCard className="p-6">
                <h3 className="text-lg font-bold text-slate-900 mb-4">训练效果核心指标</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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

            {/* Charts Row 1: Trends + Score Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <GlassCard className="lg:col-span-2 p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4">使用趋势</h3>
                    {trends && <TrendsChart data={trends.trend_data} />}
                </GlassCard>

                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4">分数分布</h3>
                    {trends && <ScoreDistributionChart data={trends.score_distribution} />}
                </GlassCard>
            </div>

            {/* Charts Row 2: Agent Ranking + Leaderboard */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4">Agent 使用排名</h3>
                    {agents && <AgentRankingChart data={agents} />}
                </GlassCard>

                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4">用户排行榜</h3>
                    {leaderboard && <LeaderboardTable data={leaderboard.leaderboard} />}
                </GlassCard>
            </div>

            {/* Scenario Distribution */}
            {agents && Object.keys(agents.scenario_distribution).length > 0 && (
                <GlassCard className="p-6">
                    <h3 className="text-lg font-bold text-slate-900 mb-4">场景分布</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(agents.scenario_distribution).map(([type, count]) => {
                            const total = Object.values(agents.scenario_distribution).reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((count / total) * 100).toFixed(1) : 0;
                            const label = type === "sales" ? "销售对练" : type === "presentation" ? "PPT演练" : type;

                            return (
                                <div
                                    key={type}
                                    className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl"
                                >
                                    <div>
                                        <p className="font-bold text-slate-900">{label}</p>
                                        <p className="text-sm text-slate-500">{count} 次练习</p>
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
