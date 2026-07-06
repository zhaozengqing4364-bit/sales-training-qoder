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
    TrainingJourneyModuleProgress,
    TrainingJourneyModuleOutcome,
    TrainingJourneyRetrainingRequest,
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
    error_terminal: "需要处理",
    error_transient: "暂时不可用",
};

const JOURNEY_MODULE_TYPE_LABELS: Record<TrainingJourneyModuleType, string> = {
    audio_scoring: "语音作业",
    article_exam: "文章学习 / 考卷",
    audio_scoring_group: "多时长语音作业",
    ai_coach: "AI 教练",
    realtime_placeholder: "暂未开放模块",
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

const JOURNEY_FAILURE_TYPE_LABELS: Record<
    NonNullable<TrainingJourneyModuleOutcome["failure_type"]>,
    string
> = {
    terminal: "需要人工处理",
    transient: "暂时不可用",
    voluntary: "已结束",
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

function getModuleTypeLabel(moduleType: TrainingJourneyModuleType): string {
    return JOURNEY_MODULE_TYPE_LABELS[moduleType] ?? moduleType;
}

function getOutcomeRecordLabel(recordType: TrainingJourneyModuleOutcome["record_type"]): string {
    return JOURNEY_OUTCOME_RECORD_LABELS[recordType] ?? recordType;
}

function getOutcomeFailureTypeLabel(
    failureType: TrainingJourneyModuleOutcome["failure_type"],
): string | null {
    if (!failureType) {
        return null;
    }
    return JOURNEY_FAILURE_TYPE_LABELS[failureType] ?? null;
}

function getLatestRecordDescription(outcome: TrainingJourneyModuleOutcome): string {
    const failureTypeLabel = getOutcomeFailureTypeLabel(outcome.failure_type);
    if (!failureTypeLabel) {
        return `最近记录：${getOutcomeRecordLabel(outcome.record_type)}`;
    }
    return `最近记录：${getOutcomeRecordLabel(outcome.record_type)} · ${failureTypeLabel}`;
}

function getOutcomeVerdict(
    outcome: TrainingJourneyModuleOutcome | null | undefined,
): string | null {
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

function toLearnerFacingMessage(message: string): string {
    const learnerMessage = message
        .replace(/\s*\(trace_id:[^)]+\)/g, "")
        .replace(/\[[A-Z0-9_]+\]\s*/g, "")
        .replace(/TrainingJourney/g, "训练路径")
        .replace(/Journey 服务/g, "训练路径服务")
        .replace(/Journey/g, "训练路径")
        .replace(/active path revision/g, "当前发布的训练路径")
        .replace(/active revision/g, "当前发布版本")
        .replace(/runtime binding/g, "后台接入配置")
        .replace(/provider readiness/g, "服务开放检查")
        .replace(/target_unit_id/g, "训练内容")
        .replace(/AI Coach/g, "AI 教练")
        .replace(/Prompt/g, "后台配置")
        .replace(/learner/g, "学员")
        .replace(/terminal/g, "需要处理")
        .trim();
    return learnerMessage || "训练路径暂时不可用，请稍后重试。";
}

function getApiErrorCode(error: unknown): string | null {
    return error instanceof ApiRequestError ? error.errorCode : null;
}

function getLearnerIssueMessage(error: unknown): string {
    const message = getApiErrorMessage(error);
    const errorCode = getApiErrorCode(error);
    if (
        errorCode === "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]" ||
        message.includes("[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]")
    ) {
        return "当前训练路径还没有发布完成，请联系培训负责人处理后再继续。";
    }
    if (
        errorCode === "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]" ||
        message.includes("[NEWCOMER_REALTIME_PROVIDER_NOT_READY]")
    ) {
        return "真实语音对练暂未开放，不影响你继续完成前置训练和查看已有结果。";
    }
    if (
        errorCode === "[ROLE_REQUIRED]" ||
        errorCode === "[TRAINING_JOURNEY_FORBIDDEN]" ||
        message.includes("[ROLE_REQUIRED]") ||
        message.includes("[TRAINING_JOURNEY_FORBIDDEN]")
    ) {
        return "当前账号没有访问这份训练路径的权限。";
    }
    return toLearnerFacingMessage(message);
}

function getLearnerDiagnosticMessage(message: string): string {
    if (message.includes("Journey 已按 active revision 更新")) {
        return "训练路径已按当前发布版本更新。";
    }
    if (message.includes("runtime binding")) {
        return "真实语音对练还没有完成后台接入，请联系培训负责人处理。";
    }
    if (message.includes("provider readiness")) {
        return "真实语音对练暂未开放，请先完成前置训练或稍后再试。";
    }
    if (message.includes("target_unit_id")) {
        return "这个训练模块还没有绑定可练内容，请联系培训负责人处理。";
    }
    if (
        message.includes("AI Coach") &&
        (message.includes("Prompt") || message.includes("配置非法"))
    ) {
        return "AI 教练暂未完成后台配置，请联系培训负责人处理。";
    }
    if (message.includes("active path revision")) {
        return "当前发布的训练路径配置需要培训负责人处理。";
    }
    return toLearnerFacingMessage(message);
}

function getRetrainingCapabilityLine(request: TrainingJourneyRetrainingRequest): string {
    if (request.capability_labels.length > 0) {
        return request.capability_labels.join("、");
    }
    return "培训负责人指定的训练能力";
}

function getRetrainingActionLabel(request: TrainingJourneyRetrainingRequest): string {
    const targetModule = request.target_modules.find(
        (module) => module.target_path === request.primary_target_path,
    );
    return targetModule?.action_label || "去完成重练";
}

interface EndpointIssueCardProps {
    title: string;
    description: string;
    error: unknown;
    tone: "error" | "warning";
    onRetry: () => void;
}

function EndpointIssueCard({ title, description, error, tone, onRetry }: EndpointIssueCardProps) {
    const message = getLearnerIssueMessage(error);
    const containerClass =
        tone === "error"
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
                    <p className={`text-sm font-medium ${textClass}`}>{message}</p>
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

    const startRealtimeRoleplay = useCallback(
        async (module: TrainingJourneyModuleProgress) => {
            if (
                module.next_action?.action_key !== "start_realtime_roleplay" ||
                module.next_action.disabled
            ) {
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
        },
        [router],
    );

    useEffect(() => {
        const timeoutId = window.setTimeout(() => {
            void loadPage();
        }, 0);
        return () => window.clearTimeout(timeoutId);
    }, [loadPage]);

    const sortedJourneyModules = useMemo(
        () =>
            [...(journey?.modules ?? [])].sort(
                (left, right) => left.order_index - right.order_index,
            ),
        [journey],
    );
    const retrainingRequests = journey?.retraining_requests ?? [];

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
                        <h1 className="text-3xl font-black tracking-tight text-slate-900">
                            新人训练路径
                        </h1>
                        <p className="mt-1 text-sm text-slate-500">
                            按当前已发布的训练路径继续学习、提交作业、补练和查看结果。
                        </p>
                    </div>
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => void loadPage()}
                        disabled={isLoading}
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        刷新
                    </Button>
                </div>
            </div>

            {isLoading ? (
                <div className="grid gap-4 md:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, index) => (
                        <div
                            key={index}
                            className="h-44 animate-pulse rounded-3xl border border-white/60 bg-white/60"
                        />
                    ))}
                </div>
            ) : journeyError ? (
                <div className="space-y-4">
                    <EndpointIssueCard
                        title="训练路径暂不可用"
                        description="系统没有加载到可用的训练任务。请刷新重试，或联系培训负责人检查训练路径配置。"
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
                                <Badge className="bg-slate-100 text-slate-700">当前训练</Badge>
                                <div>
                                    <h2 className="text-2xl font-black text-slate-900">
                                        当前训练状态
                                    </h2>
                                    <p className="mt-1 text-sm text-slate-500">
                                        系统会根据已发布的训练路径展示你现在该做什么。
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2 text-sm text-slate-600">
                                    <span>学员等级：{journey.learner_level.label}</span>
                                    <span>角色等级：{journey.role_level.label}</span>
                                </div>
                            </div>
                            <div className="space-y-2 rounded-2xl bg-slate-50 px-4 py-3 text-right">
                                <p className="text-xs font-medium text-slate-500">当前阶段</p>
                                <Badge
                                    className={getJourneyStageBadgeClass(journey.training_stage)}
                                >
                                    {getJourneyStageLabel(journey.training_stage)}
                                </Badge>
                            </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">模块总数</p>
                                <p className="mt-2 text-2xl font-black text-slate-900">
                                    {journey.overall_progress.total_modules}
                                </p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">已完成</p>
                                <p className="mt-2 text-2xl font-black text-slate-900">
                                    {journey.overall_progress.completed_modules}
                                </p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">通过模块</p>
                                <p className="mt-2 text-2xl font-black text-emerald-700">
                                    {journey.overall_progress.passed_modules}
                                </p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">未通过模块</p>
                                <p className="mt-2 text-2xl font-black text-red-700">
                                    {journey.overall_progress.failed_modules}
                                </p>
                            </div>
                            <div className="rounded-2xl bg-slate-50 p-4">
                                <p className="text-xs text-slate-500">待补救模块</p>
                                <p className="mt-2 text-2xl font-black text-amber-700">
                                    {journey.overall_progress.needs_remediation_modules}
                                </p>
                            </div>
                        </div>

                        {journey.diagnostics.length > 0 ? (
                            <div className="space-y-3">
                                <h3 className="text-sm font-semibold text-slate-900">
                                    需要处理的训练提示
                                </h3>
                                <div className="space-y-2">
                                    {journey.diagnostics.map((diagnostic) => (
                                        <div
                                            key={`${diagnostic.code}-${diagnostic.message}`}
                                            className="rounded-2xl bg-slate-50 p-3"
                                        >
                                            <p className="text-sm text-slate-600">
                                                {getLearnerDiagnosticMessage(diagnostic.message)}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : null}
                    </GlassCard>

                    {retrainingRequests.length > 0 ? (
                        <section className="space-y-4">
                            <div>
                                <h2 className="text-xl font-black text-slate-900">
                                    培训负责人已要求重练
                                </h2>
                                <p className="mt-1 text-sm text-slate-500">
                                    请先完成指定补练，再等待培训负责人复核更新。
                                </p>
                            </div>
                            <div className="space-y-3">
                                {retrainingRequests.map((request) => (
                                    <GlassCard
                                        key={request.request_id}
                                        className="space-y-4 border border-amber-100 bg-amber-50 p-5"
                                    >
                                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                            <div className="space-y-2">
                                                <Badge className="bg-amber-100 text-amber-800">
                                                    待重练
                                                </Badge>
                                                <h3 className="text-lg font-black text-amber-950">
                                                    {getRetrainingCapabilityLine(request)}
                                                </h3>
                                                {request.reason ? (
                                                    <p className="text-sm leading-6 text-amber-900">
                                                        {request.reason}
                                                    </p>
                                                ) : null}
                                                {request.source_evidence_count > 0 ? (
                                                    <p className="text-sm text-amber-800">
                                                        关联了 {request.source_evidence_count}{" "}
                                                        份你提交过的训练结果。
                                                    </p>
                                                ) : null}
                                            </div>
                                            {request.primary_target_path ? (
                                                <Button
                                                    asChild
                                                    variant="outline"
                                                    className="rounded-full border-amber-200 bg-white text-amber-900"
                                                >
                                                    <Link href={request.primary_target_path}>
                                                        {getRetrainingActionLabel(request)}
                                                    </Link>
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant="outline"
                                                    className="rounded-full"
                                                    disabled
                                                >
                                                    等待补练入口
                                                </Button>
                                            )}
                                        </div>
                                        {request.target_modules.length > 0 ? (
                                            <div className="flex flex-wrap gap-2">
                                                {request.target_modules.map((module) => (
                                                    <Badge
                                                        key={`${request.request_id}-${module.kind}-${module.module_key}`}
                                                        className="bg-white text-amber-800"
                                                    >
                                                        {module.title || "训练模块"}
                                                    </Badge>
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-sm text-amber-800">
                                                当前暂时无法定位到具体模块，请联系培训负责人确认补练入口。
                                            </p>
                                        )}
                                    </GlassCard>
                                ))}
                            </div>
                        </section>
                    ) : null}

                    <section className="space-y-4">
                        <div>
                            <h2 className="text-xl font-black text-slate-900">模块闭环状态</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                每个模块会说明当前状态、最近结果和下一步动作。
                            </p>
                        </div>
                        {realtimeStartError ? (
                            <EndpointIssueCard
                                title="真实语音对练暂不可用"
                                description="系统没有启动对练会话。你可以继续完成前置训练，或稍后再试。"
                                error={realtimeStartError}
                                tone="error"
                                onRetry={() => setRealtimeStartError(null)}
                            />
                        ) : null}
                        {sortedJourneyModules.length === 0 ? (
                            <GlassCard className="border border-amber-100 bg-amber-50 p-5">
                                <p className="text-sm text-amber-800">
                                    当前训练路径还没有可练模块，请联系培训负责人补齐配置。
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
                                                        <Badge
                                                            className={getJourneyStageBadgeClass(
                                                                module.stage,
                                                            )}
                                                        >
                                                            {getJourneyStageLabel(module.stage)}
                                                        </Badge>
                                                        {!module.enabled ? (
                                                            <Badge className="bg-slate-200 text-slate-700">
                                                                已停用
                                                            </Badge>
                                                        ) : null}
                                                    </div>
                                                    <h3 className="text-lg font-black text-slate-900">
                                                        {module.display_name}
                                                    </h3>
                                                    <p className="text-sm text-slate-500">
                                                        类型：
                                                        {getModuleTypeLabel(module.module_type)}
                                                    </p>
                                                </div>
                                                {latestVerdict ? (
                                                    <div className="rounded-2xl bg-slate-50 px-4 py-3 text-right">
                                                        <p className="text-xs text-slate-500">
                                                            最近结果
                                                        </p>
                                                        <p className="mt-1 text-sm font-semibold text-slate-900">
                                                            {latestVerdict}
                                                        </p>
                                                    </div>
                                                ) : null}
                                            </div>

                                            <div className="space-y-2 text-sm text-slate-600">
                                                {module.latest_outcome ? (
                                                    <p>
                                                        {getLatestRecordDescription(
                                                            module.latest_outcome,
                                                        )}
                                                    </p>
                                                ) : (
                                                    <p>最近记录：暂无训练结果</p>
                                                )}
                                                {module.learner_level_required?.length ? (
                                                    <p>
                                                        适用等级：
                                                        {module.learner_level_required.join("、")}
                                                    </p>
                                                ) : null}
                                                {module.latest_outcome?.failure_code ? (
                                                    <p>
                                                        最近训练结果需要处理，请按提示重试或联系培训负责人。
                                                    </p>
                                                ) : null}
                                            </div>

                                            {module.unmet_reasons.length > 0 ? (
                                                <div className="space-y-2 rounded-2xl bg-amber-50 p-3">
                                                    <p className="text-sm font-semibold text-amber-900">
                                                        模块诊断
                                                    </p>
                                                    <ul className="space-y-2 text-sm text-amber-800">
                                                        {module.unmet_reasons.map((reason) => (
                                                            <li
                                                                key={`${module.module_key}-${reason.code}`}
                                                            >
                                                                {getLearnerDiagnosticMessage(
                                                                    reason.message,
                                                                )}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            ) : null}

                                            {module.next_action ? (
                                                <div className="space-y-2">
                                                    {module.next_action.action_key ===
                                                        "start_realtime_roleplay" &&
                                                    !module.next_action.disabled ? (
                                                        <Button
                                                            variant="outline"
                                                            className="rounded-full"
                                                            disabled={
                                                                startingRealtimeModuleKey ===
                                                                module.module_key
                                                            }
                                                            onClick={() =>
                                                                void startRealtimeRoleplay(module)
                                                            }
                                                        >
                                                            {startingRealtimeModuleKey ===
                                                            module.module_key
                                                                ? "启动中"
                                                                : module.next_action.label}
                                                        </Button>
                                                    ) : module.next_action.target_path &&
                                                      !module.next_action.disabled ? (
                                                        <Button
                                                            asChild
                                                            variant="outline"
                                                            className="rounded-full"
                                                        >
                                                            <Link
                                                                href={
                                                                    module.next_action.target_path
                                                                }
                                                            >
                                                                {module.next_action.label}
                                                            </Link>
                                                        </Button>
                                                    ) : (
                                                        <Button
                                                            variant="outline"
                                                            className="rounded-full"
                                                            disabled
                                                        >
                                                            {module.next_action.label}
                                                        </Button>
                                                    )}
                                                    {module.next_action.disabled_reason ? (
                                                        <p className="text-xs text-slate-500">
                                                            {getLearnerDiagnosticMessage(
                                                                module.next_action.disabled_reason,
                                                            )}
                                                        </p>
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
                        当前没有可展示的训练数据，请刷新后重试。
                    </p>
                </GlassCard>
            )}
        </div>
    );
}
