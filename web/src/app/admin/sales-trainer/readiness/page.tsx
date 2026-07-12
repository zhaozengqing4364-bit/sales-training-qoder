"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { AlertTriangle, CheckCircle2, ClipboardCheck, RefreshCw } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    ReadinessWorkbenchGroup,
    ReadinessWorkbenchGroupKey,
    ReadinessWorkbenchItem,
    ReadinessWorkbenchResponse,
} from "@/lib/api/types/training-journey";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

const GROUP_ORDER: ReadinessWorkbenchGroupKey[] = [
    "pending_review",
    "not_passed",
    "needs_retraining",
    "config_exception",
    "approved",
    "in_training",
];

function statusBadgeClass(status: string): string {
    if (status === "approved") {
        return "bg-emerald-50 text-emerald-700";
    }
    if (status === "blocked_by_config") {
        return "bg-red-50 text-red-700";
    }
    if (status === "needs_remediation" || status === "manual_follow_up") {
        return "bg-amber-50 text-amber-700";
    }
    if (status === "pending_review") {
        return "bg-blue-50 text-blue-700";
    }
    return "bg-slate-100 text-slate-700";
}

function metric(value: number | undefined): string {
    return typeof value === "number" ? String(value) : "--";
}

function learnerName(item: ReadinessWorkbenchItem): string {
    return item.learner.name || item.learner.learner_id;
}

function groupDescription(groupKey: ReadinessWorkbenchGroupKey): string {
    return {
        pending_review: "证据已齐，需要培训负责人给出达标结论。",
        not_passed: "AI 初评或人工判断显示暂不能进入下一阶段。",
        needs_retraining: "已要求重练，等待新人补交新的训练证据。",
        config_exception: "路径、材料、题目或评分配置阻塞了可信档案。",
        approved: "培训负责人已确认达标。",
        in_training: "新人仍在完成前置训练任务。",
    }[groupKey];
}

function readinessDisplayMessage(message: string | null | undefined): string {
    const rawMessage = String(message || "").trim();
    if (!rawMessage) {
        return "";
    }
    if (rawMessage.includes("runtime binding")) {
        return "真实语音对练后台接入配置缺失，请先处理训练路径配置。";
    }
    if (rawMessage.includes("provider readiness")) {
        return "真实语音服务检查未通过，下一阶段暂不开放。";
    }
    if (rawMessage.includes("active path revision")) {
        return "当前发布的训练路径配置需要处理。";
    }
    if (rawMessage.includes("target_unit_id")) {
        return "训练模块还没有绑定可练内容。";
    }
    if (
        rawMessage.includes("AI Coach") &&
        (rawMessage.includes("Prompt") || rawMessage.includes("配置非法"))
    ) {
        return "AI 补练教练缺少后台配置。";
    }
    return rawMessage
        .replace(/\s*\(trace_id:[^)]+\)/g, "")
        .replace(/\[[A-Z0-9_]+\]\s*/g, "")
        .replace(/TrainingJourney/g, "训练路径")
        .replace(/Journey/g, "训练路径")
        .replace(/active revision/g, "当前发布版本")
        .replace(/provider readiness/g, "语音服务检查")
        .replace(/runtime binding/g, "后台接入配置")
        .replace(/target_unit_id/g, "训练内容")
        .replace(/AI Coach/g, "AI 补练教练")
        .replace(/Prompt/g, "后台配置")
        .replace(/terminal/g, "需处理")
        .trim();
}

function WorkbenchCard({ item }: { item: ReadinessWorkbenchItem }) {
    const href = item.target_path || `/admin/sales-trainer/readiness/${item.learner.learner_id}`;
    return (
        <div className="border-b border-slate-100 px-5 py-4 last:border-b-0">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <Link
                            href={href}
                            className="font-semibold text-slate-900 hover:text-slate-700"
                        >
                            {learnerName(item)}
                        </Link>
                        <Badge className={statusBadgeClass(item.status)}>{item.status_label}</Badge>
                    </div>
                    <p className="text-sm text-slate-500">
                        {item.learner.department || "未记录部门"} · 证据 {item.evidence_count} 条
                    </p>
                    <p className="text-sm leading-6 text-slate-700">
                        {readinessDisplayMessage(item.status_reason)}
                    </p>
                    {item.weak_capability_labels.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                            {item.weak_capability_labels.map((label) => (
                                <span
                                    key={label}
                                    className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600"
                                >
                                    {label}
                                </span>
                            ))}
                        </div>
                    ) : null}
                </div>
                <Button asChild variant="outline" className="shrink-0">
                    <Link href={href}>
                        <ClipboardCheck className="mr-2 h-4 w-4" />
                        {item.next_action?.label || "查看档案"}
                    </Link>
                </Button>
            </div>
        </div>
    );
}

function WorkbenchGroupSection({ group }: { group: ReadinessWorkbenchGroup }) {
    return (
        <GlassCard className="overflow-hidden p-0">
            <div className="border-b border-slate-100 px-5 py-4">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h2 className="text-base font-bold text-slate-900">{group.label}</h2>
                        <p className="mt-1 text-sm text-slate-500">
                            {groupDescription(group.group_key)}
                        </p>
                    </div>
                    <Badge className="bg-slate-100 text-slate-700">{group.count}</Badge>
                </div>
            </div>
            {group.items.length > 0 ? (
                group.items.map((item) => (
                    <WorkbenchCard key={item.learner.learner_id} item={item} />
                ))
            ) : (
                <div className="px-5 py-8 text-sm text-slate-500">暂无待处理新人</div>
            )}
        </GlassCard>
    );
}

export default function SalesTrainerReadinessWorkbenchPage() {
    const pathname = usePathname();
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
    const { capabilities } = routeAccess;
    const [workbench, setWorkbench] = useState<ReadinessWorkbenchResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const loadWorkbench = useCallback(async () => {
        if (!routeAccess.canAccess) {
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            setWorkbench(await api.admin.salesTrainer.getReadinessWorkbench({ limit: 100 }));
        } catch (loadError) {
            setWorkbench(null);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [routeAccess.canAccess]);

    useEffect(() => {
        void loadWorkbench();
    }, [loadWorkbench]);

    const orderedGroups = useMemo(() => {
        if (!workbench) {
            return [];
        }
        return GROUP_ORDER.map((key) => workbench.groups[key]).filter(Boolean);
    }, [workbench]);

    const content = (() => {
        if (routeAccess.isLoading) {
            return (
                <GlassCard className="p-5 text-sm text-slate-500">
                    正在确认达标验收权限...
                </GlassCard>
            );
        }
        if (!routeAccess.canAccess) {
            return (
                <AdminLoadErrorCard
                    title="达标验收工作台不可访问"
                    description="当前账号没有查看训练档案和验收队列的权限，系统不会加载学员档案数据。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            );
        }
        if (error) {
            return (
                <AdminLoadErrorCard
                    title="达标验收工作台加载失败"
                    description="验收队列没有加载成功，已停止渲染空状态，避免把接口错误误判为暂无待复核新人。"
                    message={error}
                    retryLabel="重新加载"
                    onRetry={() => void loadWorkbench()}
                />
            );
        }
        if (isLoading && !workbench) {
            return (
                <GlassCard className="p-5 text-sm text-slate-500">
                    正在加载达标验收队列...
                </GlassCard>
            );
        }
        if (!workbench) {
            return null;
        }
        return (
            <>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">学员</p>
                        <p className="mt-2 text-2xl font-bold text-slate-900">
                            {metric(workbench.summary.loaded_learner_count)}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">待复核</p>
                        <p className="mt-2 text-2xl font-bold text-blue-700">
                            {metric(workbench.summary.pending_review_count)}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">未达标</p>
                        <p className="mt-2 text-2xl font-bold text-amber-700">
                            {metric(workbench.summary.not_passed_count)}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">需重练</p>
                        <p className="mt-2 text-2xl font-bold text-amber-700">
                            {metric(workbench.summary.needs_retraining_count)}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">配置异常</p>
                        <p className="mt-2 flex items-center gap-2 text-2xl font-bold text-red-700">
                            <AlertTriangle className="h-5 w-5" aria-hidden />
                            {metric(workbench.summary.config_exception_count)}
                        </p>
                    </GlassCard>
                    <GlassCard className="p-5">
                        <p className="text-sm text-slate-500">已达标</p>
                        <p className="mt-2 flex items-center gap-2 text-2xl font-bold text-emerald-700">
                            <CheckCircle2 className="h-5 w-5" aria-hidden />
                            {metric(workbench.summary.approved_count)}
                        </p>
                    </GlassCard>
                </div>

                {isLoading ? (
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                        <RefreshCw className="h-4 w-4 animate-spin" aria-hidden />
                        正在刷新验收队列...
                    </div>
                ) : null}

                <div className="grid gap-4 xl:grid-cols-2">
                    {orderedGroups.map((group) => (
                        <WorkbenchGroupSection key={group.group_key} group={group} />
                    ))}
                </div>
            </>
        );
    })();

    return (
        <AdminIndexShell
            header={
                <AdminPageHeader
                    title="达标验收工作台"
                    description="按待复核、未达标、需重练、已达标和配置异常组织新人训练档案。"
                    secondaryActions={
                        <SalesTrainerAdminModuleNav
                            currentPath={pathname}
                            capabilities={capabilities}
                        />
                    }
                    primaryAction={
                        routeAccess.canAccess ? (
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => void loadWorkbench()}
                            >
                                <RefreshCw className="mr-2 h-4 w-4" />
                                刷新
                            </Button>
                        ) : null
                    }
                />
            }
        >
            {content}
        </AdminIndexShell>
    );
}
