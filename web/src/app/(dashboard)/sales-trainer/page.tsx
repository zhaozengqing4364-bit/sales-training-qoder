"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import type {
    TrainingJourneyDiagnostic,
    TrainingJourneyModuleProgress,
    TrainingJourneyModuleOutcome,
    TrainingJourneyModuleType,
    TrainingJourneyResponse,
    TrainingJourneyStage,
} from "@/lib/api/types";

const JOURNEY_STAGE_LABELS: Record<TrainingJourneyStage, string> = {
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

const JOURNEY_MODULE_TYPE_LABELS: Record<TrainingJourneyModuleType, string> = {
    audio_scoring: "语音作业",
    article_exam: "文章学习 / 考卷",
    audio_scoring_group: "多时长语音作业",
    ai_coach: "AI 教练",
    realtime_placeholder: "兼容占位模块",
    realtime_roleplay: "实时对练",
};

const JOURNEY_OUTCOME_RECORD_LABELS: Record<TrainingJourneyModuleOutcome["record_type"], string> = {
    audio_submission: "语音作业",
    quiz_attempt: "考卷结果",
    business_etiquette_quiz_attempt: "商务礼仪小测",
    ai_coach_session: "AI 教练",
    realtime_roleplay_session: "实时对练",
    remediation: "补救训练",
    regrade: "重评结果",
};

function getJourneyStageLabel(stage: TrainingJourneyStage): string {
    return JOURNEY_STAGE_LABELS[stage] ?? stage;
}

function getJourneyStageBadgeClass(stage: TrainingJourneyStage): string {
    if (stage === "passed" || stage === "scored") {
        return "bg-emerald-100 text-emerald-700";
    }
    if (stage === "failed" || stage === "error_terminal" || stage === "manual_review") {
        return "bg-red-100 text-red-700";
    }
    if (stage === "needs_remediation" || stage === "error_transient") {
        return "bg-amber-100 text-amber-700";
    }
    return "bg-blue-100 text-blue-700";
}

function getDiagnosticBadgeClass(severity: TrainingJourneyDiagnostic["severity"]): string {
    switch (severity) {
        case "error":
            return "bg-red-100 text-red-700";
        case "warning":
            return "bg-amber-100 text-amber-700";
        default:
            return "bg-blue-100 text-blue-700";
    }
}

function getModuleTypeLabel(moduleType: TrainingJourneyModuleType): string {
    return JOURNEY_MODULE_TYPE_LABELS[moduleType] ?? moduleType;
}

function getOutcomeRecordLabel(recordType: TrainingJourneyModuleOutcome["record_type"]): string {
    return JOURNEY_OUTCOME_RECORD_LABELS[recordType] ?? recordType;
}

function getOutcomeVerdict(outcome: TrainingJourneyModuleOutcome | null | undefined): string | null {
    if (!outcome) {
        return null;
    }
    if (outcome.passed === true) {
        return "已通过";
    }
    if (outcome.passed === false) {
        return "未通过";
    }
    return "待判定";
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

interface EndpointIssueCardProps {
    title: string;
    description: string;
    error: unknown;
    tone: "error" | "warning";
    onRetry: () => void;
}

function EndpointIssueCard({
    title,
    description,
    error,
    tone,
    onRetry,
}: EndpointIssueCardProps) {
    const details = getApiIssueDetails(error);
    const containerClass = tone === "error"
        ? "border border-red-100 bg-red-50"
        : "border border-amber-100 bg-amber-50";
    const titleClass = tone === "error" ? "text-red-950" : "text-amber-950";
    const textClass = tone === "error" ? "text-red-800" : "text-amber-800";
    const iconClass = tone === "error" ? "text-red-700" : "text-amber-700";

    return (
        <GlassCard className={`space-y-4 p-5 ${containerClass}`}>
            <div className="flex items-start gap-3">
                <AlertTriangle className={`mt-0.5 h-5 w-5 ${iconClass}`} aria-hidden />
                <div className="space-y-2">
                    <h2 className={`text-lg font-black ${titleClass}`}>{title}</h2>
                    <p className={`text-sm leading-6 ${textClass}`}>{description}</p>
                    <p className={`text-sm font-medium ${textClass}`}>{details.message}</p>
                    {details.backendMessage && details.backendMessage !== details.message ? (
                        <p className={`text-sm ${textClass}`}>后端信息：{details.backendMessage}</p>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                        {details.errorCode ? (
                            <Badge className={tone === "error" ? "bg-white text-red-700" : "bg-white text-amber-700"}>
                                error_code: {details.errorCode}
                            </Badge>
                        ) : null}
                        {details.traceId ? (
                            <Badge className={tone === "error" ? "bg-white text-red-700" : "bg-white text-amber-700"}>
                                trace_id: {details.traceId}
                            </Badge>
                        ) : null}
                    </div>
                </div>
            </div>
            <Button variant="outline" className="rounded-full" onClick={onRetry}>
                重试
            </Button>
        </GlassCard>
    );
}

export default function SalesTrainerPage() {
    const router = useRouter();
    const [journey, setJourney] = useState<TrainingJourneyResponse | null>(null);
    const [journeyError, setJourneyError] = useState<unknown | null>(null);
    const [realtimeStartError, setRealtimeStartError] = useState<unknown | null>(null);
    const [startingRealtimeModuleKey, setStartingRealtimeModuleKey] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const loadPage = useCallback(async () => {
        setIsLoading(true);
        setJourneyError(null);
        setRealtimeStartError(null);

        try {
            setJourney(await api.salesTrainer.getJourney());
        } catch (error) {
            setJourney(null);
            setJourneyError(error);
        }

        setIsLoading(false);
    }, []);

    const startRealtimeRoleplay = useCallback(async (module: TrainingJourneyModuleProgress) => {
        if (module.next_action?.action_key !== "start_realtime_roleplay" || module.next_action.disabled) {
            return;
        }
        setRealtimeStartError(null);
        setStartingRealtimeModuleKey(module.module_key);
        try {
            const result = await api.salesTrainer.startRealtimeRoleplay({
                module_key: "realtime_roleplay",
            });
            router.push(result.practice_url);
        } catch (error) {
            setRealtimeStartError(error);
        } finally {
            setStartingRealtimeModuleKey(null);
        }
    }, [router]);

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadPage();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadPage]);

    const sortedJourneyModules = useMemo(
        () => [...(journey?.modules ?? [])].sort((left, right) => left.order_index - right.order_index),
        [journey],
    );

    return (
        <div className="space-y-6 pb-20">
            <div className="space-y-4">
                <Link
                    href="/training"
                    className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
                >
                    <ArrowLeft className="h-4 w-4" />
                    返回训练大厅
                </Link>
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">新人训练路径</h1>
                        <p className="mt-1 text-sm text-slate-500">
                            首页以 TrainingJourney 的闭环状态为唯一真源，所有模块入口、等级和诊断均来自 active revision。
                        </p>
                    </div>
                    <Button variant="outline" className="rounded-full" onClick={() => void loadPage()} disabled={isLoading}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                </div>
            </div>

            {isLoading ? (
                <div className="grid gap-4 md:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div key={index} className="h-44 animate-pulse rounded-3xl border border-white/60 bg-white/60" />
                    ))}
                </div>
            ) : journeyError ? (
                <div className="space-y-4">
                    <EndpointIssueCard
                        title="Journey 读取失败"
                        description="首页闭环状态以 active revision 的 Journey 为唯一真源。当前不会用 /paths 或 catalog 伪装成功，请根据错误码和 trace_id 处理 active revision、权限或服务端问题。"
                        error={journeyError}
                        tone="error"
                        onRetry={() => void loadPage()}
                    />
                </div>
            ) : journey ? (
                <div className="space-y-6">
                    <GlassCard className="space-y-5 p-6">
                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                            <div className="space-y-3">
                                <Badge className="bg-slate-100 text-slate-700">TrainingJourney 真源</Badge>
                                <div>
                                    <h2 className="text-2xl font-black text-slate-900">当前训练闭环状态</h2>
                                    <p className="mt-1 text-sm text-slate-500">
                                        阶段、等级和模块进度都直接来自 active revision，不再由 catalog 本地推断。
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2 text-sm text-slate-600">
                                    <span>学员等级：{journey.learner_level.label}</span>
                                    <span>角色等级：{journey.role_level.label}</span>
                                    <span>来源：{journey.learner_level.source}</span>
                                    <span>revision：#{journey.path_revision_no}</span>
                                </div>
                            </div>
                            <div className="space-y-2 rounded-2xl bg-slate-50 px-4 py-3 text-right">
                                <p className="text-xs font-medium text-slate-500">当前阶段</p>
                                <Badge className={getJourneyStageBadgeClass(journey.training_stage)}>
                                    {getJourneyStageLabel(journey.training_stage)}
                                </Badge>
                                <p className="text-xs text-slate-500">journey_id: {journey.journey_id}</p>
                            </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">模块总数</p>
                                <p className="mt-2 text-2xl font-black text-slate-900">{journey.overall_progress.total_modules}</p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">已完成</p>
                                <p className="mt-2 text-2xl font-black text-slate-900">{journey.overall_progress.completed_modules}</p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">通过模块</p>
                                <p className="mt-2 text-2xl font-black text-emerald-700">{journey.overall_progress.passed_modules}</p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">未通过模块</p>
                                <p className="mt-2 text-2xl font-black text-red-700">{journey.overall_progress.failed_modules}</p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">待补救模块</p>
                                <p className="mt-2 text-2xl font-black text-amber-700">{journey.overall_progress.needs_remediation_modules}</p>
                            </div>
                        </div>

                        {journey.diagnostics.length > 0 ? (
                            <div className="space-y-3">
                                <h3 className="text-sm font-semibold text-slate-900">Journey 诊断</h3>
                                <div className="space-y-2">
                                    {journey.diagnostics.map((diagnostic) => (
                                        <div key={`${diagnostic.code}-${diagnostic.message}`} className="rounded-2xl bg-slate-50 p-3">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Badge className={getDiagnosticBadgeClass(diagnostic.severity)}>
                                                    {diagnostic.severity}
                                                </Badge>
                                                <span className="text-sm font-medium text-slate-900">{diagnostic.code}</span>
                                                {diagnostic.terminal ? (
                                                    <Badge className="bg-red-100 text-red-700">terminal</Badge>
                                                ) : null}
                                            </div>
                                            <p className="mt-2 text-sm text-slate-600">{diagnostic.message}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : null}
                    </GlassCard>

                    <section className="space-y-4">
                        <div>
                            <h2 className="text-xl font-black text-slate-900">模块闭环状态</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                模块阶段、最近结果和未满足原因以 Journey 为准，不再读取旧 catalog 作为入口兜底。
                            </p>
                        </div>
                        {realtimeStartError ? (
                            <EndpointIssueCard
                                title="实时对练启动失败"
                                description="实时对练入口由 active revision 和后端权限共同控制。请根据错误码、trace_id 和模块诊断处理配置、provider readiness 或权限问题。"
                                error={realtimeStartError}
                                tone="error"
                                onRetry={() => setRealtimeStartError(null)}
                            />
                        ) : null}
                        {sortedJourneyModules.length === 0 ? (
                            <GlassCard className="border border-amber-100 bg-amber-50 p-5">
                                <p className="text-sm text-amber-800">
                                    当前 Journey 没有返回模块。请先检查 active revision 是否已正确发布模块配置。
                                </p>
                            </GlassCard>
                        ) : (
                            <div className="grid gap-4 xl:grid-cols-2">
                                {sortedJourneyModules.map((module) => {
                                    const latestVerdict = getOutcomeVerdict(module.latest_outcome);
                                    return (
                                        <GlassCard
                                            key={`${module.kind}-${module.module_key}`}
                                            className="space-y-4 p-5"
                                        >
                                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                                <div className="space-y-2">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <Badge className="bg-slate-100 text-slate-700">
                                                            模块 {module.order_index}
                                                        </Badge>
                                                        <Badge className={getJourneyStageBadgeClass(module.stage)}>
                                                            {getJourneyStageLabel(module.stage)}
                                                        </Badge>
                                                        {!module.enabled ? (
                                                            <Badge className="bg-slate-200 text-slate-700">已停用</Badge>
                                                        ) : null}
                                                    </div>
                                                    <h3 className="text-lg font-black text-slate-900">{module.display_name}</h3>
                                                    <p className="text-sm text-slate-500">
                                                        类型：{getModuleTypeLabel(module.module_type)}
                                                    </p>
                                                </div>
                                                {latestVerdict ? (
                                                    <div className="rounded-2xl bg-slate-50 px-4 py-3 text-right">
                                                        <p className="text-xs text-slate-500">最近结果</p>
                                                        <p className="mt-1 text-sm font-semibold text-slate-900">{latestVerdict}</p>
                                                    </div>
                                                ) : null}
                                            </div>

                                            <div className="space-y-2 text-sm text-slate-600">
                                                {module.latest_outcome ? (
                                                    <p>
                                                        最近记录：{getOutcomeRecordLabel(module.latest_outcome.record_type)}
                                                        {module.latest_outcome.failure_type ? ` · ${module.latest_outcome.failure_type}` : ""}
                                                    </p>
                                                ) : (
                                                    <p>最近记录：暂无训练结果</p>
                                                )}
                                                {module.learner_level_required?.length ? (
                                                    <p>适用等级：{module.learner_level_required.join("、")}</p>
                                                ) : null}
                                                {module.latest_outcome?.failure_code ? (
                                                    <p>failure_code：{module.latest_outcome.failure_code}</p>
                                                ) : null}
                                            </div>

                                            {module.unmet_reasons.length > 0 ? (
                                                <div className="space-y-2 rounded-2xl bg-amber-50 p-3">
                                                    <p className="text-sm font-semibold text-amber-900">模块诊断</p>
                                                    <ul className="space-y-2 text-sm text-amber-800">
                                                        {module.unmet_reasons.map((reason) => (
                                                            <li key={`${module.module_key}-${reason.code}`}>
                                                                {reason.message}
                                                                {reason.terminal ? "（terminal）" : ""}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            ) : null}

                                            {module.next_action ? (
                                                <div className="space-y-2">
                                                    {module.next_action.action_key === "start_realtime_roleplay" && !module.next_action.disabled ? (
                                                        <Button
                                                            variant="outline"
                                                            className="rounded-full"
                                                            disabled={startingRealtimeModuleKey === module.module_key}
                                                            onClick={() => void startRealtimeRoleplay(module)}
                                                        >
                                                            {startingRealtimeModuleKey === module.module_key ? "启动中" : module.next_action.label}
                                                        </Button>
                                                    ) : module.next_action.target_path && !module.next_action.disabled ? (
                                                        <Button asChild variant="outline" className="rounded-full">
                                                            <Link href={module.next_action.target_path}>
                                                                {module.next_action.label}
                                                            </Link>
                                                        </Button>
                                                    ) : (
                                                        <Button variant="outline" className="rounded-full" disabled>
                                                            {module.next_action.label}
                                                        </Button>
                                                    )}
                                                    {module.next_action.disabled_reason ? (
                                                        <p className="text-xs text-slate-500">{module.next_action.disabled_reason}</p>
                                                    ) : null}
                                                </div>
                                            ) : null}
                                        </GlassCard>
                                    );
                                })}
                            </div>
                        )}
                    </section>
                </div>
            ) : (
                <GlassCard className="border border-amber-100 bg-amber-50 p-5">
                    <p className="text-sm text-amber-800">
                        Journey 没有返回可展示数据，请刷新后重试。
                    </p>
                </GlassCard>
            )}
        </div>
    );
}
