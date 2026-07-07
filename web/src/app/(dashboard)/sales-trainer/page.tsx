"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
    AlertTriangle,
    ArrowLeft,
    ArrowRight,
    CheckCircle2,
    Layers,
    Play,
    RefreshCw,
    Trophy,
    XCircle,
    Headphones,
} from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMyAudioSubmissions } from "@/hooks/use-my-audio-submissions";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import type {
    TrainingJourneyModuleProgress,
    TrainingJourneyModuleOutcome,
    TrainingJourneyRetrainingRequest,
    TrainingJourneyModuleType,
    TrainingJourneyResponse,
    TrainingJourneyStage,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";
import {
    getJourneyStageBadgeVariant,
    getJourneyStageCardAccent,
    getModuleIcon,
    getScoreTextColorClass,
} from "@/lib/sales-trainer/journey-presentation";

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

interface StatTileProps {
    icon: React.ReactNode;
    iconBg: string;
    label: string;
    value: number;
    valueClass?: string;
}

function StatTile({ icon, iconBg, label, value, valueClass }: StatTileProps) {
    return (
        <div className="rounded-2xl border border-stone-200/70 bg-white p-4 shadow-[0_1px_2px_rgba(28,25,23,0.04),0_4px_12px_-2px_rgba(28,25,23,0.05)]">
            <div
                className={cn(
                    "mb-3 flex h-10 w-10 items-center justify-center rounded-xl",
                    iconBg,
                )}
            >
                {icon}
            </div>
            <p className="text-xs font-medium text-stone-500">{label}</p>
            <p
                className={cn(
                    "mt-1 text-2xl font-black tabular-nums text-slate-900",
                    valueClass,
                )}
            >
                {value}
            </p>
        </div>
    );
}

function EndpointIssueCard({ title, description, error, tone, onRetry }: EndpointIssueCardProps) {
    const message = getLearnerIssueMessage(error);
    const accentClass =
        tone === "error"
            ? "bg-rose-50/60"
            : "bg-amber-50/60";
    const titleClass = tone === "error" ? "text-rose-950" : "text-amber-950";
    const textClass = tone === "error" ? "text-rose-800" : "text-amber-800";
    const iconClass = tone === "error" ? "text-rose-600" : "text-amber-600";

    return (
        <GlassCard className={cn("space-y-4 p-5", accentClass)}>
            <div className="flex items-start gap-3">
                <AlertTriangle className={cn("mt-0.5 h-5 w-5 shrink-0", iconClass)} aria-hidden />
                <div className="space-y-2">
                    <h2 className={cn("text-lg font-black", titleClass)}>{title}</h2>
                    <p className={cn("text-sm leading-6", textClass)}>{description}</p>
                    <p className={cn("text-sm font-medium", textClass)}>{message}</p>
                </div>
            </div>
            <Button
                variant={tone === "error" ? "danger" : "outline"}
                onClick={onRetry}
            >
                <RefreshCw className="mr-2 h-4 w-4" />
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

    // 学员"我的录音"区：只在 journey 加载成功后加载，避免无路径时多余请求。
    const myAudio = useMyAudioSubmissions({ enabled: Boolean(journey) });

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
                                <Badge variant="gray">当前训练</Badge>
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
                            <div className="space-y-2 rounded-2xl border border-stone-200/70 bg-stone-50/60 px-4 py-3 text-right">
                                <p className="text-xs font-medium text-stone-500">当前阶段</p>
                                <Badge variant={getJourneyStageBadgeVariant(journey.training_stage)}>
                                    {getJourneyStageLabel(journey.training_stage)}
                                </Badge>
                            </div>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                            <StatTile
                                icon={<Layers className="h-5 w-5 text-stone-500" />}
                                iconBg="bg-stone-100"
                                label="模块总数"
                                value={journey.overall_progress.total_modules}
                            />
                            <StatTile
                                icon={<CheckCircle2 className="h-5 w-5 text-stone-600" />}
                                iconBg="bg-stone-100"
                                label="已完成"
                                value={journey.overall_progress.completed_modules}
                            />
                            <StatTile
                                icon={<Trophy className="h-5 w-5 text-emerald-700" />}
                                iconBg="bg-emerald-50"
                                label="通过模块"
                                value={journey.overall_progress.passed_modules}
                                valueClass="text-emerald-700"
                            />
                            <StatTile
                                icon={<XCircle className="h-5 w-5 text-rose-700" />}
                                iconBg="bg-rose-50"
                                label="未通过模块"
                                value={journey.overall_progress.failed_modules}
                                valueClass="text-rose-700"
                            />
                            <StatTile
                                icon={<AlertTriangle className="h-5 w-5 text-amber-700" />}
                                iconBg="bg-amber-50"
                                label="待补救模块"
                                value={journey.overall_progress.needs_remediation_modules}
                                valueClass="text-amber-700"
                            />
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
                                            className="rounded-xl border border-stone-200/70 bg-stone-50/60 p-3"
                                        >
                                            <p className="text-sm text-stone-700">
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
                                        className="space-y-4 p-5"
                                    >
                                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                            <div className="space-y-2">
                                                <div className="flex items-center gap-2">
                                                    <RefreshCw className="h-4 w-4 text-amber-600" />
                                                    <Badge variant="orange">待重练</Badge>
                                                </div>
                                                <h3 className="text-lg font-black text-slate-900">
                                                    {getRetrainingCapabilityLine(request)}
                                                </h3>
                                                {request.reason ? (
                                                    <p className="text-sm leading-6 text-slate-600">
                                                        {request.reason}
                                                    </p>
                                                ) : null}
                                                {request.source_evidence_count > 0 ? (
                                                    <p className="text-sm text-slate-500">
                                                        关联了 {request.source_evidence_count}{" "}
                                                        份你提交过的训练结果。
                                                    </p>
                                                ) : null}
                                            </div>
                                            {request.primary_target_path ? (
                                                <Button asChild variant="primary">
                                                    <Link href={request.primary_target_path}>
                                                        <ArrowRight className="mr-2 h-4 w-4" />
                                                        {getRetrainingActionLabel(request)}
                                                    </Link>
                                                </Button>
                                            ) : (
                                                <Button variant="outline" disabled>
                                                    等待补练入口
                                                </Button>
                                            )}
                                        </div>
                                        {request.target_modules.length > 0 ? (
                                            <div className="flex flex-wrap gap-2">
                                                {request.target_modules.map((module) => (
                                                    <Badge
                                                        key={`${request.request_id}-${module.kind}-${module.module_key}`}
                                                        variant="outline"
                                                    >
                                                        {module.title || "训练模块"}
                                                    </Badge>
                                                ))}
                                            </div>
                                        ) : (
                                            <p className="text-sm text-slate-500">
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
                                    const accent = getJourneyStageCardAccent(module.stage);
                                    const ModuleIcon = getModuleIcon(module.module_type);
                                    const latestOutcome = module.latest_outcome;
                                    const latestPassed = latestOutcome?.passed;
                                    const recentResultBg =
                                        latestPassed === true
                                            ? "bg-emerald-50"
                                            : latestPassed === false
                                              ? "bg-rose-50"
                                              : "bg-amber-50";
                                    const recentResultText =
                                        latestPassed === true
                                            ? "text-emerald-700"
                                            : latestPassed === false
                                              ? "text-rose-700"
                                              : "text-amber-700";
                                    return (
                                        <GlassCard
                                            key={`${module.kind}-${module.module_key}`}
                                            className="space-y-4 p-5"
                                        >
                                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                                <div className="space-y-2">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <div
                                                            className={cn(
                                                                "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                                                                accent.iconBg,
                                                            )}
                                                        >
                                                            <ModuleIcon
                                                                className={cn(
                                                                    "h-5 w-5",
                                                                    accent.iconColor,
                                                                )}
                                                            />
                                                        </div>
                                                        <Badge variant="gray">
                                                            模块 {module.order_index}
                                                        </Badge>
                                                        <Badge
                                                            variant={getJourneyStageBadgeVariant(
                                                                module.stage,
                                                            )}
                                                        >
                                                            {getJourneyStageLabel(module.stage)}
                                                        </Badge>
                                                        {!module.enabled ? (
                                                            <Badge variant="secondary">
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
                                                    <div
                                                        className={cn(
                                                            "rounded-2xl px-4 py-3 text-right",
                                                            recentResultBg,
                                                        )}
                                                    >
                                                        <p className="text-xs text-slate-500">
                                                            最近结果
                                                        </p>
                                                        <p
                                                            className={cn(
                                                                "mt-1 text-sm font-semibold",
                                                                recentResultText,
                                                            )}
                                                        >
                                                            {latestVerdict}
                                                        </p>
                                                        {typeof latestOutcome?.score === "number" ? (
                                                            <p
                                                                className={cn(
                                                                    "mt-1 text-lg font-black tabular-nums",
                                                                    getScoreTextColorClass(
                                                                        latestOutcome.score,
                                                                    ),
                                                                )}
                                                            >
                                                                {latestOutcome.score}
                                                                {typeof latestOutcome.max_score ===
                                                                    "number"
                                                                    ? ` / ${latestOutcome.max_score}`
                                                                    : ""}
                                                            </p>
                                                        ) : null}
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
                                                <div className="space-y-2 rounded-xl bg-amber-50/50 p-3">
                                                    <p className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                                                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                                                        模块诊断
                                                    </p>
                                                    <ul className="space-y-2 text-sm text-stone-700">
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
                                                            variant="primary"
                                                            isLoading={
                                                                startingRealtimeModuleKey ===
                                                                module.module_key
                                                            }
                                                            onClick={() =>
                                                                void startRealtimeRoleplay(module)
                                                            }
                                                        >
                                                            <Play className="mr-2 h-4 w-4" />
                                                            {startingRealtimeModuleKey ===
                                                            module.module_key
                                                                ? "启动中"
                                                                : module.next_action.label}
                                                        </Button>
                                                    ) : module.next_action.target_path &&
                                                      !module.next_action.disabled ? (
                                                        <Button asChild variant="primary">
                                                            <Link
                                                                href={
                                                                    module.next_action.target_path
                                                                }
                                                            >
                                                                <ArrowRight className="mr-2 h-4 w-4" />
                                                                {module.next_action.label}
                                                            </Link>
                                                        </Button>
                                                    ) : (
                                                        <Button variant="outline" disabled>
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

                    <section className="space-y-4">
                        <div>
                            <h2 className="text-xl font-black text-slate-900">我的录音</h2>
                            <p className="mt-1 text-sm text-slate-500">
                                按上传时间倒序列出你提交过的语音作业，可回看分数与反馈。
                            </p>
                        </div>
                        {myAudio.isLoading ? (
                            <GlassCard className="p-5">
                                <p className="text-sm text-slate-500">正在加载录音记录...</p>
                            </GlassCard>
                        ) : myAudio.isError ? (
                            <GlassCard className="space-y-3 p-5">
                                <p className="text-sm text-rose-700">录音记录加载失败：{getApiErrorMessage(myAudio.error)}</p>
                                <Button variant="outline" onClick={() => void myAudio.refetch()}>
                                    <RefreshCw className="mr-2 h-4 w-4" />
                                    重试
                                </Button>
                            </GlassCard>
                        ) : myAudio.submissions.length === 0 ? (
                            <GlassCard className="p-5">
                                <p className="text-sm text-slate-500">
                                    还没有录音，完成语音作业后这里会显示。
                                </p>
                            </GlassCard>
                        ) : (
                            <div className="space-y-3">
                                {myAudio.submissions.map((submission) => {
                                    const score = submission.score_result?.total_score;
                                    const passed = submission.score_result?.passed;
                                    const resultHref = `/sales-trainer/audio/result/${submission.submission_id}`;
                                    return (
                                        <GlassCard key={submission.submission_id} className="p-4">
                                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                                <div className="min-w-0 flex-1">
                                                    <p className="truncate font-semibold text-slate-900">
                                                        {submission.original_filename}
                                                    </p>
                                                    <p className="mt-1 text-xs text-slate-500">
                                                        {new Date(submission.created_at).toLocaleString()}
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    {typeof score === "number" ? (
                                                        <div className="text-right">
                                                            <p className="text-xs text-slate-400">分数</p>
                                                            <p
                                                                className={cn(
                                                                    "text-lg font-black tabular-nums",
                                                                    passed === true
                                                                        ? "text-emerald-600"
                                                                        : passed === false
                                                                          ? "text-rose-600"
                                                                          : "text-slate-900",
                                                                )}
                                                            >
                                                                {score}
                                                            </p>
                                                        </div>
                                                    ) : (
                                                        <Badge variant="gray">未评分</Badge>
                                                    )}
                                                    {passed === true ? (
                                                        <Badge variant="green">通过</Badge>
                                                    ) : passed === false ? (
                                                        <Badge variant="red">未通过</Badge>
                                                    ) : null}
                                                    <Button asChild variant="outline" size="sm">
                                                        <Link href={resultHref}>
                                                            <Headphones className="mr-2 h-4 w-4" />
                                                            回看
                                                        </Link>
                                                    </Button>
                                                </div>
                                            </div>
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
