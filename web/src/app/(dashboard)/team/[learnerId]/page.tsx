"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
    ArrowLeft,
    RefreshCw,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Lock,
    User,
} from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useTeamJourneyDetail } from "@/hooks/use-team-journey-detail";
import { getApiErrorMessage } from "@/lib/api/client";
import type {
    TrainingJourneyModuleProgress,
    TrainingJourneyResponse,
} from "@/lib/api/types";
import {
    getStageLabel,
    getStageToneClass,
    formatRiskReasons,
    buildModuleKeyToTitleMapFromJourney,
    detectJourneyRiskModules,
} from "@/lib/team-journey/view-models";
import { cn } from "@/lib/utils";

interface ModuleViewModel {
    module_key: string;
    display_title: string;
    stage_label: string;
    stage_tone: string;
    passed_label: string;
    passed_tone: "green" | "red" | "gray";
    score_label: string;
    next_action_label: string;
    is_risk: boolean;
}

function getPassedLabel(passed: boolean | null | undefined): string {
    if (passed === true) {
        return "已通过";
    }
    if (passed === false) {
        return "未通过";
    }
    return "待判分";
}

function getPassedTone(passed: boolean | null | undefined): "green" | "red" | "gray" {
    if (passed === true) {
        return "green";
    }
    if (passed === false) {
        return "red";
    }
    return "gray";
}

function formatScore(score: number | null | undefined, maxScore: number | null | undefined): string {
    if (typeof score === "number" && typeof maxScore === "number" && maxScore > 0) {
        return `${score} / ${maxScore}`;
    }
    if (typeof score === "number") {
        return String(score);
    }
    return "暂无成绩";
}

function mapModuleToViewModel(
    module: TrainingJourneyModuleProgress,
    riskModuleKeys: Set<string>,
): ModuleViewModel {
    const title = module.display_name?.trim() || module.title?.trim() || "未命名模块";
    return {
        module_key: module.module_key,
        display_title: title,
        stage_label: getStageLabel(module.stage ?? module.status),
        stage_tone: getStageToneClass(module.stage ?? module.status),
        passed_label: getPassedLabel(module.passed),
        passed_tone: getPassedTone(module.passed),
        score_label: formatScore(module.score, module.max_score),
        next_action_label: module.next_action?.label?.trim() || "无待办",
        is_risk: riskModuleKeys.has(module.module_key),
    };
}

function DetailLoadingSkeleton() {
    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <Skeleton className="h-10 w-48 rounded-full" />
            <Skeleton className="h-28 rounded-[2rem]" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[0, 1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-24 rounded-[2rem]" />
                ))}
            </div>
            <div className="space-y-3">
                {[0, 1, 2].map((i) => (
                    <Skeleton key={i} className="h-24 rounded-2xl" />
                ))}
            </div>
        </div>
    );
}

function DetailErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <EmptyState
            title="学员数据加载失败"
            description={`${message} 请稍后重试，或检查网络连接后刷新页面。`}
            actionLabel="重试"
            onAction={onRetry}
            icon={<RefreshCw className="w-10 h-10 text-slate-300" />}
        />
    );
}

function DetailPermissionDenied() {
    return (
        <EmptyState
            title="该页面仅向销售组长/培训经理开放"
            description="当前账号无团队管理权限。如需查看下属学习情况，请联系管理员开通培训经理角色。"
            icon={<User className="w-10 h-10 text-slate-300" />}
        />
    );
}

function DetailNotFound() {
    return (
        <EmptyState
            title="学员记录不存在或无权查看"
            description="该学员记录可能已被移除，或您所在部门无权查看该学员的学习情况。请返回团队看板核对。"
            icon={<User className="w-10 h-10 text-slate-300" />}
        />
    );
}

function ProgressCard({ journey }: { journey: TrainingJourneyResponse }) {
    const overall = journey.overall_progress;
    const total = overall.total_modules ?? 0;
    const completed = overall.completed_modules ?? 0;
    const passed = overall.passed_modules ?? 0;
    const failed = overall.failed_modules ?? 0;
    const needsRemediation = overall.needs_remediation_modules ?? 0;
    const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;

    return (
        <GlassCard className="p-6 border border-white/60">
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">整体进度</h2>
                    <p className="text-sm text-slate-500 mt-1">
                        {getStageLabel(journey.training_stage)} · 已完成 {completed}/{total} 个模块
                    </p>
                </div>
                <div className="text-right">
                    <div className="text-3xl font-black text-slate-900">{percent}%</div>
                </div>
            </div>
            <div className="mt-4 h-2 rounded-full bg-slate-100 overflow-hidden">
                <div
                    className={cn(
                        "h-full rounded-full transition-all",
                        percent === 100 ? "bg-emerald-500" : "bg-blue-500",
                    )}
                    style={{ width: `${percent}%` }}
                />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant="green" className="shrink-0">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    通过 {passed}
                </Badge>
                {failed > 0 ? (
                    <Badge variant="red" className="shrink-0">
                        <XCircle className="w-3 h-3 mr-1" />
                        未通过 {failed}
                    </Badge>
                ) : null}
                {needsRemediation > 0 ? (
                    <Badge variant="orange" className="shrink-0">
                        <AlertTriangle className="w-3 h-3 mr-1" />
                        待补救 {needsRemediation}
                    </Badge>
                ) : null}
            </div>
        </GlassCard>
    );
}

function ModuleCard({ module }: { module: ModuleViewModel }) {
    return (
        <GlassCard className="p-5 border border-white/60">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-bold text-slate-900 truncate">{module.display_title}</h3>
                        {module.is_risk ? (
                            <Badge variant="red" className="shrink-0">
                                <AlertTriangle className="w-3 h-3 mr-1" />
                                需关注
                            </Badge>
                        ) : null}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">下一步：{module.next_action_label}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <span className={cn("inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border", module.stage_tone)}>
                        {module.stage_label}
                    </span>
                    <Badge variant={module.passed_tone} className="shrink-0">
                        {module.passed_label}
                    </Badge>
                </div>
            </div>
            <div className="mt-3 flex items-center gap-4 text-sm">
                <span className="text-slate-500">成绩</span>
                <span className="font-bold text-slate-900">{module.score_label}</span>
            </div>
        </GlassCard>
    );
}

export default function TeamLearnerDetailPage() {
    const params = useParams<{ learnerId: string }>();
    const learnerId = params?.learnerId ?? "";
    const { data: currentUser } = useCurrentUser();
    const detail = useTeamJourneyDetail({ learnerId });

    const role = currentUser?.role;
    const isPermissionDenied = Boolean(role)
        && role !== "training_manager"
        && role !== "admin"
        && role !== "super_admin";

    const viewModels = useMemo<ModuleViewModel[]>(() => {
        const journey = detail.journey;
        if (!journey) {
            return [];
        }
        const riskIndicators = detectJourneyRiskModules(journey);
        const riskKeys = new Set(riskIndicators.map((i) => i.module_key));
        return (journey.modules ?? [])
            .slice()
            .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
            .map((m) => mapModuleToViewModel(m, riskKeys));
    }, [detail.journey]);

    const riskReasonLabels = useMemo<string[]>(() => {
        const journey = detail.journey;
        if (!journey) {
            return [];
        }
        const indicators = detectJourneyRiskModules(journey);
        if (indicators.length === 0) {
            return [];
        }
        const moduleKeyToTitle = buildModuleKeyToTitleMapFromJourney(journey);
        const reasons = indicators.map((i) => i.reason);
        return formatRiskReasons(reasons, moduleKeyToTitle);
    }, [detail.journey]);

    const journey = detail.journey;
    const learnerName = journey?.learner_name?.trim() || "未命名学员";
    const department = journey?.department?.trim() || "未分配部门";
    const stageLabel = journey ? getStageLabel(journey.training_stage) : "";

    const handleRetry = () => {
        void detail.refetch();
    };

    if (isPermissionDenied) {
        return (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
                <DetailPermissionDenied />
            </div>
        );
    }

    const isLoading = detail.isLoading;
    const isError = detail.isError;
    const errorMessage = detail.error ? getApiErrorMessage(detail.error) : "学员数据暂时无法读取";

    // 后端 404 [TRAINING_RECORD_NOT_FOUND]：跨部门/不存在均返回此码，不泄露学员是否存在。
    const isNotFound = Boolean(
        detail.error
            && typeof detail.error === "object"
            && "message" in detail.error
            && String((detail.error as { message?: string }).message ?? "").includes("[TRAINING_RECORD_NOT_FOUND]"),
    );

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            <header className="flex items-center justify-between px-2 flex-wrap gap-3">
                <div className="flex items-center gap-3 min-w-0">
                    <Button asChild variant="outline" size="sm" className="shrink-0">
                        <Link href="/team">
                            <ArrowLeft className="w-4 h-4 mr-1" />
                            返回团队
                        </Link>
                    </Button>
                    <div className="min-w-0">
                        <h1 className="text-2xl font-black text-slate-900 tracking-tight leading-tight truncate">
                            {isLoading ? <Skeleton className="h-8 w-40" /> : learnerName}
                        </h1>
                        {isLoading ? null : (
                            <p className="text-slate-500 mt-1 text-sm font-medium">
                                {department} · {stageLabel}
                            </p>
                        )}
                    </div>
                </div>
                {isError && !isNotFound ? (
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={handleRetry}
                    >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        重试数据
                    </Button>
                ) : null}
            </header>

            {isLoading ? (
                <DetailLoadingSkeleton />
            ) : isNotFound ? (
                <DetailNotFound />
            ) : isError ? (
                <DetailErrorState message={errorMessage} onRetry={handleRetry} />
            ) : journey ? (
                <>
                    {riskReasonLabels.length > 0 ? (
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-start gap-3">
                            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                            <div>
                                <p className="font-bold">待辅导标记</p>
                                <p className="mt-1">{riskReasonLabels.join("、")}</p>
                            </div>
                        </div>
                    ) : null}

                    <ProgressCard journey={journey} />

                    <section>
                        <div className="flex items-center justify-between mb-4 px-2">
                            <h2 className="text-xl font-bold text-slate-900">模块进度</h2>
                            <span className="text-xs text-slate-400">
                                共 {viewModels.length} 个模块
                            </span>
                        </div>

                        {viewModels.length === 0 ? (
                            <EmptyState
                                title="暂无模块记录"
                                description="该学员的训练路径尚未配置模块，或模块数据仍在生成中。"
                                icon={<Lock className="w-10 h-10 text-slate-300" />}
                            />
                        ) : (
                            <div className="space-y-3">
                                {viewModels.map((module) => (
                                    <ModuleCard key={module.module_key} module={module} />
                                ))}
                            </div>
                        )}
                    </section>
                </>
            ) : (
                <DetailNotFound />
            )}

            <div className="text-center text-xs text-slate-400 pt-4">
                仅展示本部门学员；如需跨部门查看，请联系管理员。
            </div>
        </div>
    );
}
