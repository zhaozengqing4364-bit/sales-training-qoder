"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
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

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { LearnerHelpCard } from "@/components/dashboard/learner-help-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    HistorySessionSummary,
    HistoryStatistics,
    HistoryTrendPoint,
} from "@/lib/api/types";
import { debug } from "@/lib/debug";
import {
    extractSessionLearningCue,
    formatEvidenceCompletenessNote,
    formatNotEvaluableReason,
    readSessionEvaluationRollups,
} from "@/lib/session-evidence";

type ScenarioFilter = "all" | "sales" | "presentation";

const DEFAULT_STATS: HistoryStatistics = {
    total_sessions: 0,
    evaluable_sessions: 0,
    not_evaluable_sessions: 0,
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

function resolveSessionDisplayRollups(session: {
    canonical_evaluation_kernel?: HistorySessionSummary["canonical_evaluation_kernel"] | HistoryTrendPoint["canonical_evaluation_kernel"];
    compatibility_readers?: HistorySessionSummary["compatibility_readers"] | HistoryTrendPoint["compatibility_readers"];
    logic_score?: number | null;
    accuracy_score?: number | null;
    completeness_score?: number | null;
    overall_score?: number | null;
}) {
    return readSessionEvaluationRollups({
        canonicalEvaluationKernel: session.canonical_evaluation_kernel,
        compatibilityReaders: session.compatibility_readers,
        logicScore: session.logic_score,
        accuracyScore: session.accuracy_score,
        completenessScore: session.completeness_score,
        overallScore: session.overall_score,
    });
}

function renderEnhancedStatusBadge(reportStatus: HistorySessionSummary["report_status"]) {
    if (reportStatus === "pending") {
        return <Badge variant="secondary" className="text-xs">综合洞察待生成</Badge>;
    }
    if (reportStatus === "processing") {
        return <Badge variant="gray" className="text-xs animate-pulse">综合洞察生成中...</Badge>;
    }
    if (reportStatus === "failed") {
        return <Badge variant="red" className="text-xs">综合洞察生成失败</Badge>;
    }
    return null;
}

export default function HistoryPage() {
    const [scenarioFilter, setScenarioFilter] = useState<ScenarioFilter>("all");
    const [history, setHistory] = useState<HistorySessionSummary[]>([]);
    const [stats, setStats] = useState<HistoryStatistics>(DEFAULT_STATS);
    const [trends, setTrends] = useState<HistoryTrendPoint[]>([]);
    const [analyticsSnapshotCount, setAnalyticsSnapshotCount] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [historyLoadError, setHistoryLoadError] = useState<string | null>(null);
    const [analyticsHint, setAnalyticsHint] = useState<string | null>(null);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        setHistoryLoadError(null);
        setAnalyticsHint(null);

        const [historyResult, statsResult, trendsResult] = await Promise.allSettled([
            api.user.getMyHistory({
                page: 1,
                page_size: 50,
                scenario_type: scenarioFilter === "all" ? undefined : scenarioFilter,
            }),
            api.dashboard.getHistoryStatistics(),
            api.dashboard.getHistoryTrends(30),
        ]);

        let historyAvailable = false;

        if (historyResult.status === "fulfilled") {
            const sessions = Array.isArray(historyResult.value?.sessions)
                ? historyResult.value.sessions
                : [];
            setHistory(sessions);
            historyAvailable = true;
            debug.log("[History] Loaded unified evidence list", {
                scenarioFilter,
                sessionCount: sessions.length,
                evaluableCount: sessions.filter((item) => item.evaluable === true).length,
                notEvaluableCount: sessions.filter((item) => item.evaluable === false).length,
            });
        } else {
            setHistory([]);
            setHistoryLoadError(`统一训练证据加载失败：${getApiErrorMessage(historyResult.reason)}`);
            debug.error("[History] Unified evidence list load failed", {
                scenarioFilter,
                error: historyResult.reason,
            });
        }

        const degradedSections: string[] = [];

        if (statsResult.status === "fulfilled") {
            setStats(statsResult.value);
        } else {
            setStats(DEFAULT_STATS);
            degradedSections.push("统计看板");
        }

        if (trendsResult.status === "fulfilled") {
            const trendPoints = Array.isArray(trendsResult.value) ? trendsResult.value : [];
            setTrends(trendPoints);
            setAnalyticsSnapshotCount(trendPoints.length);
        } else {
            setTrends([]);
            degradedSections.push("趋势快照");
            setAnalyticsSnapshotCount(0);
        }

        if (historyAvailable && degradedSections.length > 0) {
            setAnalyticsHint(`${degradedSections.join("、")}暂不可用，训练列表仍基于统一训练证据展示。`);
            debug.warn("[History] Analytics snapshot unavailable; keeping unified evidence list", {
                scenarioFilter,
                degradedSections,
            });
        }

        if (historyAvailable && degradedSections.length === 0 && historyResult.status === "fulfilled") {
            setAnalyticsSnapshotCount((current) => current || historyResult.value.sessions.length);
        }

        setIsLoading(false);
    }, [scenarioFilter]);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    const trendDelta = useMemo(() => {
        if (trends.length < 2) return null;
        const latest = resolveSessionDisplayRollups(trends[trends.length - 1] || {}).overall ?? 0;
        const previous = resolveSessionDisplayRollups(trends[trends.length - 2] || {}).overall ?? 0;
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
                    <p className="text-sm text-slate-500 mt-1">
                        回顾每一次练习，并跟踪你的进步趋势（分析样本 {analyticsSnapshotCount}）
                    </p>
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
                    <Button variant="outline" onClick={() => void loadData()} disabled={isLoading}>
                        重试
                    </Button>
                </div>
            </header>

            {historyLoadError && (
                <GlassCard className="p-4 border border-amber-200 bg-amber-50/80">
                    <p className="text-sm text-amber-800">{historyLoadError}</p>
                </GlassCard>
            )}

            {analyticsHint && !historyLoadError && (
                <GlassCard className="p-4 border border-slate-200 bg-slate-50/80">
                    <p className="text-sm text-slate-700">{analyticsHint}</p>
                </GlassCard>
            )}

            <LearnerHelpCard />

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
                    {historyLoadError ? (
                        "统一训练证据加载失败，请点击右上角“重试”。"
                    ) : (
                        <>
                            暂无训练记录，去 <Link href="/training" className="text-blue-600 font-semibold">训练大厅</Link> 开始第一次练习吧。
                        </>
                    )}
                </GlassCard>
            ) : (
                <div className="space-y-4">
                    {history.map((item) => {
                        const canOpenReport = item.status === "completed";
                        const evidenceCompletenessNote = formatEvidenceCompletenessNote(item.evidence_completeness);
                        const notEvaluableReason = item.evaluable === false
                            ? formatNotEvaluableReason(item.not_evaluable_reason)
                            : null;
                        const learningCue = extractSessionLearningCue({
                            mainIssue: item.main_issue,
                            nextGoal: item.next_goal,
                            feedbackSummary: item.feedback_summary,
                        });
                        const scoreRollups = resolveSessionDisplayRollups(item);
                        const displayOverallScore = scoreRollups.overall;

                        return (
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
                                            {renderEnhancedStatusBadge(item.report_status)}
                                        </div>
                                        {notEvaluableReason && (
                                            <div className="mt-2 text-sm text-amber-700">
                                                {notEvaluableReason}
                                            </div>
                                        )}
                                        {!notEvaluableReason && evidenceCompletenessNote && (
                                            <div className="mt-2 text-xs text-slate-500">
                                                {evidenceCompletenessNote}
                                            </div>
                                        )}
                                        {learningCue && (
                                            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                                                <div className="flex flex-wrap gap-2 mb-2">
                                                    {learningCue.issueLabel ? (
                                                        <span className="inline-flex rounded-full bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700">
                                                            {learningCue.issueLabel}
                                                        </span>
                                                    ) : null}
                                                    {learningCue.goalLabel ? (
                                                        <span className="inline-flex rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
                                                            {learningCue.goalLabel}
                                                        </span>
                                                    ) : null}
                                                </div>
                                                {learningCue.issueText ? (
                                                    <p className="text-sm text-slate-800">
                                                        <span className="text-slate-500">当前卡点：</span>
                                                        <span>{learningCue.issueText}</span>
                                                    </p>
                                                ) : null}
                                                {learningCue.goalText ? (
                                                    <p className="mt-1 text-sm text-slate-800">
                                                        <span className="text-slate-500">下一轮重点：</span>
                                                        <span>{learningCue.goalText}</span>
                                                    </p>
                                                ) : null}
                                                {learningCue.summary
                                                    && learningCue.summary !== learningCue.issueText
                                                    && learningCue.summary !== learningCue.goalText ? (
                                                        <p className="mt-2 text-xs text-slate-500">
                                                            {learningCue.summary}
                                                        </p>
                                                    ) : null}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="flex items-center gap-6 flex-wrap justify-end">
                                    <div className="text-right">
                                        {item.evaluable === false ? (
                                            <>
                                                <div className="text-lg font-bold text-amber-700">不可评估</div>
                                                <span className="text-xs text-amber-600 font-medium">统一训练证据不足</span>
                                            </>
                                        ) : displayOverallScore !== null ? (
                                            <>
                                                <div
                                                    data-testid={`history-score-${item.session_id}`}
                                                    data-contract-source={scoreRollups.source}
                                                    className={`text-2xl font-bold ${scoreClass(displayOverallScore)}`}
                                                >
                                                    {Math.round(displayOverallScore)}
                                                    <span className="text-sm font-normal text-slate-400 ml-1">分</span>
                                                </div>
                                                <span className="text-xs text-slate-400 font-medium">统一训练证据评分</span>
                                            </>
                                        ) : item.status === "completed" ? (
                                            <>
                                                <div className="text-2xl font-bold text-slate-300">--</div>
                                                <span className="text-xs text-slate-400 font-medium">统一证据待同步</span>
                                            </>
                                        ) : (
                                            <>
                                                <div className="text-2xl font-bold text-slate-300">--</div>
                                                <span className="text-xs text-slate-400 font-medium">进行中</span>
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
                                        <Button className="gap-1" disabled={!canOpenReport}>
                                            报告
                                        </Button>
                                    </Link>
                                </div>
                            </GlassCard>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
