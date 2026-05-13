"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, BarChart3, CheckCircle2, RefreshCw, Target, TrendingUp } from "lucide-react";
import { CurriculumHeatmap } from "@/components/analytics/curriculum-heatmap";
import { CurriculumScoreTrend } from "@/components/analytics/curriculum-score-trend";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { CurriculumAnalyticsResponse } from "@/lib/api/types";

type CurriculumAnalyticsTimeRange = "7d" | "30d" | "90d" | "all_time";

const TIME_RANGE_OPTIONS: Array<{ label: string; value: CurriculumAnalyticsTimeRange; badge: string }> = [
    { label: "近 7 天", value: "7d", badge: "最近 7 天" },
    { label: "近 30 天", value: "30d", badge: "最近 30 天" },
    { label: "近 90 天", value: "90d", badge: "最近 90 天" },
    { label: "全部", value: "all_time", badge: "全部时间" },
];

function formatPercent(value: number): string {
    return `${Math.round(value * 100)}%`;
}

function formatDelta(value: number): string {
    return value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1);
}

function SummaryCard({ label, value, helper }: { label: string; value: string; helper: string }) {
    return (
        <GlassCard className="p-6">
            <p className="text-sm font-medium text-slate-500">{label}</p>
            <p className="mt-3 text-3xl font-black text-slate-950">{value}</p>
            <p className="mt-2 text-sm text-slate-600">{helper}</p>
        </GlassCard>
    );
}

function LoadingState() {
    return (
        <div className="space-y-6" aria-live="polite">
            <p className="text-sm font-semibold text-slate-600">正在加载课程分析数据...</p>
            <div className="grid gap-4 md:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="h-36 animate-pulse rounded-[2rem] bg-white/70" />
                ))}
            </div>
        </div>
    );
}

export default function CurriculumAnalyticsPage() {
    const [dashboard, setDashboard] = useState<CurriculumAnalyticsResponse | null>(null);
    const [timeRange, setTimeRange] = useState<CurriculumAnalyticsTimeRange>("30d");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadDashboard = async (selectedRange: CurriculumAnalyticsTimeRange) => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.analytics.getCurriculumAnalytics({ time_range: selectedRange });
            setDashboard(data);
        } catch (loadError) {
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadDashboard(timeRange);
    }, [timeRange]);

    const selectedTimeRange = TIME_RANGE_OPTIONS.find((option) => option.value === timeRange) ?? TIME_RANGE_OPTIONS[1];

    if (isLoading) {
        return <LoadingState />;
    }

    if (error) {
        return (
            <GlassCard className="p-8">
                <div className="flex items-start gap-4">
                    <AlertTriangle className="mt-1 h-6 w-6 text-red-500" />
                    <div>
                        <h1 className="text-2xl font-black text-slate-950">课程分析仪表盘加载失败</h1>
                        <p className="mt-2 text-sm text-slate-600">{error}</p>
                        <Button onClick={() => void loadDashboard(timeRange)} className="mt-5 rounded-full">
                            <RefreshCw className="mr-2 h-4 w-4" />
                            重试加载
                        </Button>
                    </div>
                </div>
            </GlassCard>
        );
    }

    if (!dashboard || (dashboard.summary.completed_count === 0 && dashboard.heatmap.length === 0)) {
        return (
            <EmptyState
                title="暂无课程分析数据"
                description="完成课程训练并生成冻结报告后，这里会展示完成率、弱项维度、分数趋势和主管复核结果。"
                icon={<BarChart3 className="h-10 w-10 text-slate-300" />}
            />
        );
    }

    return (
        <div className="space-y-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <Badge variant="blue">{selectedTimeRange.badge}</Badge>
                    <h1 className="mt-4 text-3xl font-black tracking-tight text-slate-950">课程分析仪表盘</h1>
                    <p className="mt-2 max-w-3xl text-sm text-slate-600">
                        基于冻结训练报告、课程运行快照和主管复核结果，帮助运营团队识别课程完成情况、弱项维度与复训闭环。
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex items-center rounded-full border border-slate-200 bg-white/70 p-1 text-xs text-slate-600">
                        {TIME_RANGE_OPTIONS.map((option) => (
                            <button
                                key={option.value}
                                type="button"
                                onClick={() => { setTimeRange(option.value); }}
                                className={`rounded-full px-3 py-1.5 font-semibold transition ${
                                    timeRange === option.value
                                        ? "bg-blue-600 text-white shadow-sm"
                                        : "text-slate-600 hover:bg-slate-100"
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white/70 px-4 py-2 text-xs text-slate-600">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        缓存：{dashboard.cache.enabled ? (dashboard.cache.hit ? "命中" : "未命中") : "未启用"}
                    </div>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <SummaryCard label="已完成课程" value={String(dashboard.summary.completed_count)} helper={`已分配 ${dashboard.summary.assigned_count} 个课程任务`} />
                <SummaryCard label="课程完成率" value={formatPercent(dashboard.summary.completion_rate)} helper="按训练任务分配口径统计" />
                <SummaryCard label="最高风险维度" value={dashboard.summary.top_weak_dimension || "暂无"} helper="按冻结报告维度均分排序" />
                <SummaryCard label="平均分变化" value={formatDelta(dashboard.summary.average_score_delta)} helper="周期内首末课程会话均分差" />
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
                <GlassCard className="p-6">
                    <div className="mb-5 flex items-center justify-between gap-3">
                        <div>
                            <h2 className="text-xl font-black text-slate-950">课程维度热图</h2>
                            <p className="mt-1 text-sm text-slate-500">弱项优先排序，并提供数字标签避免只依赖颜色。</p>
                        </div>
                        <Target className="h-6 w-6 text-blue-600" />
                    </div>
                    <CurriculumHeatmap data={dashboard.heatmap} />
                </GlassCard>

                <GlassCard className="p-6">
                    <div className="mb-5 flex items-center justify-between gap-3">
                        <div>
                            <h2 className="text-xl font-black text-slate-950">课程分数趋势</h2>
                            <p className="mt-1 text-sm text-slate-500">按冻结会话日期聚合平均分。</p>
                        </div>
                        <TrendingUp className="h-6 w-6 text-emerald-600" />
                    </div>
                    <CurriculumScoreTrend data={dashboard.score_trend} />
                </GlassCard>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                <GlassCard className="p-6">
                    <h2 className="text-xl font-black text-slate-950">主管复核结果</h2>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                        <OutcomePill label="已通过" value={dashboard.review_outcomes.approved} tone="green" />
                        <OutcomePill label="已驳回" value={dashboard.review_outcomes.rejected} tone="red" />
                        <OutcomePill label="已校准" value={dashboard.review_outcomes.calibrated} tone="blue" />
                        <OutcomePill label="需复训" value={dashboard.review_outcomes.retraining_required} tone="orange" />
                    </div>
                </GlassCard>

                <GlassCard className="p-6">
                    <h2 className="text-xl font-black text-slate-950">复训闭环</h2>
                    <div className="mt-5 grid gap-3 sm:grid-cols-3">
                        <OutcomePill label="已创建" value={dashboard.retraining_conversion.created} tone="blue" />
                        <OutcomePill label="已开始" value={dashboard.retraining_conversion.started} tone="orange" />
                        <OutcomePill label="已完成" value={dashboard.retraining_conversion.completed} tone="green" />
                    </div>
                </GlassCard>
            </div>
        </div>
    );
}

function OutcomePill({ label, value, tone }: { label: string; value: number; tone: "green" | "red" | "blue" | "orange" }) {
    const toneClass = {
        green: "bg-emerald-50 text-emerald-700 border-emerald-100",
        red: "bg-red-50 text-red-700 border-red-100",
        blue: "bg-blue-50 text-blue-700 border-blue-100",
        orange: "bg-orange-50 text-orange-700 border-orange-100",
    }[tone];
    return (
        <div className={`rounded-2xl border px-4 py-3 ${toneClass}`}>
            <p className="text-sm font-semibold">{label} {value}</p>
        </div>
    );
}
