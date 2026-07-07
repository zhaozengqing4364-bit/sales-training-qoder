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
    Circle,
    Loader2,
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
    TrainingJourneyModuleKind,
    TrainingJourneyModuleProgress,
    TrainingJourneyResponse,
} from "@/lib/api/types";
import {
    getStageLabel,
    formatRiskReasons,
    buildModuleKeyToTitleMapFromJourney,
    detectJourneyRiskModules,
} from "@/lib/team-journey/view-models";
import { cn } from "@/lib/utils";

/**
 * 单个 part 的展示状态（DTO → ViewModel 映射）。
 * 不直接暴露后端 stage/status 原始枚举，只保留 5 种用户可理解的状态。
 *
 * 判定优先级（与关卡整体状态判定一致）：
 *   locked > failed > in_progress > not_started > passed
 *   其中 passed 是兜底：passed=true 视为已通过；passed=null + 非失败/进行中 视为未开始。
 */
type PartStatus = "passed" | "failed" | "in_progress" | "not_started" | "locked";

/**
 * 关卡整体状态：取该关所有 part 里最需关注的状态。
 * 优先级：failed > in_progress > not_started > passed（locked 归入 not_started 一起算"未开始"）。
 */
type StageStatus = "passed" | "failed" | "in_progress" | "not_started";

const PART_STATUS_LABEL: Record<PartStatus, string> = {
    passed: "已通过",
    failed: "未通过",
    in_progress: "进行中",
    not_started: "未开始",
    locked: "未解锁",
};

const STAGE_STATUS_LABEL: Record<StageStatus, string> = {
    passed: "已通过",
    failed: "需关注",
    in_progress: "进行中",
    not_started: "未开始",
};

interface PartViewModel {
    /** 唯一 React key：同关内 kind 唯一，跨关用 order_index 区分 */
    react_key: string;
    /** part 标题：文章做题 / AI 教练 / 音频提交 / 实时对练 */
    part_title: string;
    status: PartStatus;
    score_label: string;
    next_action_label: string;
    is_risk: boolean;
}

interface StageGroupViewModel {
    /** 唯一 React key：order_index 在 journey 内唯一 */
    react_key: string;
    /** 第 N 关：order_index + 1（0-based → 1-based，兜底用 1） */
    stage_number: number;
    /** 关卡标题：取该关第一个 part 的 title/display_name（同关共享标题） */
    stage_title: string;
    /** 关卡整体状态 */
    status: StageStatus;
    /** 关卡下一步：取该关最靠前未完成 part 的 next_action.label */
    next_action_label: string;
    /** 关卡内所有 part */
    parts: PartViewModel[];
}

/**
 * 后端 kind 工程 key → part 中文标签（不进 UI 文本前先兜底）。
 * 优先用 module.title/display_name（受治理的运营文案），kind 只在 title 缺失时兜底。
 *
 * 注意：同关的两个 part 共享 title（如"第2关：商务技巧"），所以 part 标题用 kind 区分
 * 做题/AI 教练，而不是重复显示关卡标题。
 */
function getPartTitleFromKind(kind: TrainingJourneyModuleKind | string | undefined): string {
    switch (kind) {
        case "quiz_attempt":
            return "文章做题";
        case "ai_coach":
            return "AI 教练";
        case "audio_submission":
            return "音频提交";
        case "realtime_roleplay":
            return "实时对练";
        default:
            return "训练模块";
    }
}

/**
 * 从原始 module 判定单个 part 的展示状态。
 *
 * 判定规则（与后端 stage 语义对齐，但映射到 5 种用户状态）：
 * - locked === true → locked（未解锁，不显示成绩）
 * - passed === true → passed
 * - passed === false → failed（含 needs_remediation/manual_review/error_terminal 等风险态）
 * - passed === null/undefined：
 *   - stage ∈ {in_progress, processing, waiting_upload} → in_progress
 *   - stage === not_started → not_started
 *   - stage ∈ {scored} → passed（已评分但 passed 未回填，视为已通过兜底）
 *   - 其他 → not_started（兜底，不泄露工程态）
 */
function determinePartStatus(journeyModule: TrainingJourneyModuleProgress): PartStatus {
    if (journeyModule.locked === true) {
        return "locked";
    }
    if (journeyModule.passed === true) {
        return "passed";
    }
    if (journeyModule.passed === false) {
        return "failed";
    }
    // passed === null/undefined：按 stage 推断
    const stage = journeyModule.stage ?? journeyModule.status;
    if (stage === "in_progress" || stage === "processing" || stage === "waiting_upload") {
        return "in_progress";
    }
    if (stage === "scored" || stage === "passed") {
        return "passed";
    }
    return "not_started";
}

/**
 * 判定单个 part 是否为待辅导（与 view-models.ts 的 detectJourneyRiskModules 语义一致，
 * 但按 part 独立判定，避免 module_key 重复时误标同关其他 part）。
 */
function isPartAtRisk(journeyModule: TrainingJourneyModuleProgress): boolean {
    if (journeyModule.passed === false) {
        return true;
    }
    const status = journeyModule.status;
    const RISK_STATUSES: ReadonlySet<string> = new Set([
        "failed",
        "needs_remediation",
        "manual_review",
        "error_terminal",
        "error_transient",
    ]);
    return typeof status === "string" && RISK_STATUSES.has(status);
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

/**
 * 把单条原始 module 映射为 part ViewModel。
 * 不携带任何工程字段（module_key/kind/order_index 不进 UI 文本）。
 */
function mapModuleToPartViewModel(journeyModule: TrainingJourneyModuleProgress): PartViewModel {
    const kind = journeyModule.kind ?? journeyModule.module_type;
    const partTitle = getPartTitleFromKind(kind);
    const status = determinePartStatus(journeyModule);
    const nextActionLabel = journeyModule.next_action?.label?.trim() || "无待办";
    // locked 不展示成绩
    const scoreLabel = status === "locked" ? "—" : formatScore(journeyModule.score, journeyModule.max_score);

    return {
        // 同关内 kind 唯一，跨关用 order_index 区分 → 全局唯一
        react_key: `${journeyModule.order_index ?? 0}-${kind}`,
        part_title: partTitle,
        status,
        score_label: scoreLabel,
        next_action_label: nextActionLabel,
        is_risk: isPartAtRisk(journeyModule),
    };
}

const PART_STATUS_PRIORITY: Record<PartStatus, number> = {
    failed: 0,
    in_progress: 1,
    locked: 2,
    not_started: 2,
    passed: 3,
};

const STAGE_STATUS_PRIORITY: Record<StageStatus, number> = {
    failed: 0,
    in_progress: 1,
    not_started: 2,
    passed: 3,
};

/**
 * 从该关所有 part 的状态推导关卡整体状态。
 * 取最需关注的（priority 最小）。
 */
function determineStageStatus(partStatuses: PartStatus[]): StageStatus {
    if (partStatuses.length === 0) {
        return "not_started";
    }
    let minPriority = Infinity;
    let result: StageStatus = "passed";
    for (const ps of partStatuses) {
        // locked 归入 not_started 一起算关卡"未开始"
        const stageStatus: StageStatus = ps === "locked" ? "not_started" : ps === "passed" ? "passed" : ps;
        const priority = STAGE_STATUS_PRIORITY[stageStatus];
        if (priority < minPriority) {
            minPriority = priority;
            result = stageStatus;
        }
    }
    return result;
}

/**
 * 取该关下一步：优先级 failed > in_progress > not_started/locked > passed。
 * 取最靠前未完成 part 的 next_action.label；若全部已通过，取第一个 part 的（通常是"查看详情"）。
 */
function pickStageNextActionLabel(parts: PartViewModel[]): string {
    if (parts.length === 0) {
        return "无待办";
    }
    const sorted = parts.slice().sort(
        (a, b) => PART_STATUS_PRIORITY[a.status] - PART_STATUS_PRIORITY[b.status],
    );
    return sorted[0].next_action_label || "无待办";
}

/**
 * 把 journey.modules 按 order_index 分组为关卡列表。
 *
 * 分组规则：
 * - 同 order_index 的 module 归到同一关（如 order=2 下 quiz_attempt + ai_coach 共享第2关）
 * - 关卡标题取该关第一个 module 的 title/display_name（同关共享标题）
 * - 关卡编号 = order_index + 1（0-based → 1-based）
 *
 * 输入已按 order_index 升序排列的 modules。
 */
function groupModulesByStage(modules: TrainingJourneyModuleProgress[]): StageGroupViewModel[] {
    const groups: StageGroupViewModel[] = [];
    const groupMap = new Map<number, TrainingJourneyModuleProgress[]>();

    for (const journeyModule of modules) {
        const order = journeyModule.order_index ?? 0;
        const arr = groupMap.get(order);
        if (arr) {
            arr.push(journeyModule);
        } else {
            groupMap.set(order, [journeyModule]);
        }
    }

    // order_index 升序
    const sortedOrders = Array.from(groupMap.keys()).sort((a, b) => a - b);

    for (const order of sortedOrders) {
        const stageModules = groupMap.get(order) ?? [];
        const parts = stageModules
            .slice()
            .sort((a, b) => {
                // 同关内按 kind 字母序稳定排序，避免随机
                const ka = a.kind ?? a.module_type ?? "";
                const kb = b.kind ?? b.module_type ?? "";
                return ka.localeCompare(kb);
            })
            .map(mapModuleToPartViewModel);

        const partStatuses = parts.map((p) => p.status);
        const stageStatus = determineStageStatus(partStatuses);
        const nextAction = pickStageNextActionLabel(parts);

        // 关卡标题：同关共享，取第一个 module 的 title/display_name
        const firstModule = stageModules[0];
        const stageTitle =
            firstModule.display_name?.trim()
            || firstModule.title?.trim()
            || "未命名关卡";

        groups.push({
            react_key: `stage-${order}`,
            stage_number: order + 1,
            stage_title: stageTitle,
            status: stageStatus,
            next_action_label: nextAction,
            parts,
        });
    }

    return groups;
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

/** part 状态 → 图标 + 颜色 class */
function getPartStatusIcon(status: PartStatus): {
    icon: React.ReactNode;
    iconColor: string;
    borderColor: string;
} {
    switch (status) {
        case "passed":
            return {
                icon: <CheckCircle2 className="w-5 h-5" />,
                iconColor: "text-emerald-500",
                borderColor: "border-l-emerald-400",
            };
        case "failed":
            return {
                icon: <XCircle className="w-5 h-5" />,
                iconColor: "text-red-500",
                borderColor: "border-l-red-400",
            };
        case "in_progress":
            return {
                icon: <Loader2 className="w-5 h-5 animate-spin" />,
                iconColor: "text-blue-500",
                borderColor: "border-l-blue-400",
            };
        case "locked":
            return {
                icon: <Lock className="w-5 h-5" />,
                iconColor: "text-slate-400",
                borderColor: "border-l-slate-300",
            };
        case "not_started":
        default:
            return {
                icon: <Circle className="w-5 h-5" />,
                iconColor: "text-slate-400",
                borderColor: "border-l-slate-300",
            };
    }
}

/** 关卡整体状态 → 图标 + 颜色 class */
function getStageStatusIcon(status: StageStatus): {
    icon: React.ReactNode;
    iconColor: string;
    badgeVariant: "green" | "red" | "blue" | "gray";
    cardAccent: string;
} {
    switch (status) {
        case "passed":
            return {
                icon: <CheckCircle2 className="w-5 h-5" />,
                iconColor: "text-emerald-500",
                badgeVariant: "green",
                cardAccent: "border-white/60",
            };
        case "failed":
            return {
                icon: <AlertTriangle className="w-5 h-5" />,
                iconColor: "text-red-500",
                badgeVariant: "red",
                cardAccent: "border-red-200/80 bg-red-50/30",
            };
        case "in_progress":
            return {
                icon: <Loader2 className="w-5 h-5 animate-spin" />,
                iconColor: "text-blue-500",
                badgeVariant: "blue",
                cardAccent: "border-blue-200/80 bg-blue-50/30",
            };
        case "not_started":
        default:
            return {
                icon: <Circle className="w-5 h-5" />,
                iconColor: "text-slate-400",
                badgeVariant: "gray",
                cardAccent: "border-white/60",
            };
    }
}

function PartRow({ part }: { part: PartViewModel }) {
    const { icon, iconColor, borderColor } = getPartStatusIcon(part.status);
    return (
        <div
            data-testid="part-row"
            data-part-status={part.status}
            className={cn("flex items-center gap-3 rounded-xl border border-l-4 bg-white/50 px-4 py-3", borderColor)}
        >
            <span className={cn("shrink-0", iconColor)} aria-hidden="true">
                {icon}
            </span>
            <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-slate-900 truncate">{part.part_title}</span>
                    <span
                        className={cn(
                            "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
                            part.status === "passed" && "bg-emerald-50 text-emerald-700",
                            part.status === "failed" && "bg-red-50 text-red-700",
                            part.status === "in_progress" && "bg-blue-50 text-blue-700",
                            (part.status === "not_started" || part.status === "locked") && "bg-slate-100 text-slate-500",
                        )}
                    >
                        {PART_STATUS_LABEL[part.status]}
                    </span>
                    {part.is_risk && part.status === "failed" ? (
                        <Badge variant="red" className="shrink-0">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            需关注
                        </Badge>
                    ) : null}
                </div>
                <p className="text-xs text-slate-500 mt-1">下一步：{part.next_action_label}</p>
            </div>
            <div className="shrink-0 text-right">
                <span className="text-xs text-slate-400 block">成绩</span>
                <span className="font-bold text-slate-900 text-sm">{part.score_label}</span>
            </div>
        </div>
    );
}

function StageGroupCard({ group }: { group: StageGroupViewModel }) {
    const { icon, iconColor, badgeVariant, cardAccent } = getStageStatusIcon(group.status);
    return (
        <GlassCard
            data-testid="stage-group"
            data-stage-status={group.status}
            data-stage-number={group.stage_number}
            className={cn("p-5 border", cardAccent)}
        >
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                    <span className={cn("shrink-0", iconColor)} aria-hidden="true">
                        {icon}
                    </span>
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-bold text-slate-900 truncate">
                                第{group.stage_number}关 · {group.stage_title}
                            </h3>
                            <Badge variant={badgeVariant} className="shrink-0">
                                {STAGE_STATUS_LABEL[group.status]}
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">下一步：{group.next_action_label}</p>
                    </div>
                </div>
            </div>
            <div className="mt-4 space-y-2">
                {group.parts.map((part) => (
                    <PartRow key={part.react_key} part={part} />
                ))}
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

    const stageGroups = useMemo<StageGroupViewModel[]>(() => {
        const journey = detail.journey;
        if (!journey) {
            return [];
        }
        const modules = (journey.modules ?? [])
            .slice()
            .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0));
        return groupModulesByStage(modules);
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

    const totalParts = stageGroups.reduce((sum, g) => sum + g.parts.length, 0);

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
                                共 {stageGroups.length} 个关卡 · {totalParts} 个训练项
                            </span>
                        </div>

                        {stageGroups.length === 0 ? (
                            <EmptyState
                                title="暂无模块记录"
                                description="该学员的训练路径尚未配置模块，或模块数据仍在生成中。"
                                icon={<Lock className="w-10 h-10 text-slate-300" />}
                            />
                        ) : (
                            <div className="space-y-4">
                                {stageGroups.map((group) => (
                                    <StageGroupCard key={group.react_key} group={group} />
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
