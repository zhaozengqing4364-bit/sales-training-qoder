"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
    Users,
    UserCheck,
    AlertTriangle,
    RefreshCw,
    ArrowRight,
    TrendingUp,
} from "lucide-react";

import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useTeamJourneys } from "@/hooks/use-team-journeys";
import { getApiErrorMessage } from "@/lib/api/client";
import type {
    TrainingJourneyResponse,
    TrainingJourneyStage,
    TrainingJourneyAnalyticsResponse,
} from "@/lib/api/types/training-journey";
import {
    getStageLabel,
    getStageToneClass,
    formatRiskReasons,
    buildModuleKeyToTitleMap,
} from "@/lib/team-journey/view-models";
import { cn } from "@/lib/utils";

interface TeamSummaryCards {
    totalCount: number;
    inProgressCount: number;
    completedCount: number;
    needsCoachingCount: number;
}

function buildTeamSummary(
    analytics: TrainingJourneyAnalyticsResponse | undefined,
): TeamSummaryCards {
    if (!analytics) {
        return {
            totalCount: 0,
            inProgressCount: 0,
            completedCount: 0,
            needsCoachingCount: 0,
        };
    }

    const inProgressCount = analytics.funnel
        .filter((entry) => entry.stage === "in_progress")
        .reduce((sum, entry) => sum + entry.learner_count, 0);

    return {
        totalCount: analytics.summary.learner_count ?? 0,
        inProgressCount,
        completedCount: analytics.summary.passed_learner_count ?? 0,
        needsCoachingCount: analytics.summary.risk_learner_count ?? 0,
    };
}

interface LearnerRowViewModel {
    journey_id: string;
    learner_id: string;
    learner_name: string;
    department: string;
    training_stage: TrainingJourneyStage;
    stage_label: string;
    stage_tone: string;
    total_modules: number;
    completed_modules: number;
    passed_modules: number;
    failed_modules: number;
    needs_remediation_modules: number;
    progress_percent: number;
    is_risk: boolean;
    risk_reasons: string[];
}

function mapJourneyToViewModel(
    journey: TrainingJourneyResponse,
    riskLearnerIds: Set<string>,
    riskReasonsMap: Map<string, string[]>,
    moduleKeyToTitle: Map<string, string>,
): LearnerRowViewModel {
    const overall = journey.overall_progress;
    const totalModules = overall.total_modules ?? 0;
    const completedModules = overall.completed_modules ?? 0;
    const progressPercent = totalModules > 0
        ? Math.min(100, Math.round((completedModules / totalModules) * 100))
        : 0;

    const rawReasons = riskReasonsMap.get(journey.learner_id) ?? [];

    return {
        journey_id: journey.journey_id,
        learner_id: journey.learner_id,
        learner_name: journey.learner_name?.trim() || "未命名学员",
        department: journey.department?.trim() || "未分配部门",
        training_stage: journey.training_stage,
        stage_label: getStageLabel(journey.training_stage),
        stage_tone: getStageToneClass(journey.training_stage),
        total_modules: totalModules,
        completed_modules: completedModules,
        passed_modules: overall.passed_modules ?? 0,
        failed_modules: overall.failed_modules ?? 0,
        needs_remediation_modules: overall.needs_remediation_modules ?? 0,
        progress_percent: progressPercent,
        is_risk: riskLearnerIds.has(journey.learner_id),
        risk_reasons: formatRiskReasons(rawReasons, moduleKeyToTitle),
    };
}

function getDisplayName(currentUser: ReturnType<typeof useCurrentUser>["data"]): string {
    return currentUser?.display_name || currentUser?.name || currentUser?.email?.split("@")[0] || "管理员";
}

function TeamSummaryCard({
    label,
    value,
    icon,
    tone,
    isLoading,
}: {
    label: string;
    value: number;
    icon: React.ReactNode;
    tone: "blue" | "amber" | "emerald" | "red";
    isLoading: boolean;
}) {
    const toneClasses = {
        blue: "bg-blue-50 text-blue-700 border-blue-100",
        amber: "bg-amber-50 text-amber-700 border-amber-100",
        emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
        red: "bg-red-50 text-red-700 border-red-100",
    };

    return (
        <GlassCard className="p-5 border border-white/60">
            <div className="flex items-center gap-3">
                <div className={cn("w-11 h-11 rounded-2xl flex items-center justify-center border", toneClasses[tone])}>
                    {icon}
                </div>
                <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{label}</p>
                    <h3 className="mt-1 text-2xl font-black text-slate-900">
                        {isLoading ? <Skeleton className="h-7 w-12" /> : value}
                    </h3>
                </div>
            </div>
        </GlassCard>
    );
}

function LearnerRow({ row }: { row: LearnerRowViewModel }) {
    const detailHref = `/team/${row.learner_id}`;

    return (
        <Link
            href={detailHref}
            className="block rounded-2xl border border-slate-100 bg-white/80 px-5 py-4 transition-all hover:border-slate-200 hover:bg-white hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
        >
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-600 shrink-0">
                        {row.learner_name.slice(0, 1)}
                    </div>
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 truncate">{row.learner_name}</span>
                            {row.is_risk ? (
                                <Badge variant="red" className="shrink-0">
                                    <AlertTriangle className="w-3 h-3 mr-1" />
                                    待辅导
                                </Badge>
                            ) : null}
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 truncate">
                            {row.department} · {row.stage_label}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="text-right">
                        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">进度</div>
                        <div className="text-sm font-bold text-slate-900">
                            {row.completed_modules}/{row.total_modules}
                        </div>
                    </div>
                    <div className="w-24 hidden sm:block">
                        <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                            <div
                                className={cn(
                                    "h-full rounded-full transition-all",
                                    row.progress_percent === 100
                                        ? "bg-emerald-500"
                                        : row.is_risk
                                            ? "bg-amber-500"
                                            : "bg-blue-500",
                                )}
                                style={{ width: `${row.progress_percent}%` }}
                            />
                        </div>
                        <p className="text-[10px] text-slate-400 mt-1 text-right">{row.progress_percent}%</p>
                    </div>
                    <div className="flex items-center gap-2 text-right">
                        <Badge variant={row.passed_modules > 0 ? "green" : "gray"} className="shrink-0">
                            通过 {row.passed_modules}
                        </Badge>
                        {row.failed_modules > 0 ? (
                            <Badge variant="red" className="shrink-0">
                                未通过 {row.failed_modules}
                            </Badge>
                        ) : null}
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-300 shrink-0" />
                </div>
            </div>

            {row.is_risk && row.risk_reasons.length > 0 ? (
                <div className="mt-3 flex items-start gap-2 rounded-lg bg-amber-50/60 px-3 py-2 text-xs text-amber-800">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    <span>{row.risk_reasons.join("、")}</span>
                </div>
            ) : null}
        </Link>
    );
}

function TeamLoadingSkeleton() {
    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[0, 1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-24 rounded-[2rem]" />
                ))}
            </div>
            <div className="space-y-3">
                {[0, 1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-20 rounded-2xl" />
                ))}
            </div>
        </div>
    );
}

function TeamErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
    return (
        <EmptyState
            title="团队数据加载失败"
            description={`${message} 请稍后重试，或检查网络连接后刷新页面。`}
            actionLabel="重试"
            onAction={onRetry}
            icon={<RefreshCw className="w-10 h-10 text-slate-300" />}
        />
    );
}

function TeamPermissionDenied() {
    return (
        <EmptyState
            title="该页面仅向销售组长/培训经理开放"
            description="当前账号无团队管理权限。如需查看下属学习情况，请联系管理员开通培训经理角色。"
            icon={<Users className="w-10 h-10 text-slate-300" />}
        />
    );
}

function TeamEmptyDepartment() {
    return (
        <EmptyState
            title="您尚未分配部门"
            description="团队看板按部门展示下属学员。请联系管理员配置您的部门后再查看团队学习情况。"
            icon={<Users className="w-10 h-10 text-slate-300" />}
        />
    );
}

function TeamNoLearners() {
    return (
        <EmptyState
            title="本部门暂无学员"
            description="当前部门下没有进行新人训练的学员。学员开始训练后将出现在此列表。"
            icon={<Users className="w-10 h-10 text-slate-300" />}
        />
    );
}

export default function TeamDashboardPage() {
    const { data: currentUser } = useCurrentUser();
    const teamData = useTeamJourneys({ limit: 50, offset: 0 });

    const displayName = getDisplayName(currentUser);
    const role = currentUser?.role;

    const riskLearnerMap = useMemo(() => {
        const ids = new Set<string>();
        const reasons = new Map<string, string[]>();
        const riskLearners = teamData.analytics.data?.risk_learners ?? [];
        for (const learner of riskLearners) {
            ids.add(learner.learner_id);
            reasons.set(learner.learner_id, learner.risk_reasons ?? []);
        }
        return { ids, reasons };
    }, [teamData.analytics.data]);

    const summary = useMemo(
        () => buildTeamSummary(teamData.analytics.data),
        [teamData.analytics.data],
    );

    const learnerRows = useMemo(() => {
        const items = teamData.journeys.data?.items ?? [];
        const moduleKeyToTitle = buildModuleKeyToTitleMap(items);
        return items.map((journey) =>
            mapJourneyToViewModel(
                journey,
                riskLearnerMap.ids,
                riskLearnerMap.reasons,
                moduleKeyToTitle,
            ),
        );
    }, [teamData.journeys.data, riskLearnerMap]);

    const isPermissionDenied = Boolean(role) && role !== "training_manager" && role !== "admin" && role !== "super_admin";

    if (isPermissionDenied) {
        return (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
                <TeamPermissionDenied />
            </div>
        );
    }

    const hasDepartment = Boolean(currentUser?.department);
    const isLoading = teamData.isLoading;
    const isError = teamData.isError;
    const errorMessage = teamData.error ? getApiErrorMessage(teamData.error) : "团队数据暂时无法读取";

    const handleRetry = () => {
        void teamData.refetch();
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            <header className="flex items-end justify-between px-2 flex-wrap gap-3">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight leading-tight">
                        我的团队
                    </h1>
                    <p className="text-slate-500 mt-2 text-base font-medium">
                        {displayName}，查看本部门下属学员的学习进度与待辅导情况。
                    </p>
                </div>
                {isError ? (
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
                <TeamLoadingSkeleton />
            ) : isError && !teamData.journeys.data && !teamData.analytics.data ? (
                <TeamErrorState message={errorMessage} onRetry={handleRetry} />
            ) : (
                <>
                    {!hasDepartment && role === "training_manager" ? (
                        <TeamEmptyDepartment />
                    ) : (
                        <>
                            <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <TeamSummaryCard
                                    label="总人数"
                                    value={summary.totalCount}
                                    tone="blue"
                                    isLoading={false}
                                    icon={<Users className="w-5 h-5" />}
                                />
                                <TeamSummaryCard
                                    label="进行中"
                                    value={summary.inProgressCount}
                                    tone="amber"
                                    isLoading={false}
                                    icon={<TrendingUp className="w-5 h-5" />}
                                />
                                <TeamSummaryCard
                                    label="已完成"
                                    value={summary.completedCount}
                                    tone="emerald"
                                    isLoading={false}
                                    icon={<UserCheck className="w-5 h-5" />}
                                />
                                <TeamSummaryCard
                                    label="待辅导"
                                    value={summary.needsCoachingCount}
                                    tone="red"
                                    isLoading={false}
                                    icon={<AlertTriangle className="w-5 h-5" />}
                                />
                            </section>

                            {isError ? (
                                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-center justify-between gap-3">
                                    <span>部分数据加载失败：{errorMessage}可查看已加载内容或重试。</span>
                                    <button
                                        type="button"
                                        onClick={handleRetry}
                                        className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-bold text-amber-800 shadow-sm hover:bg-amber-100"
                                    >
                                        重试
                                    </button>
                                </div>
                            ) : null}

                            <section>
                                <div className="flex items-center justify-between mb-4 px-2">
                                    <h2 className="text-xl font-bold text-slate-900">
                                        学员列表
                                    </h2>
                                    <span className="text-xs text-slate-400">
                                        共 {learnerRows.length} 名学员
                                    </span>
                                </div>

                                {learnerRows.length === 0 ? (
                                    <TeamNoLearners />
                                ) : (
                                    <div className="space-y-3">
                                        {learnerRows.map((row) => (
                                            <LearnerRow key={row.learner_id} row={row} />
                                        ))}
                                    </div>
                                )}
                            </section>
                        </>
                    )}
                </>
            )}

            <div className="text-center text-xs text-slate-400 pt-4">
                仅展示本部门学员；如需跨部门查看，请联系管理员。
            </div>
        </div>
    );
}
