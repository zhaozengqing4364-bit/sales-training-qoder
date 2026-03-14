"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api } from "@/lib/api/client";
import {
    ArrowRight,
    Calendar,
    ChevronLeft,
    Clock,
    Loader2,
    Mic,
    Presentation,
    TrendingUp,
} from "lucide-react";
import Link from "next/link";

type ScenarioFilter = "all" | "sales" | "presentation";

type HistoryItem = {
    session_id: string;
    scenario_name: string;
    scenario_type: "sales" | "presentation";
    persona_name: string | null;
    agent_name: string | null;
    start_time: string;
    duration_seconds: number;
    overall_score: number | null;
    report_status: "pending" | "processing" | "completed" | "failed";
    report_generated_at: string | null;
    status: string;
};

type HistoryStats = {
    total_sessions: number;
    average_score: number;
    best_score: number;
    total_practice_time_seconds: number;
    total_practice_time_minutes: number;
};

type TrendPoint = {
    overall_score?: number;
};

const DEFAULT_STATS: HistoryStats = {
    total_sessions: 0,
    average_score: 0,
    best_score: 0,
    total_practice_time_seconds: 0,
    total_practice_time_minutes: 0,
};

function formatDuration(totalSeconds: number): string {
    const safeSeconds = Number.isFinite(totalSeconds) ? Math.max(0, Math.floor(totalSeconds)) : 0;
    const minutes = Math.floor(safeSeconds / 60);
    const seconds = safeSeconds % 60;
    return `${minutes}分${seconds.toString().padStart(2, "0")}秒`;
}

function formatDateTime(value: string): string {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    return date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
    });
}

function scoreClass(score: number): string {
    if (score >= 80) return "text-emerald-600";
    if (score >= 60) return "text-amber-600";
    return "text-red-600";
}

export default function HistoryPage() {
    const [scenarioFilter, setScenarioFilter] = useState<ScenarioFilter>("all");
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [stats, setStats] = useState<HistoryStats>(DEFAULT_STATS);
    const [trends, setTrends] = useState<TrendPoint[]>([]);
    const [analyticsSnapshotCount, setAnalyticsSnapshotCount] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        setLoadError(null);

        const [historyResult, statsResult, trendsResult] = await Promise.allSettled([
            api.user.getMyHistory({
                page: 1,
                page_size: 50,
                scenario_type: scenarioFilter === "all" ? undefined : scenarioFilter,
            }),
            api.dashboard.getHistoryStatistics(),
            api.dashboard.getHistoryTrends(30),
        ]);

        const failedSections: string[] = [];

        if (historyResult.status === "fulfilled") {
            const historyData = ((historyResult.value?.sessions as HistoryItem[]) || []);
            setHistory(historyData);
            setAnalyticsSnapshotCount(historyData.length);
        } else {
            failedSections.push("训练记录");
        }

        if (statsResult.status === "fulfilled") {
            setStats(statsResult.value);
        } else {
            failedSections.push("统计数据");
        }

        if (trendsResult.status === "fulfilled") {
            setTrends(trendsResult.value as TrendPoint[]);
        } else {
            failedSections.push("趋势数据");
        }

        if (failedSections.length > 0) {
            setLoadError(`部分历史数据加载失败（${failedSections.join("、")}），请重试。`);
        }
        setIsLoading(false);
    }, [scenarioFilter]);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const trendDelta = useMemo(() => {
        if (trends.length < 2) return null;
        const latest = trends[trends.length - 1]?.overall_score ?? 0;
        const previous = trends[trends.length - 2]?.overall_score ?? 0;
        return Number((latest - previous).toFixed(1));
    }, [trends]);

    const totalHours = useMemo(
        () => Number((stats.total_practice_time_minutes / 60).toFixed(1)),
        [stats.total_practice_time_minutes],
    );

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            <div>
                <Link href="/training">
                    <Button variant="ghost" className="pl-0 text-slate-500 hover:text-slate-900 hover:bg-transparent gap-1">
                        <ChevronLeft className="w-4 h-4" />
                        返回训练大厅
                    </Button>
                </Link>
            </div>

            <header className="flex justify-between items-center gap-4 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">训练历史记录</h1>
                    <p className="text-sm text-slate-500 mt-1">回顾每一次练习，并跟踪你的进步趋势（分析样本 {analyticsSnapshotCount}）</p>
                </div>
                <div className="flex gap-2">
                    <select
                        value={scenarioFilter}
                        onChange={(event) => setScenarioFilter(event.target.value as ScenarioFilter)}
                        className="bg-white border-none rounded-lg text-sm text-slate-600 px-3 py-2 shadow-sm focus:ring-2 focus:ring-slate-200 outline-none"
                    >
                        <option value="all">全部场景</option>
                        <option value="sales">销售对练</option>
                        <option value="presentation">PPT 演讲</option>
                    </select>
                    <Button
                        variant="outline"
                        onClick={() => {
                            void loadData();
                        }}
                        disabled={isLoading}
                    >
                        重试
                    </Button>
                </div>
            </header>

            {loadError && (
                <GlassCard className="p-4 border border-amber-200 bg-amber-50/80">
                    <p className="text-sm text-amber-800">{loadError}</p>
                </GlassCard>
            )}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <GlassCard className="p-4">
                    <div className="text-xs text-slate-500">完成练习</div>
                    <div className="text-2xl font-black text-slate-900 mt-1">{stats.total_sessions}</div>
                </GlassCard>
                <GlassCard className="p-4">
                    <div className="text-xs text-slate-500">平均得分</div>
                    <div className="text-2xl font-black text-blue-600 mt-1">{Math.round(stats.average_score || 0)}</div>
                </GlassCard>
                <GlassCard className="p-4">
                    <div className="text-xs text-slate-500">历史最好</div>
                    <div className="text-2xl font-black text-emerald-600 mt-1">{Math.round(stats.best_score || 0)}</div>
                </GlassCard>
                <GlassCard className="p-4">
                    <div className="text-xs text-slate-500">总时长（小时）</div>
                    <div className="text-2xl font-black text-slate-900 mt-1 flex items-center gap-2">
                        {totalHours}
                        {trendDelta !== null && (
                            <Badge variant={trendDelta >= 0 ? "green" : "red"} className="text-[10px]">
                                <TrendingUp className="w-3 h-3 mr-1" />
                                {trendDelta >= 0 ? "+" : ""}
                                {trendDelta}
                            </Badge>
                        )}
                    </div>
                </GlassCard>
            </div>

            {isLoading ? (
                <GlassCard className="p-10 flex items-center justify-center text-slate-500 gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    正在加载训练历史...
                </GlassCard>
            ) : history.length === 0 ? (
                <GlassCard className="p-10 text-center text-slate-500">
                    {loadError ? (
                        "历史记录加载失败，请点击右上角“重试”。"
                    ) : (
                        <>
                            暂无训练记录，去 <Link href="/training" className="text-blue-600 font-semibold">训练大厅</Link> 开始第一次练习吧。
                        </>
                    )}
                </GlassCard>
            ) : (
                <div className="space-y-4">
                    {history.map((item) => (
                        <GlassCard
                            key={item.session_id}
                            className="p-6 flex items-center justify-between border border-transparent hover:border-blue-200 transition-all"
                        >
                            <div className="flex items-center gap-6">
                                <div
                                    className={`w-12 h-12 rounded-2xl flex items-center justify-center ${
                                        item.scenario_type === "sales" ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"
                                    }`}
                                >
                                    {item.scenario_type === "sales" ? <Mic className="w-6 h-6" /> : <Presentation className="w-6 h-6" />}
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900">
                                        {item.scenario_name || "练习记录"}
                                        {item.persona_name && (
                                            <span className="text-sm font-normal text-slate-500 ml-2">
                                                ({item.persona_name})
                                            </span>
                                        )}
                                    </h3>
                                    <div className="flex items-center gap-4 text-sm text-slate-500 mt-1 flex-wrap">
                                        <span className="flex items-center gap-1.5">
                                            <Calendar className="w-4 h-4" />
                                            {formatDateTime(item.start_time)}
                                        </span>
                                        <span className="flex items-center gap-1.5">
                                            <Clock className="w-4 h-4" />
                                            {formatDuration(item.duration_seconds || 0)}
                                        </span>
                                        {/* Report Status Badge */}
                                        {item.report_status === "pending" && (
                                            <Badge variant="secondary" className="text-xs">报告待生成</Badge>
                                        )}
                                        {item.report_status === "processing" && (
                                            <Badge variant="gray" className="text-xs animate-pulse">报告生成中...</Badge>
                                        )}
                                        {item.report_status === "failed" && (
                                            <Badge variant="red" className="text-xs">报告生成失败</Badge>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-6 flex-wrap justify-end">
                                <div className="text-right">
                                    {item.report_status === "completed" && item.overall_score !== null ? (
                                        <>
                                            <div className={`text-2xl font-bold ${scoreClass(item.overall_score)}`}>
                                                {Math.round(item.overall_score)}
                                                <span className="text-sm font-normal text-slate-400 ml-1">分</span>
                                            </div>
                                            <span className="text-xs text-slate-400 font-medium">综合评分</span>
                                        </>
                                    ) : (
                                        <>
                                            <div className="text-2xl font-bold text-slate-300">--</div>
                                            <span className="text-xs text-slate-400 font-medium">
                                                {item.report_status === "pending" ? "评分中" :
                                                 item.report_status === "processing" ? "评分中" :
                                                 item.report_status === "failed" ? "评分失败" : "暂无评分"}
                                            </span>
                                        </>
                                    )}
                                </div>

                                <Link href={`/practice/${item.session_id}/replay`}>
                                    <Button variant="outline" className="gap-1">
                                        回放
                                        <ArrowRight className="w-4 h-4" />
                                    </Button>
                                </Link>
                                <Link href={`/practice/${item.session_id}/report`}>
                                    <Button className="gap-1" disabled={item.report_status !== "completed"}>
                                        报告
                                    </Button>
                                </Link>
                            </div>
                        </GlassCard>
                    ))}
                </div>
            )}
        </div>
    );
}
