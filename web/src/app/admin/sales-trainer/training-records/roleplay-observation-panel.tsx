"use client";

import { useEffect, useMemo, useState } from "react";
import { Bot, ShieldAlert, TimerReset } from "lucide-react";

import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerRoleplayObservationSessionResponse,
    SalesTrainerTrainingRecord,
} from "@/lib/api/types";
import { buildRoleplayObservationPanelState } from "@/lib/sales-trainer/roleplay-observation";

function formatDateTime(value: string | null): string {
    if (!value) {
        return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString();
}

function formatMetric(value: number): string {
    return new Intl.NumberFormat("zh-CN", {
        maximumFractionDigits: 0,
    }).format(value);
}

function formatRuntimeDisposition(value: string | null): string {
    return value || "record_only";
}

function formatMainChainEffect(value: string | null): string {
    return `main_chain_effect=${value || "none"}`;
}

function ObservationMetric({
    label,
    value,
    helper,
}: {
    label: string;
    value: string;
    helper?: string;
}) {
    return (
        <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className="mt-2 text-lg font-bold text-slate-950">{value}</p>
            {helper ? <p className="mt-1 text-xs text-slate-500">{helper}</p> : null}
        </div>
    );
}

export function RoleplayObservationPanel({
    record,
}: {
    record: SalesTrainerTrainingRecord;
}) {
    const sessionId = record.realtime_roleplay_session?.session_id;
    const [observationData, setObservationData] =
        useState<SalesTrainerRoleplayObservationSessionResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [reloadToken, setReloadToken] = useState(0);

    useEffect(() => {
        let cancelled = false;
        if (!sessionId) {
            return () => {
                cancelled = true;
            };
        }
        void api.admin.salesTrainer.getRealtimeRoleplayObservations(sessionId)
            .then((result) => {
                if (cancelled) {
                    return;
                }
                setObservationData(result);
            })
            .catch((loadError) => {
                if (cancelled) {
                    return;
                }
                setObservationData(null);
                setError(getApiErrorMessage(loadError));
            });
        return () => {
            cancelled = true;
        };
    }, [reloadToken, sessionId]);

    const observationState = useMemo(
        () => buildRoleplayObservationPanelState(record, observationData),
        [record, observationData],
    );
    const observation = observationState.observation;
    const isLoading = Boolean(sessionId) && observationData === null && error === null;

    if (!sessionId) {
        return (
            <EmptyState
                title="暂无角色一致性观察"
                description="当前实时对练记录缺少可回放的会话标识，无法单独读取旁路质检结果。"
                icon={<ShieldAlert className="h-10 w-10 text-slate-300" />}
            />
        );
    }

    if (isLoading) {
        return (
            <GlassCard className="space-y-4 p-6" role="status">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">角色一致性观察</h2>
                    <p className="mt-1 text-sm text-slate-500">
                        正在读取旁路质检快照，不影响训练记录主信息加载。
                    </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div
                            key={index}
                            className="h-24 animate-pulse rounded-2xl bg-slate-100/80"
                        />
                    ))}
                </div>
            </GlassCard>
        );
    }

    if (error) {
        return (
            <AdminLoadErrorCard
                title="角色一致性观察加载失败"
                description="该卡片独立读取 admin observation endpoint；失败会显式提示，但不会影响训练记录其余卡片继续展示。"
                message={error}
                retryLabel="重新加载观察"
                onRetry={() => {
                    setObservationData(null);
                    setError(null);
                    setReloadToken((value) => value + 1);
                }}
            />
        );
    }

    if (!observation) {
        return (
            <EmptyState
                title={observationState.emptyState?.title || "暂无角色一致性观察"}
                description={
                    observationState.emptyState?.description
                    || "当前会话没有可展示的旁路质检快照。"
                }
                icon={<ShieldAlert className="h-10 w-10 text-slate-300" />}
            />
        );
    }

    return (
        <GlassCard aria-label="角色一致性观察" className="space-y-5 p-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-bold text-slate-900">角色一致性观察</h2>
                        <Badge className="bg-slate-900 text-white">{observationState.sourceLabel}</Badge>
                        <Badge className="bg-slate-100 text-slate-700">
                            {observation.summaryStatusLabel}
                        </Badge>
                        {observation.manualReviewRequired ? (
                            <Badge className="bg-amber-50 text-amber-700">需人工复核</Badge>
                        ) : null}
                    </div>
                    <p className="text-sm text-slate-600">
                        {observationState.sourceDescription}
                    </p>
                </div>
                <div className="space-y-1 text-sm text-slate-500">
                    <p>最近观测：{formatDateTime(observation.lastObservedAt)}</p>
                    <p className="break-all">合同哈希：{observation.contractHash || "--"}</p>
                </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <ObservationMetric
                    label="风险观察"
                    value={formatMetric(observation.violationCount)}
                />
                <ObservationMetric
                    label="需复核信号"
                    value={formatMetric(observation.blockingViolationCount)}
                />
                <ObservationMetric
                    label="处理模式"
                    value={formatRuntimeDisposition(observation.runtimeDisposition)}
                    helper="后台复盘只读记录。"
                />
                <ObservationMetric
                    label="主链路影响"
                    value={formatMainChainEffect(observation.mainChainEffect)}
                    helper="观测结果不改变 learner 输出。"
                />
                <ObservationMetric
                    label="检测来源"
                    value={observation.detectionSourceLabels[0] || "--"}
                    helper={observation.detectionSourceLabels.slice(1).join(" / ") || undefined}
                />
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <ObservationMetric
                    label="LLM Timeout"
                    value={observation.llmTimedOut ? "是" : "否"}
                    helper="旁路观测超时只记诊断，不中断会话。"
                />
                <ObservationMetric
                    label="仅 Heuristic"
                    value={observation.heuristicOnly ? "是" : "否"}
                    helper="当前结果是否完全由规则信号得出。"
                />
                <ObservationMetric
                    label="逐轮发现"
                    value={formatMetric(observation.findings.length)}
                    helper="含违规决策与规则披露事件。"
                />
            </div>

            {observation.dimensionScores.length ? (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-slate-900">维度分数</h3>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {observation.dimensionScores.map((dimension) => (
                            <div
                                key={dimension.key}
                                className="rounded-2xl border border-slate-100 bg-white/80 p-4"
                            >
                                <p className="text-sm font-semibold text-slate-900">{dimension.label}</p>
                                <p className="mt-2 text-lg font-bold text-slate-950">
                                    {dimension.score == null
                                        ? "--"
                                        : `${dimension.score} / ${dimension.maxScore}`}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">{dimension.key}</p>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}

            <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-900">风险标签</h3>
                <div className="flex flex-wrap gap-2">
                    {observation.riskTagLabels.length > 0 ? observation.riskTagLabels.map((tag) => (
                        <Badge key={tag} className="bg-amber-50 text-amber-700">
                            {tag}
                        </Badge>
                    )) : (
                        <span className="text-sm text-slate-500">当前未记录额外风险标签。</span>
                    )}
                </div>
            </div>

            {observation.manualReviewReasons.length ? (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-slate-900">人工复核原因</h3>
                    <div className="flex flex-wrap gap-2">
                        {observation.manualReviewReasons.map((reason) => (
                            <Badge key={reason} className="bg-red-50 text-red-700">
                                {reason}
                            </Badge>
                        ))}
                    </div>
                </div>
            ) : null}

            {observationState.sourceKind === "legacy_fallback" ? (
                <div className="rounded-2xl border border-amber-100 bg-amber-50/70 px-4 py-3 text-sm text-amber-800">
                    当前页没有读取到新的 observation sidecar 行，以下内容来自训练记录冻结的
                    legacy compliance snapshot，仅用于兼容历史复盘。
                </div>
            ) : null}

            <div className="space-y-3">
                <div className="flex items-center gap-2">
                    <Bot className="h-4 w-4 text-slate-400" aria-hidden />
                    <h3 className="text-sm font-semibold text-slate-900">Turn 级观察列表</h3>
                </div>
                {observation.findings.length > 0 ? (
                    <div className="space-y-3">
                        {observation.findings.map((finding) => (
                            <div
                                key={finding.id}
                                className="rounded-2xl border border-slate-100 bg-white/85 p-4"
                            >
                                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                    <span className="font-semibold text-slate-900">
                                        {finding.turnNumber ? `Turn ${finding.turnNumber}` : "未标记轮次"}
                                    </span>
                                    <span>{finding.eventType}</span>
                                    <span>{finding.severityLabel}</span>
                                    <span>{finding.actionLabel}</span>
                                </div>
                                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                                    <ObservationMetric
                                        label="违规码"
                                        value={finding.violationLabel}
                                        helper={finding.violationCode || undefined}
                                    />
                                    <ObservationMetric
                                        label="检测来源"
                                        value={finding.detectionSourceLabel}
                                        helper={finding.salesStage || undefined}
                                    />
                                    <ObservationMetric
                                        label="时间 / Trace"
                                        value={formatDateTime(finding.createdAt)}
                                        helper={finding.traceId || undefined}
                                    />
                                </div>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {finding.visibleKeysCount != null ? (
                                        <Badge className="bg-slate-100 text-slate-700">
                                            visible keys: {finding.visibleKeysCount}
                                        </Badge>
                                    ) : null}
                                    {finding.disclosedKeysCount != null ? (
                                        <Badge className="bg-slate-100 text-slate-700">
                                            disclosed keys: {finding.disclosedKeysCount}
                                        </Badge>
                                    ) : null}
                                    {finding.matchedPattern ? (
                                        <Badge className="bg-red-50 text-red-700">
                                            命中内容：{finding.matchedPattern}
                                        </Badge>
                                    ) : null}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-5 text-sm text-slate-500">
                        当前没有逐轮旁路观察事件；这通常表示会话未触发角色边界守护或 replay
                        侧尚未回传 turn 级发现。
                    </div>
                )}
            </div>

            <div className="rounded-2xl border border-blue-100 bg-blue-50/70 px-4 py-3 text-sm text-blue-800">
                <div className="flex items-start gap-2">
                    <TimerReset className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    <p>
                        本卡片把 admin observation 旁路观测与训练记录快照并列展示。若这里报错或缺失，
                        只影响后台复盘，不应被当成 learner 主链路失败，也不会向 learner 暴露 admin-only
                        原始观测载荷。
                    </p>
                </div>
            </div>
        </GlassCard>
    );
}
