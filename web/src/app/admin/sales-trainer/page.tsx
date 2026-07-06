"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { AlertTriangle, TrendingUp } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import {
    SALES_TRAINER_ADMIN_WORKBENCH_LINKS,
    SalesTrainerAdminModuleNav,
    filterSalesTrainerAdminRouteItemsForCapabilities,
} from "@/components/admin/sales-trainer/module-nav";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerManagerDashboard,
} from "@/lib/api/types";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

function numberMetric(value: unknown): string {
    return typeof value === "number" ? String(value) : "--";
}

function rateMetric(value: unknown): string {
    return typeof value === "number" ? `${value.toFixed(1)}%` : "--";
}

function firstWeakDimension(dashboard: SalesTrainerManagerDashboard | null): string {
    const first = dashboard?.weak_dimensions[0];
    if (!first) {
        return "暂无集中弱项";
    }
    return String(first["dimension_label"] ?? first["dimension_key"] ?? "弱项维度");
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function requireDashboardArray(
    dashboard: SalesTrainerManagerDashboard,
    key: "module_summaries" | "weak_dimensions" | "risk_learners" | "intervention_suggestions",
) {
    if (!Array.isArray(dashboard[key])) {
        throw new Error(`管理看板响应缺少 ${key} 数组。`);
    }
}

function assertManagerDashboardContract(
    dashboard: SalesTrainerManagerDashboard,
): SalesTrainerManagerDashboard {
    if (!isRecord(dashboard.summary)) {
        throw new Error("管理看板响应缺少 summary。");
    }
    for (const key of ["record_count", "completion_rate", "pass_rate"]) {
        if (typeof dashboard.summary[key] !== "number") {
            throw new Error(`管理看板 summary.${key} 不是数字。`);
        }
    }
    if (!isRecord(dashboard.policy)) {
        throw new Error("管理看板响应缺少 policy。");
    }
    requireDashboardArray(dashboard, "module_summaries");
    requireDashboardArray(dashboard, "weak_dimensions");
    requireDashboardArray(dashboard, "risk_learners");
    requireDashboardArray(dashboard, "intervention_suggestions");
    return dashboard;
}

export default function SalesTrainerWorkbenchPage() {
    const pathname = usePathname();
    const [dashboard, setDashboard] = useState<SalesTrainerManagerDashboard | null>(null);
    const [dashboardError, setDashboardError] = useState<string | null>(null);
    const [dashboardReloadToken, setDashboardReloadToken] = useState(0);
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
    const { capabilities } = routeAccess;
    const riskLearners = dashboard?.risk_learners.slice(0, 5) ?? [];
    const weakDimensions = dashboard?.weak_dimensions.slice(0, 5) ?? [];
    const interventionSuggestions = dashboard?.intervention_suggestions.slice(0, 5) ?? [];
    const workbenchLinks = filterSalesTrainerAdminRouteItemsForCapabilities(
        SALES_TRAINER_ADMIN_WORKBENCH_LINKS,
        capabilities,
    );

    useEffect(() => {
        if (!routeAccess.canAccess) {
            return;
        }
        let isCurrent = true;
        async function loadDashboard() {
            try {
                const result = await api.admin.salesTrainer.getManagerDashboard();
                if (!isCurrent) return;
                setDashboard(assertManagerDashboardContract(result));
                setDashboardError(null);
            } catch (error) {
                if (!isCurrent) return;
                setDashboard(null);
                setDashboardError(getApiErrorMessage(error));
            }
        }
        void loadDashboard();
        return () => {
            isCurrent = false;
        };
    }, [dashboardReloadToken, routeAccess.canAccess]);

    function retryDashboard() {
        setDashboardError(null);
        setDashboardReloadToken((current) => current + 1);
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径工作台"
                    description="新人训练路径的模块、文章、考卷、录音评分、配置健康和操作记录集中在这里管理。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={capabilities} />}
                />
            )}
        >
            {routeAccess.isLoading ? (
                <GlassCard className="p-5 text-sm text-slate-500">
                    正在确认新人训练管理权限...
                </GlassCard>
            ) : null}
            {!routeAccess.isLoading && !routeAccess.canAccess ? (
                <AdminLoadErrorCard
                    title="新人训练工作台不可访问"
                    description="当前账号没有进入新人训练工作台的权限，系统不会加载管理看板数据。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : null}
            {routeAccess.canAccess && dashboardError ? (
                <AdminLoadErrorCard
                    title="新人训练看板加载失败"
                    description="管理看板数据未加载成功，已停止渲染指标和风险学员空态，避免把接口错误误判为暂无数据。"
                    message={dashboardError}
                    onRetry={retryDashboard}
                />
            ) : null}

            {routeAccess.canAccess && !dashboardError ? (
            <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-500">训练记录</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                        {numberMetric(dashboard?.summary["record_count"])}
                    </p>
                </GlassCard>
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-500">完成率</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                        {rateMetric(dashboard?.summary["completion_rate"])}
                    </p>
                </GlassCard>
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-500">通过率</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900">
                        {rateMetric(dashboard?.summary["pass_rate"])}
                    </p>
                </GlassCard>
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-500">风险学员</p>
                    <p className="mt-2 flex items-center gap-2 text-2xl font-bold text-slate-900">
                        <AlertTriangle className="h-5 w-5 text-amber-500" />
                        {numberMetric(dashboard?.risk_learners.length)}
                    </p>
                </GlassCard>
                <GlassCard className="p-5">
                    <p className="text-sm text-slate-500">集中弱项</p>
                    <p className="mt-2 flex items-center gap-2 text-base font-semibold text-slate-900">
                        <TrendingUp className="h-5 w-5 text-slate-500" />
                        {firstWeakDimension(dashboard)}
                    </p>
                </GlassCard>
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
                <GlassCard className="space-y-4 p-5">
                    <div>
                        <h2 className="text-base font-bold text-slate-900">风险学员</h2>
                        <p className="text-sm text-slate-500">低分、未通过或多次重练的学员。</p>
                    </div>
                    <div className="space-y-3">
                        {riskLearners.length > 0 ? riskLearners.map((learner) => (
                            <div key={learner.user_id} className="rounded-lg border border-slate-100 p-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="font-medium text-slate-900">
                                            {learner.user_name || learner.user_id}
                                        </p>
                                        <p className="mt-1 text-xs text-slate-500">
                                            最低分 {learner.lowest_score ?? "--"} · 记录 {learner.record_count}
                                        </p>
                                    </div>
                                    <Badge className="bg-amber-50 text-amber-700">
                                        {learner.suggested_action || "查看训练记录"}
                                    </Badge>
                                </div>
                            </div>
                        )) : (
                            <p className="text-sm text-slate-500">暂无风险学员</p>
                        )}
                    </div>
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                    <div>
                        <h2 className="text-base font-bold text-slate-900">模块弱项</h2>
                        <p className="text-sm text-slate-500">按评分维度聚合的团队薄弱点。</p>
                    </div>
                    <div className="space-y-3">
                        {weakDimensions.length > 0 ? weakDimensions.map((dimension) => (
                            <div key={dimension.dimension_key} className="rounded-lg border border-slate-100 p-3">
                                <p className="font-medium text-slate-900">
                                    {dimension.dimension_label || dimension.dimension_key}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    记录 {dimension.record_count} · 学员 {dimension.learner_count} · 均分 {dimension.average_score ?? "--"}
                                </p>
                            </div>
                        )) : (
                            <p className="text-sm text-slate-500">暂无集中弱项</p>
                        )}
                    </div>
                </GlassCard>

                <GlassCard className="space-y-4 p-5">
                    <div>
                        <h2 className="text-base font-bold text-slate-900">干预建议</h2>
                        <p className="text-sm text-slate-500">把看板风险转成主管下一步动作。</p>
                    </div>
                    <div className="space-y-3">
                        {interventionSuggestions.length > 0 ? interventionSuggestions.map((suggestion) => (
                            <div key={suggestion.user_id} className="rounded-lg border border-slate-100 p-3">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="font-medium text-slate-900">
                                            {suggestion.user_name || suggestion.user_id}
                                        </p>
                                        <p className="mt-1 text-xs text-slate-500">
                                            {suggestion.action || "查看训练记录"}
                                        </p>
                                    </div>
                                    <Badge className="bg-slate-100 text-slate-700">
                                        {suggestion.priority}
                                    </Badge>
                                </div>
                            </div>
                        )) : (
                            <p className="text-sm text-slate-500">暂无干预建议</p>
                        )}
                    </div>
                </GlassCard>
            </div>
            </>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {routeAccess.canAccess ? workbenchLinks.map((item) => {
                    const Icon = item.icon;
                    return (
                        <Link key={item.href} href={item.href}>
                            <GlassCard className="flex items-center gap-4 p-5 transition hover:border-slate-300 hover:bg-white">
                                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                                    <Icon className="h-5 w-5" />
                                </span>
                                <span className="font-semibold text-slate-900">{item.label}</span>
                            </GlassCard>
                        </Link>
                    );
                }) : null}
                {!routeAccess.error && !routeAccess.isLoading && routeAccess.canAccess && workbenchLinks.length === 0 ? (
                    <GlassCard className="p-5 text-sm text-slate-500">
                        当前账号没有可进入的新人训练管理入口。
                    </GlassCard>
                ) : null}
            </div>
        </AdminIndexShell>
    );
}
