"use client";

import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    AlertTriangle,
    BarChart3,
    Building2,
    ChevronRight,
    LineChart,
    RefreshCw,
    ShieldAlert,
    Sparkles,
    Users,
} from "lucide-react";

import {
    AdminContextBar,
    AdminIndexShell,
    AdminPageHeader,
} from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import { buildRoleplayObservationAnalyticsViewModel } from "@/lib/sales-trainer/roleplay-observation";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";
import type {
    TrainingJourneyAnalyticsLevelSummary,
    TrainingJourneyAnalyticsModuleSummary,
    TrainingJourneyAnalyticsResponse,
    TrainingJourneyAnalyticsRiskLearner,
    TrainingJourneyAnalyticsTrendPoint,
    TrainingJourneyAnalyticsWeaknessHeatmapEntry,
    TrainingJourneyModuleKind,
    TrainingJourneyModuleType,
    TrainingJourneyStage,
} from "@/lib/api/types";

const DEFAULT_LIMIT = 500;

const STAGE_LABELS: Record<TrainingJourneyStage, string> = {
    not_started: "未开始",
    in_progress: "训练中",
    waiting_upload: "待上传",
    processing: "处理中",
    scored: "已评分",
    passed: "已通过",
    failed: "未通过",
    needs_remediation: "待补救",
    manual_review: "待人工复核",
    disabled: "已停用",
    archived: "已归档",
    error_terminal: "终态错误",
    error_transient: "暂态错误",
};

function getStageLabel(stage: string | null | undefined): string {
    if (!stage) {
        return "未识别状态";
    }
    return STAGE_LABELS[stage as TrainingJourneyStage] ?? stage;
}

function getStageToneClass(stage: string | null | undefined): string {
    if (stage === "passed" || stage === "scored") {
        return "bg-emerald-50 text-emerald-700";
    }
    if (stage === "failed" || stage === "error_terminal" || stage === "manual_review") {
        return "bg-red-50 text-red-700";
    }
    if (stage === "needs_remediation" || stage === "error_transient") {
        return "bg-amber-50 text-amber-700";
    }
    return "bg-blue-50 text-blue-700";
}

function getModuleKindLabel(
    kind: TrainingJourneyModuleKind | TrainingJourneyModuleType | string | null | undefined,
): string {
    switch (kind) {
        case "audio_submission":
        case "audio_scoring":
            return "语音作业";
        case "quiz_attempt":
        case "article_exam":
            return "文章学习 / 考卷";
        case "ai_coach":
            return "AI 教练";
        case "audio_scoring_group":
            return "多时长语音";
        case "realtime_roleplay":
            return "实时对练";
        case "realtime_placeholder":
            return "兼容占位";
        default:
            return "训练模块";
    }
}

function getModuleSummaryIdentity(summary: TrainingJourneyAnalyticsModuleSummary): string {
    return [
        summary.module_key,
        summary.kind ?? "unknown_kind",
        summary.module_type ?? "unknown_type",
        summary.title,
    ].join(":");
}

function formatPercent(value: number | null | undefined): string {
    if (typeof value !== "number") {
        return "--";
    }
    return `${new Intl.NumberFormat("zh-CN", {
        maximumFractionDigits: 1,
    }).format(value)}%`;
}

function formatScore(value: number | null | undefined): string {
    if (typeof value !== "number") {
        return "--";
    }
    return new Intl.NumberFormat("zh-CN", {
        maximumFractionDigits: 1,
    }).format(value);
}

function formatCount(value: number | null | undefined): string {
    if (typeof value !== "number") {
        return "--";
    }
    return new Intl.NumberFormat("zh-CN", {
        maximumFractionDigits: 0,
    }).format(value);
}

function formatDateTime(value: string | null | undefined): string {
    if (!value) {
        return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString();
}

function formatDate(value: string | null | undefined): string {
    if (!value) {
        return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleDateString();
}

function normalizeDepartment(value: string): string | undefined {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
}

function normalizeLearnerLevel(value: string): string | undefined {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
}

function normalizeRoleLevel(value: string): string | undefined {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
}

function normalizeTrainingStage(value: string): TrainingJourneyStage | undefined {
    const trimmed = value.trim();
    return trimmed ? trimmed as TrainingJourneyStage : undefined;
}

function normalizeModuleKey(value: string): string | undefined {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
}

function getRiskTags(learner: TrainingJourneyAnalyticsRiskLearner): string[] {
    return learner.risk_reasons;
}

function firstRiskModuleKey(learner: TrainingJourneyAnalyticsRiskLearner): string | null {
    const firstKey = learner.risk_module_keys?.[0];
    return firstKey && firstKey.trim() ? firstKey : null;
}

function buildRiskLearnerRecordsHref(learner: TrainingJourneyAnalyticsRiskLearner): string {
    const params = new URLSearchParams({ user_id: learner.learner_id });
    const moduleKey = firstRiskModuleKey(learner);
    if (moduleKey) {
        params.set("module_key", moduleKey);
    }
    return `/admin/sales-trainer/training-records?${params.toString()}`;
}

function getApiIssueDetails(error: unknown): {
    message: string;
    backendMessage: string | null;
    errorCode: string | null;
    traceId: string | null;
} {
    if (error instanceof ApiRequestError) {
        return {
            message: error.message,
            backendMessage: error.rawMessage,
            errorCode: error.errorCode,
            traceId: error.traceId ?? null,
        };
    }
    return {
        message: getApiErrorMessage(error),
        backendMessage: null,
        errorCode: null,
        traceId: null,
    };
}

function MetricCard({
    label,
    value,
    helper,
    icon,
}: {
    label: string;
    value: string;
    helper: string;
    icon: ReactNode;
}) {
    return (
        <GlassCard className="rounded-[2rem] p-5">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <p className="text-sm font-medium text-slate-500">{label}</p>
                    <p className="mt-3 text-3xl font-black text-slate-950">{value}</p>
                    <p className="mt-2 text-sm text-slate-600">{helper}</p>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                    {icon}
                </div>
            </div>
        </GlassCard>
    );
}

function LoadingState() {
    return (
        <div className="space-y-6" aria-live="polite">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, index) => (
                    <div
                        key={index}
                        className="h-36 animate-pulse rounded-[2rem] bg-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)]"
                    />
                ))}
            </div>
            <div className="grid gap-6 xl:grid-cols-2">
                <div className="h-72 animate-pulse rounded-[2rem] bg-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)]" />
                <div className="h-72 animate-pulse rounded-[2rem] bg-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)]" />
            </div>
            <div className="h-96 animate-pulse rounded-[2rem] bg-white/70 shadow-[0_8px_30px_rgb(0,0,0,0.04)]" />
        </div>
    );
}

function IssueCard({
    error,
    onRetry,
}: {
    error: unknown;
    onRetry: () => void;
}) {
    const details = getApiIssueDetails(error);

    return (
        <GlassCard className="space-y-4 rounded-[2rem] border border-red-100 bg-red-50/90 p-6">
            <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 text-red-700" aria-hidden />
                <div className="space-y-2">
                    <h2 className="text-xl font-black text-red-950">Journey Analytics 加载失败</h2>
                    <p className="text-sm leading-6 text-red-800">
                        当前页不会把接口异常伪装成空数据。请核对权限、部门范围或后端服务状态后重试。
                    </p>
                    <p className="text-sm font-medium text-red-800">{details.message}</p>
                    {details.backendMessage && details.backendMessage !== details.message ? (
                        <p className="text-sm text-red-800">后端信息：{details.backendMessage}</p>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                        {details.errorCode ? (
                            <Badge className="bg-white text-red-700">error_code: {details.errorCode}</Badge>
                        ) : null}
                        {details.traceId ? (
                            <Badge className="bg-white text-red-700">trace_id: {details.traceId}</Badge>
                        ) : null}
                    </div>
                </div>
            </div>
            <Button
                type="button"
                variant="outline"
                className="rounded-full bg-white"
                onClick={onRetry}
            >
                <RefreshCw className="mr-2 h-4 w-4" />
                重试加载
            </Button>
        </GlassCard>
    );
}

function LevelSummarySection({
    title,
    description,
    items,
}: {
    title: string;
    description: string;
    items: TrainingJourneyAnalyticsLevelSummary[];
}) {
    return (
        <GlassCard
            aria-label={title}
            className="space-y-5 rounded-[2rem] p-6"
            role="region"
        >
            <div>
                <h2 className="text-xl font-black text-slate-950">{title}</h2>
                <p className="mt-1 text-sm text-slate-500">{description}</p>
            </div>
            {items.length === 0 ? (
                <p className="text-sm text-slate-500">当前筛选下暂无分层数据。</p>
            ) : (
                <div className="space-y-3">
                    {items.map((item) => (
                        <div
                            key={`${title}-${item.key}`}
                            className="rounded-[1.5rem] border border-slate-100 bg-white/80 p-4"
                        >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-semibold text-slate-900">{item.label || item.key}</p>
                                        {item.source ? (
                                            <Badge className="bg-slate-100 text-slate-700">
                                                source: {item.source}
                                            </Badge>
                                        ) : null}
                                    </div>
                                    <p className="mt-1 text-xs text-slate-500">key: {item.key}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-lg font-black text-slate-950">{item.learner_count}</p>
                                    <p className="text-xs text-slate-500">学员数</p>
                                </div>
                            </div>
                            {(typeof item.passed_count === "number" || typeof item.pass_rate === "number") ? (
                                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                    <div className="rounded-2xl bg-slate-50 px-3 py-2">
                                        <p className="text-xs text-slate-500">已通过</p>
                                        <p className="mt-1 font-semibold text-slate-900">
                                            {typeof item.passed_count === "number" ? item.passed_count : "--"}
                                        </p>
                                    </div>
                                    <div className="rounded-2xl bg-slate-50 px-3 py-2">
                                        <p className="text-xs text-slate-500">通过率</p>
                                        <p className="mt-1 font-semibold text-slate-900">
                                            {formatPercent(item.pass_rate)}
                                        </p>
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    ))}
                </div>
            )}
        </GlassCard>
    );
}

function JourneyTrendSection({
    items,
}: {
    items: TrainingJourneyAnalyticsTrendPoint[];
}) {
    const maxOutcomeCount = items.reduce(
        (max, item) => Math.max(max, item.outcome_count),
        0,
    );

    return (
        <GlassCard
            aria-label="历史趋势"
            className="space-y-5 rounded-[2rem] p-6"
            role="region"
        >
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-xl font-black text-slate-950">历史趋势</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        按后端 Journey outcome 的发生日期聚合，跟随当前部门、阶段、模块和等级筛选。
                    </p>
                </div>
                <Badge className="bg-slate-100 text-slate-700">
                    {items.length} 个日期桶
                </Badge>
            </div>
            {items.length === 0 ? (
                <div className="rounded-[1.5rem] border border-slate-100 bg-white/85 px-4 py-5 text-sm text-slate-500">
                    当前筛选下还没有可回放的 Journey outcome 历史事件。
                </div>
            ) : (
                <div className="space-y-3">
                    {items.map((item) => {
                        const width = maxOutcomeCount > 0
                            ? Math.max(8, Math.round((item.outcome_count / maxOutcomeCount) * 100))
                            : 0;
                        return (
                            <div
                                key={item.date}
                                className="rounded-[1.5rem] border border-slate-100 bg-white/85 p-4"
                            >
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div className="flex items-center gap-2">
                                        <LineChart className="h-4 w-4 text-slate-400" />
                                        <p className="font-semibold text-slate-900">
                                            {formatDate(item.date)}
                                        </p>
                                    </div>
                                    <Badge className="bg-blue-50 text-blue-700">
                                        通过率 {formatPercent(item.pass_rate)}
                                    </Badge>
                                </div>
                                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
                                    <div
                                        className="h-full rounded-full bg-slate-900"
                                        style={{ width: `${width}%` }}
                                    />
                                </div>
                                <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                                    <MetricChip label="事件数" value={String(item.outcome_count)} />
                                    <MetricChip label="活跃学员" value={String(item.active_learner_count)} />
                                    <MetricChip label="已通过事件" value={String(item.passed_outcome_count)} />
                                    <MetricChip label="风险事件" value={String(item.risk_outcome_count)} />
                                    <MetricChip label="平均分" value={formatScore(item.average_score)} />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </GlassCard>
    );
}

function ModuleSummaryCard({
    summary,
}: {
    summary: TrainingJourneyAnalyticsModuleSummary;
}) {
    const moduleKind = summary.module_type ?? summary.kind;
    const moduleIdentity = getModuleSummaryIdentity(summary);
    const statusEntries = Object.entries(summary.status_counts).sort((left, right) => right[1] - left[1]);

    return (
        <GlassCard className="space-y-5 rounded-[2rem] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-black text-slate-950">{summary.title}</h3>
                        <Badge className="bg-slate-100 text-slate-700">
                            {getModuleKindLabel(moduleKind)}
                        </Badge>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">module_key: {summary.module_key}</p>
                </div>
                <div className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                    {formatPercent(summary.pass_rate)}
                </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <MetricChip label="参与学员" value={String(summary.learner_count)} />
                <MetricChip label="已通过" value={String(summary.passed_count)} />
                <MetricChip label="未通过" value={String(summary.failed_count)} />
                <MetricChip label="平均分" value={formatScore(summary.average_score)} />
            </div>

            <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    状态分布
                </p>
                <div className="flex flex-wrap gap-2">
                    {statusEntries.length > 0 ? statusEntries.map(([status, count]) => (
                        <Badge
                            key={`${moduleIdentity}-${status}`}
                            className={`${getStageToneClass(status)} border-0`}
                        >
                            {getStageLabel(status)} {count}
                        </Badge>
                    )) : (
                        <span className="text-sm text-slate-500">暂无状态数据</span>
                    )}
                </div>
            </div>
        </GlassCard>
    );
}

function WeaknessHeatmapSection({
    items,
}: {
    items: TrainingJourneyAnalyticsWeaknessHeatmapEntry[];
}) {
    return (
        <GlassCard
            aria-label="弱项热图"
            className="space-y-5 rounded-[2rem] p-6"
            role="region"
        >
            <div>
                <h2 className="text-xl font-black text-slate-950">弱项热图</h2>
                <p className="mt-1 text-sm text-slate-500">
                    按后端 Journey outcome 派生模块风险率，排序使用风险人数、风险率和模块键，不在前端伪造业务阈值。
                </p>
            </div>
            {items.length === 0 ? (
                <p className="text-sm text-slate-500">当前样本没有可用于热图的模块数据。</p>
            ) : (
                <div className="grid gap-4 xl:grid-cols-3">
                    {items.map((item) => {
                        const moduleKind = item.module_type ?? item.kind;
                        const statusEntries = Object.entries(item.status_counts)
                            .sort((left, right) => right[1] - left[1])
                            .slice(0, 4);
                        return (
                            <div
                                key={item.heatmap_key}
                                className="rounded-[1.5rem] border border-slate-100 bg-white/85 p-5"
                            >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                        <h3 className="text-lg font-black text-slate-950">{item.title}</h3>
                                        <p className="mt-1 text-xs text-slate-500">module_key: {item.module_key}</p>
                                    </div>
                                    <Badge className="bg-slate-100 text-slate-700">
                                        {getModuleKindLabel(moduleKind)}
                                    </Badge>
                                </div>
                                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                                    <MetricChip label="风险率" value={formatPercent(item.risk_rate)} />
                                    <MetricChip label="风险人数" value={`${item.risk_count}/${item.learner_count}`} />
                                    <MetricChip label="通过率" value={formatPercent(item.pass_rate)} />
                                </div>
                                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                    <MetricChip label="已通过" value={String(item.passed_count)} />
                                    <MetricChip label="平均分" value={formatScore(item.average_score)} />
                                </div>
                                <div className="mt-4 flex flex-wrap gap-2">
                                    {statusEntries.length > 0 ? statusEntries.map(([status, count]) => (
                                        <Badge
                                            key={`${item.module_key}-${status}`}
                                            className={`${getStageToneClass(status)} border-0`}
                                        >
                                            {getStageLabel(status)} {count}
                                        </Badge>
                                    )) : (
                                        <span className="text-sm text-slate-500">暂无状态数据</span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </GlassCard>
    );
}

function MetricChip({
    label,
    value,
}: {
    label: string;
    value: string;
}) {
    return (
        <div className="rounded-[1.5rem] bg-slate-50 px-4 py-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
        </div>
    );
}

function ObservationAggregateSection({
    analytics,
}: {
    analytics: TrainingJourneyAnalyticsResponse;
}) {
    const observation = buildRoleplayObservationAnalyticsViewModel(analytics);

    return (
        <GlassCard
            aria-label="角色一致性观测聚合"
            className="space-y-5 rounded-[2rem] p-6"
            role="region"
        >
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-xl font-black text-slate-950">角色一致性观测聚合</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        该块优先消费后端 additive observation DTO；如果字段尚未下发，页面会保持兼容占位，不把缺字段伪装成错误或零值。
                    </p>
                </div>
                {observation?.status ? (
                    <Badge className="bg-slate-100 text-slate-700">
                        status: {observation.status}
                    </Badge>
                ) : null}
            </div>

            {!observation ? (
                <div className="rounded-[1.5rem] border border-dashed border-slate-200 bg-slate-50/80 px-4 py-5 text-sm text-slate-500">
                    后端 observation 聚合 DTO 尚未返回。Journey 主图表继续按既有契约渲染，不把缺少 additive
                    字段误判成“暂无观测”。
                </div>
            ) : (
                <>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <MetricChip
                            label="已落库会话"
                            value={formatCount(observation.observedSessionCount)}
                        />
                        <MetricChip
                            label="legacy compliance fallback"
                            value={formatCount(observation.legacyFallbackSessionCount)}
                        />
                        <MetricChip
                            label="观测待落库"
                            value={formatCount(observation.notPersistedSessionCount)}
                        />
                        <MetricChip
                            label="总候选会话"
                            value={formatCount(observation.totalSessionCount)}
                        />
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <MetricChip
                            label="需人工复核"
                            value={formatCount(observation.manualReviewSessionCount)}
                        />
                        <MetricChip
                            label="LLM 默认关闭"
                            value={formatCount(observation.llmDisabledSessionCount)}
                        />
                        <MetricChip
                            label="LLM 超时"
                            value={formatCount(observation.llmTimeoutSessionCount)}
                        />
                        <MetricChip
                            label="观测信号 / 行数"
                            value={`${formatCount(observation.signalCount)} / ${formatCount(observation.observationCount)}`}
                        />
                    </div>

                    <div className="space-y-3">
                        <h3 className="text-sm font-semibold text-slate-900">来源 / 状态分布</h3>
                        <div className="flex flex-wrap gap-2">
                            {observation.sourceCounts.map((item) => (
                                <Badge key={`source-${item.key}`} className="bg-blue-50 text-blue-700">
                                    {item.label} {item.count}
                                </Badge>
                            ))}
                            {observation.statusCounts.map((item) => (
                                <Badge key={`status-${item.key}`} className="bg-slate-100 text-slate-700">
                                    {item.label} {item.count}
                                </Badge>
                            ))}
                            {observation.sourceCounts.length === 0 && observation.statusCounts.length === 0 ? (
                                <span className="text-sm text-slate-500">当前 additive DTO 还没有来源或状态分布字段。</span>
                            ) : null}
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                        {observation.generatedAt ? (
                            <Badge className="bg-emerald-50 text-emerald-700">
                                观测聚合时间 {formatDateTime(observation.generatedAt)}
                            </Badge>
                        ) : null}
                        {observation.fallbackApplied ? (
                            <Badge className="bg-amber-50 text-amber-700">
                                fallback_applied
                            </Badge>
                        ) : null}
                        {observation.fallbackReason ? (
                            <Badge className="bg-amber-50 text-amber-700">
                                fallback_reason: {observation.fallbackReason}
                            </Badge>
                        ) : null}
                    </div>
                </>
            )}
        </GlassCard>
    );
}

export default function SalesTrainerJourneyAnalyticsPage() {
    const pathname = usePathname();
    const [analytics, setAnalytics] = useState<TrainingJourneyAnalyticsResponse | null>(null);
    const [departmentInput, setDepartmentInput] = useState("");
    const [trainingStageInput, setTrainingStageInput] = useState("");
    const [moduleKeyInput, setModuleKeyInput] = useState("");
    const [learnerLevelInput, setLearnerLevelInput] = useState("");
    const [roleLevelInput, setRoleLevelInput] = useState("");
    const [appliedDepartment, setAppliedDepartment] = useState<string | null>(null);
    const [appliedTrainingStage, setAppliedTrainingStage] = useState<TrainingJourneyStage | null>(null);
    const [appliedModuleKey, setAppliedModuleKey] = useState<string | null>(null);
    const [appliedLearnerLevel, setAppliedLearnerLevel] = useState<string | null>(null);
    const [appliedRoleLevel, setAppliedRoleLevel] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<unknown | null>(null);
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);

    const loadAnalytics = useCallback(async (filters?: {
        department?: string;
        trainingStage?: TrainingJourneyStage;
        moduleKey?: string;
        learnerLevel?: string;
        roleLevel?: string;
    }) => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.admin.salesTrainer.getJourneyAnalytics({
                department: filters?.department,
                training_stage: filters?.trainingStage,
                module_key: filters?.moduleKey,
                learner_level: filters?.learnerLevel,
                role_level: filters?.roleLevel,
                limit: DEFAULT_LIMIT,
            });
            setAnalytics(data);
        } catch (loadError) {
            setAnalytics(null);
            setError(loadError);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (routeAccess.isLoading) {
            return;
        }
        if (!routeAccess.canAccess) {
            setAnalytics(null);
            setError(null);
            setIsLoading(false);
            return;
        }
        const timer = window.setTimeout(() => {
            void loadAnalytics();
        }, 0);
        return () => window.clearTimeout(timer);
    }, [loadAnalytics, routeAccess.canAccess, routeAccess.isLoading]);

    const requestedDepartment = appliedDepartment;
    const requestedTrainingStage = appliedTrainingStage;
    const requestedModuleKey = appliedModuleKey;
    const requestedLearnerLevel = appliedLearnerLevel;
    const requestedRoleLevel = appliedRoleLevel;
    const scopeDepartment = analytics?.filters.department ?? null;
    const scopeTrainingStage = analytics?.filters.training_stage ?? null;
    const scopeModuleKey = analytics?.filters.module_key ?? null;
    const scopeLearnerLevel = analytics?.filters.learner_level ?? null;
    const scopeRoleLevel = analytics?.filters.role_level ?? null;
    const isEmpty = !isLoading && !error && analytics?.summary.loaded_learner_count === 0;
    const riskLearners = analytics?.risk_learners ?? [];
    const riskCount = analytics?.summary.risk_learner_count ?? 0;
    const learnerLevelOptions = useMemo(() => {
        const options = analytics?.learner_level_summaries ?? [];
        const selected = requestedLearnerLevel ?? scopeLearnerLevel;
        if (!selected || options.some((item) => item.key === selected)) {
            return options;
        }
        return [
            {
                key: selected,
                label: selected,
                learner_count: 0,
                source: null,
            },
            ...options,
        ];
    }, [analytics?.learner_level_summaries, requestedLearnerLevel, scopeLearnerLevel]);
    const roleLevelOptions = useMemo(() => {
        const options = analytics?.role_level_summaries ?? [];
        const selected = requestedRoleLevel ?? scopeRoleLevel;
        if (!selected || options.some((item) => item.key === selected)) {
            return options;
        }
        return [
            {
                key: selected,
                label: selected,
                learner_count: 0,
                source: null,
            },
            ...options,
        ];
    }, [analytics?.role_level_summaries, requestedRoleLevel, scopeRoleLevel]);
    const moduleOptions = useMemo(() => {
        const options = analytics?.module_summaries ?? [];
        const selected = requestedModuleKey ?? scopeModuleKey;
        if (!selected || options.some((item) => item.module_key === selected)) {
            return options;
        }
        return [
            {
                module_key: selected,
                title: selected,
                learner_count: 0,
                passed_count: 0,
                failed_count: 0,
                status_counts: {},
                pass_rate: null,
            },
            ...options,
        ];
    }, [analytics?.module_summaries, requestedModuleKey, scopeModuleKey]);

    const refreshCurrent = useCallback(() => {
        void loadAnalytics({
            department: requestedDepartment ?? scopeDepartment ?? undefined,
            trainingStage: requestedTrainingStage ?? scopeTrainingStage ?? undefined,
            moduleKey: requestedModuleKey ?? scopeModuleKey ?? undefined,
            learnerLevel: requestedLearnerLevel ?? scopeLearnerLevel ?? undefined,
            roleLevel: requestedRoleLevel ?? scopeRoleLevel ?? undefined,
        });
    }, [
        loadAnalytics,
        requestedDepartment,
        requestedTrainingStage,
        requestedModuleKey,
        requestedLearnerLevel,
        requestedRoleLevel,
        scopeDepartment,
        scopeTrainingStage,
        scopeModuleKey,
        scopeLearnerLevel,
        scopeRoleLevel,
    ]);

    const funnel = useMemo(() => analytics?.funnel ?? [], [analytics]);
    const trendData = useMemo(() => analytics?.trend_data ?? [], [analytics]);

    function applyFilters(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const department = normalizeDepartment(departmentInput);
        const trainingStage = normalizeTrainingStage(trainingStageInput);
        const moduleKey = normalizeModuleKey(moduleKeyInput);
        const learnerLevel = normalizeLearnerLevel(learnerLevelInput);
        const roleLevel = normalizeRoleLevel(roleLevelInput);
        setAppliedDepartment(department ?? null);
        setAppliedTrainingStage(trainingStage ?? null);
        setAppliedModuleKey(moduleKey ?? null);
        setAppliedLearnerLevel(learnerLevel ?? null);
        setAppliedRoleLevel(roleLevel ?? null);
        if (!routeAccess.canAccess) {
            return;
        }
        void loadAnalytics({ department, trainingStage, moduleKey, learnerLevel, roleLevel });
    }

    function resetFilters() {
        setDepartmentInput("");
        setTrainingStageInput("");
        setModuleKeyInput("");
        setLearnerLevelInput("");
        setRoleLevelInput("");
        setAppliedDepartment(null);
        setAppliedTrainingStage(null);
        setAppliedModuleKey(null);
        setAppliedLearnerLevel(null);
        setAppliedRoleLevel(null);
        if (!routeAccess.canAccess) {
            return;
        }
        void loadAnalytics();
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="Journey Analytics"
                    description="聚合新人训练 Journey 的漏斗、模块通过率、分层分布与风险学员，首切片仅消费后端投影，不在前端伪造等级或默认规则。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                    primaryAction={(
                        <Button
                            type="button"
                            variant="outline"
                            className="rounded-full bg-white/80"
                            onClick={refreshCurrent}
                            disabled={isLoading || !routeAccess.canAccess}
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            刷新数据
                        </Button>
                    )}
                />
            )}
            contextBar={!routeAccess.denialMessage ? (
                <AdminContextBar>
                    <GlassCard className="rounded-[2rem] border border-white/50 bg-white/75 p-5 backdrop-blur-xl">
                        <form className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_1fr_1fr_auto_auto]" onSubmit={applyFilters}>
                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="journey-analytics-department"
                                >
                                    部门筛选
                                </label>
                                <Input
                                    id="journey-analytics-department"
                                    placeholder="例如：销售一部"
                                    value={departmentInput}
                                    onChange={(event) => setDepartmentInput(event.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="journey-analytics-training-stage"
                                >
                                    训练阶段筛选
                                </label>
                                <select
                                    id="journey-analytics-training-stage"
                                    className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                                    value={trainingStageInput}
                                    onChange={(event) => setTrainingStageInput(event.target.value)}
                                >
                                    <option value="">全部训练阶段</option>
                                    {Object.entries(STAGE_LABELS).map(([stage, label]) => (
                                        <option key={stage} value={stage}>
                                            {label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="journey-analytics-module-key"
                                >
                                    模块筛选
                                </label>
                                <select
                                    id="journey-analytics-module-key"
                                    className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                                    value={moduleKeyInput}
                                    onChange={(event) => setModuleKeyInput(event.target.value)}
                                >
                                    <option value="">全部模块</option>
                                    {moduleOptions.map((item) => (
                                        <option key={getModuleSummaryIdentity(item)} value={item.module_key}>
                                            {item.title || item.module_key}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="journey-analytics-learner-level"
                                >
                                    学员等级筛选
                                </label>
                                <select
                                    id="journey-analytics-learner-level"
                                    className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                                    value={learnerLevelInput}
                                    onChange={(event) => setLearnerLevelInput(event.target.value)}
                                >
                                    <option value="">全部学员等级</option>
                                    {learnerLevelOptions.map((item) => (
                                        <option key={item.key} value={item.key}>
                                            {item.label || item.key} ({item.key})
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label
                                    className="text-sm font-medium text-slate-700"
                                    htmlFor="journey-analytics-role-level"
                                >
                                    角色等级筛选
                                </label>
                                <select
                                    id="journey-analytics-role-level"
                                    className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                                    value={roleLevelInput}
                                    onChange={(event) => setRoleLevelInput(event.target.value)}
                                >
                                    <option value="">全部角色等级</option>
                                    {roleLevelOptions.map((item) => (
                                        <option key={item.key} value={item.key}>
                                            {item.label || item.key} ({item.key})
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex items-end">
                                <Button type="submit" className="w-full rounded-full bg-slate-900 text-white">
                                    应用筛选
                                </Button>
                            </div>
                            <div className="flex items-end">
                                <Button
                                    type="button"
                                    variant="outline"
                                    className="w-full rounded-full bg-white"
                                    onClick={resetFilters}
                                >
                                    重置筛选
                                </Button>
                            </div>
                        </form>
                        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                            <Badge className="bg-slate-100 text-slate-700">
                                scope: {scopeDepartment ?? "当前权限范围内全部部门"}
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700">
                                training_stage: {scopeTrainingStage ? getStageLabel(scopeTrainingStage) : "全部"}
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700">
                                module_key: {scopeModuleKey ?? "全部"}
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700">
                                learner_level: {scopeLearnerLevel ?? "全部"}
                            </Badge>
                            <Badge className="bg-slate-100 text-slate-700">
                                role_level: {scopeRoleLevel ?? "全部"}
                            </Badge>
                            {analytics ? (
                                <>
                                    <Badge className="bg-blue-50 text-blue-700">
                                        已加载 {analytics.summary.loaded_learner_count} / {analytics.summary.learner_count}
                                    </Badge>
                                    <Badge className="bg-amber-50 text-amber-700">
                                        limit: {analytics.filters.limit}
                                    </Badge>
                                    <Badge className="bg-emerald-50 text-emerald-700">
                                        生成于 {formatDateTime(analytics.generated_at)}
                                    </Badge>
                                </>
                            ) : null}
                        </div>
                    </GlassCard>
                </AdminContextBar>
            ) : undefined}
        >
            {routeAccess.denialMessage ? (
                <GlassCard className="space-y-3 rounded-[2rem] border border-amber-200 bg-amber-50/90 p-6 text-amber-900">
                    <h2 className="text-xl font-black text-amber-950">页面访问受限</h2>
                    <p className="text-sm leading-6">
                        当前页不会在能力接口失败或权限不足时继续加载 Journey Analytics，避免把不可访问状态伪装成空分析。
                    </p>
                    <p className="text-sm font-medium">{routeAccess.denialMessage}</p>
                    <Button
                        type="button"
                        variant="outline"
                        className="rounded-full bg-white"
                        onClick={routeAccess.reloadCapabilities}
                    >
                        重新检查权限
                    </Button>
                </GlassCard>
            ) : null}

            {!routeAccess.denialMessage && isLoading ? <LoadingState /> : null}

            {!routeAccess.denialMessage && !isLoading && error ? (
                <IssueCard error={error} onRetry={refreshCurrent} />
            ) : null}

            {isEmpty ? (
                <EmptyState
                    title="当前筛选下暂无 Journey 数据"
                    description={
                        requestedDepartment
                            ? `部门「${requestedDepartment}」当前没有可见学员 Journey。部门权限会 fail-closed，跨部门查询不会降级成伪数据。`
                            : scopeDepartment
                                ? `部门「${scopeDepartment}」当前没有可见学员 Journey。部门权限会 fail-closed，跨部门查询不会降级成伪数据。`
                            : "当前权限范围内还没有可用 Journey 投影。等学员被纳入新人训练路径后，这里会显示漏斗、模块通过率和风险队列。"
                    }
                    actionLabel="刷新数据"
                    onAction={refreshCurrent}
                    icon={<BarChart3 className="h-10 w-10 text-slate-300" />}
                />
            ) : null}

            {!isLoading && !error && analytics && !isEmpty ? (
                <div className="space-y-6">
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        <MetricCard
                            label="纳入 Journey 的学员"
                            value={String(analytics.summary.loaded_learner_count)}
                            helper={`总样本 ${analytics.summary.learner_count} 人`}
                            icon={<Users className="h-5 w-5" />}
                        />
                        <MetricCard
                            label="Journey 通过率"
                            value={formatPercent(analytics.summary.pass_rate)}
                            helper={`已通过 ${analytics.summary.passed_learner_count} 人`}
                            icon={<Sparkles className="h-5 w-5" />}
                        />
                        <MetricCard
                            label="风险学员"
                            value={String(riskCount)}
                            helper="待干预或终态错误学员"
                            icon={<ShieldAlert className="h-5 w-5" />}
                        />
                        <MetricCard
                            label="部门范围"
                            value={scopeDepartment ?? "全部"}
                            helper="受后端权限与团队范围约束"
                            icon={<Building2 className="h-5 w-5" />}
                        />
                    </div>

                    <ObservationAggregateSection analytics={analytics} />

                    <GlassCard
                        aria-label="Journey 漏斗"
                        className="space-y-5 rounded-[2rem] p-6"
                        role="region"
                    >
                        <div>
                            <h2 className="text-xl font-black text-slate-950">Journey 漏斗</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                使用后端 `training_stage` 投影，不在前端拼接状态机。
                            </p>
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                            {funnel.map((item) => (
                                <div
                                    key={item.stage}
                                    className="rounded-[1.5rem] border border-slate-100 bg-white/85 p-4"
                                >
                                    <div className="flex items-center justify-between gap-3">
                                        <Badge className={`${getStageToneClass(item.stage)} border-0`}>
                                            {getStageLabel(item.stage)}
                                        </Badge>
                                        <span className="text-xs text-slate-500">
                                            {formatPercent(item.rate)}
                                        </span>
                                    </div>
                                    <p className="mt-4 text-3xl font-black text-slate-950">
                                        {item.learner_count}
                                    </p>
                                    <p className="mt-1 text-sm text-slate-500">学员数</p>
                                </div>
                            ))}
                        </div>
                    </GlassCard>

                    <JourneyTrendSection items={trendData} />

                    <GlassCard
                        aria-label="模块通过率与状态分布"
                        className="space-y-5 rounded-[2rem] p-6"
                        role="region"
                    >
                        <div>
                            <h2 className="text-xl font-black text-slate-950">模块通过率与状态分布</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                移动端以卡片展示，避免依赖宽表。模块状态完全跟随后端 `module_summaries`。
                            </p>
                        </div>
                        {analytics.module_summaries.length === 0 ? (
                            <p className="text-sm text-slate-500">当前样本没有模块聚合数据。</p>
                        ) : (
                            <div className="grid gap-4 xl:grid-cols-2">
                                {analytics.module_summaries.map((summary) => (
                                    <ModuleSummaryCard
                                        key={getModuleSummaryIdentity(summary)}
                                        summary={summary}
                                    />
                                ))}
                            </div>
                        )}
                    </GlassCard>

                    <WeaknessHeatmapSection items={analytics.weakness_heatmap} />

                    <div className="grid gap-6 xl:grid-cols-2">
                        <LevelSummarySection
                            title="学员等级分布"
                            description="显示后端返回的 learner level 聚合；如果后端补充 source，会直接在此透出。"
                            items={analytics.learner_level_summaries}
                        />
                        <LevelSummarySection
                            title="角色等级分布"
                            description="显示后端 role level 投影；等级来源、fallback 和发布配置由后端治理。"
                            items={analytics.role_level_summaries}
                        />
                    </div>

                    <GlassCard
                        aria-label="风险学员队列"
                        className="space-y-5 rounded-[2rem] p-6"
                        role="region"
                    >
                        <div>
                            <h2 className="text-xl font-black text-slate-950">风险学员队列</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                后端首切片当前返回风险模块数量/模块键；如后续契约升级为风险原因数组，页面会直接消费。
                            </p>
                        </div>
                        {riskLearners.length === 0 ? (
                            <div className="rounded-[1.5rem] border border-emerald-100 bg-emerald-50 px-4 py-5 text-sm text-emerald-700">
                                当前筛选下暂无风险学员。
                            </div>
                        ) : (
                            <div className="grid gap-4 xl:grid-cols-2">
                                {riskLearners.map((learner) => {
                                    const tags = getRiskTags(learner);
                                    const riskModuleKey = firstRiskModuleKey(learner);
                                    return (
                                        <div
                                            key={learner.learner_id}
                                            className="rounded-[1.5rem] border border-slate-100 bg-white/85 p-5"
                                        >
                                            <div className="flex flex-wrap items-start justify-between gap-3">
                                                <div>
                                                    <p className="text-lg font-black text-slate-950">
                                                        {learner.learner_name || learner.learner_id}
                                                    </p>
                                                    <p className="mt-1 text-sm text-slate-500">
                                                        {learner.department || "未标记部门"} · {learner.learner_id}
                                                    </p>
                                                </div>
                                                <Badge className={`${getStageToneClass(learner.training_stage)} border-0`}>
                                                    {getStageLabel(learner.training_stage)}
                                                </Badge>
                                            </div>
                                            <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                                <MetricChip
                                                    label="风险模块数"
                                                    value={String(learner.risk_module_count ?? tags.length)}
                                                />
                                                <MetricChip
                                                    label="风险标签数"
                                                    value={String(tags.length)}
                                                />
                                            </div>
                                            <div className="mt-4 flex flex-wrap gap-2">
                                                {tags.length > 0 ? tags.map((tag) => (
                                                    <Badge
                                                        key={`${learner.learner_id}-${tag}`}
                                                        className="bg-amber-50 text-amber-700"
                                                    >
                                                        {tag}
                                                    </Badge>
                                                )) : (
                                                    <span className="text-sm text-slate-500">暂无风险标签</span>
                                                )}
                                            </div>
                                            <div className="mt-4">
                                                <Link
                                                    className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 transition hover:border-slate-300 hover:bg-slate-50"
                                                    href={buildRiskLearnerRecordsHref(learner)}
                                                >
                                                    查看训练记录
                                                    {riskModuleKey ? (
                                                        <span className="ml-2 text-xs font-medium text-slate-500">
                                                            module_key: {riskModuleKey}
                                                        </span>
                                                    ) : null}
                                                    <ChevronRight className="ml-2 h-4 w-4" aria-hidden />
                                                </Link>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </GlassCard>
                </div>
            ) : null}
        </AdminIndexShell>
    );
}
