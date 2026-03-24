"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Activity, RefreshCcw, ShieldAlert, ShieldCheck } from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuthProtection } from "@/hooks/use-auth-protection";
import { cn } from "@/lib/utils";
import type {
    SupportRuntimeFaultItem,
    SupportRuntimeFaultSeverity,
    SupportRuntimeOverview,
    SupportRuntimeReleaseHealthStatus,
} from "@/lib/api/types";

function formatDateTime(value: string | null): string {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("zh-CN", { hour12: false });
}

function formatDiagnosticValue(value: unknown): string | null {
    if (value === null || value === undefined || value === "") {
        return null;
    }
    if (Array.isArray(value)) {
        return value.map((entry) => String(entry)).join(", ");
    }
    if (typeof value === "object") {
        return JSON.stringify(value);
    }
    return String(value);
}

function formatDiagnosticEntries(diagnostics: Record<string, unknown>): string[] {
    return Object.entries(diagnostics)
        .map(([key, value]) => {
            const formatted = formatDiagnosticValue(value);
            return formatted ? `${key}: ${formatted}` : null;
        })
        .filter((entry): entry is string => Boolean(entry));
}

function formatAnomalySummary(items: Array<{ kind: string; count: number }>): string {
    if (!items.length) {
        return "无";
    }
    return items.map((item) => `${item.kind} ×${item.count}`).join("，");
}

function releaseStatusMeta(status: SupportRuntimeReleaseHealthStatus | null) {
    switch (status) {
        case "blocking":
            return {
                label: "阻塞发布",
                tone: "blocking" as const,
                description: "存在 blocking anomaly，当前不适合直接给团队发。",
            };
        case "warning":
            return {
                label: "仅警告",
                tone: "warning" as const,
                description: "当前没有 blocking，但仍有 warning 需要跟进。",
            };
        case "healthy":
            return {
                label: "健康",
                tone: "healthy" as const,
                description: "当前 typed anomaly 读面未发现阻塞或警告。",
            };
        default:
            return {
                label: "-",
                tone: "neutral" as const,
                description: "发布健康摘要暂不可用。",
            };
    }
}

function severityBadgeClass(severity: SupportRuntimeFaultSeverity): string {
    if (severity === "blocking") {
        return "border-red-200 bg-red-50 text-red-700";
    }
    return "border-amber-200 bg-amber-50 text-amber-700";
}

function toneCardClass(tone: "blocking" | "warning" | "healthy" | "neutral"): string {
    if (tone === "blocking") {
        return "border-red-200 bg-red-50/70";
    }
    if (tone === "warning") {
        return "border-amber-200 bg-amber-50/70";
    }
    if (tone === "healthy") {
        return "border-emerald-200 bg-emerald-50/70";
    }
    return "border-slate-200 bg-white";
}

function SummaryCard({
    title,
    value,
    description,
    detail,
    tone = "neutral",
    icon,
}: {
    title: string;
    value: string;
    description: string;
    detail?: string;
    tone?: "blocking" | "warning" | "healthy" | "neutral";
    icon: ReactNode;
}) {
    return (
        <article className={cn("rounded-2xl border p-5 shadow-sm", toneCardClass(tone))}>
            <div className="flex items-center gap-2 text-sm text-slate-600">
                {icon}
                <span>{title}</span>
            </div>
            <div className="mt-3 text-2xl font-black text-slate-900 tabular-nums">{value}</div>
            <p className="mt-2 text-sm text-slate-600 text-pretty">{description}</p>
            {detail ? <p className="mt-2 text-xs text-slate-500 text-pretty">{detail}</p> : null}
        </article>
    );
}

function SummarySkeletonGrid() {
    return (
        <section className="grid grid-cols-1 gap-4 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="mt-3 h-8 w-32" />
                    <Skeleton className="mt-3 h-4 w-full" />
                    <Skeleton className="mt-2 h-4 w-2/3" />
                </div>
            ))}
        </section>
    );
}

function FaultListSkeleton() {
    return (
        <div className="space-y-3 px-5 py-5">
            {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="rounded-2xl border border-slate-100 bg-slate-50/60 p-4">
                    <Skeleton className="h-5 w-40" />
                    <Skeleton className="mt-3 h-4 w-full" />
                    <Skeleton className="mt-2 h-4 w-2/3" />
                </div>
            ))}
        </div>
    );
}

export default function SupportRuntimeStatusPage() {
    const { isLoading: authLoading, isAuthorized } = useAuthProtection({ requiredRoles: ["support", "admin"] });
    const [overviewLoading, setOverviewLoading] = useState(true);
    const [faultsLoading, setFaultsLoading] = useState(true);
    const [overviewError, setOverviewError] = useState<string | null>(null);
    const [faultsError, setFaultsError] = useState<string | null>(null);
    const [overview, setOverview] = useState<SupportRuntimeOverview | null>(null);
    const [faults, setFaults] = useState<SupportRuntimeFaultItem[]>([]);

    const refreshing = overviewLoading || faultsLoading;
    const releaseMeta = releaseStatusMeta(overview?.release_health.status ?? null);

    const loadData = async () => {
        setOverviewLoading(true);
        setFaultsLoading(true);
        setOverviewError(null);
        setFaultsError(null);

        const [overviewResult, faultsResult] = await Promise.allSettled([
            api.supportRuntime.getOverview({ window_hours: 24 }),
            api.supportRuntime.getFaults({ limit: 20 }),
        ]);

        if (overviewResult.status === "fulfilled") {
            setOverview(overviewResult.value);
        } else {
            setOverviewError(getApiErrorMessage(overviewResult.reason));
        }
        setOverviewLoading(false);

        if (faultsResult.status === "fulfilled") {
            setFaults(faultsResult.value.items || []);
        } else {
            setFaultsError(getApiErrorMessage(faultsResult.reason));
        }
        setFaultsLoading(false);
    };

    useEffect(() => {
        if (!authLoading && isAuthorized) {
            void loadData();
        }
    }, [authLoading, isAuthorized]);

    if (authLoading || !isAuthorized) {
        return (
            <div className="flex min-h-[40vh] items-center justify-center text-slate-500">
                权限验证中...
            </div>
        );
    }

    return (
        <div className="space-y-6 pb-16">
            <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900 text-balance">发布健康（只读）</h1>
                    <p className="mt-1 text-pretty text-slate-500">
                        support/admin 直接看 blocking / warning 与会话级异常，不提供 learner report 入口。
                    </p>
                </div>
                <Button
                    variant="outline"
                    className="rounded-full border-slate-200"
                    onClick={() => void loadData()}
                    disabled={refreshing}
                >
                    <RefreshCcw className="mr-2 h-4 w-4" />
                    刷新
                </Button>
            </header>

            {overviewError ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 text-pretty">
                    发布健康摘要加载失败：{overviewError}
                </div>
            ) : null}

            {!overview && overviewLoading ? (
                <SummarySkeletonGrid />
            ) : (
                <section className="grid grid-cols-1 gap-4 xl:grid-cols-4">
                    <SummaryCard
                        title="发布状态"
                        value={releaseMeta.label}
                        description={releaseMeta.description}
                        detail={overview
                            ? `最近 ${overview.window_hours}h 共识别 ${overview.release_health.typed_anomaly_count} 条 typed anomaly · ${formatDateTime(overview.generated_at)}`
                            : "发布健康摘要暂不可用。"}
                        tone={releaseMeta.tone}
                        icon={releaseMeta.tone === "healthy"
                            ? <ShieldCheck className="h-4 w-4" />
                            : releaseMeta.tone === "blocking"
                                ? <ShieldAlert className="h-4 w-4" />
                                : <AlertTriangle className="h-4 w-4" />}
                    />
                    <SummaryCard
                        title="进行中 / scoring"
                        value={overview
                            ? `进行中 ${overview.session_health.active_sessions} · scoring ${overview.session_health.scoring_sessions}`
                            : "-"}
                        description={overview
                            ? `最近 ${overview.window_hours}h 启动 ${overview.session_health.total_sessions_window} 个会话，完成 ${overview.session_health.completed_sessions_window} 个。`
                            : "会话窗口摘要暂不可用。"}
                        detail={overview
                            ? `stuck ${overview.session_health.stuck_scoring_sessions} · not_evaluable ${overview.session_health.not_evaluable_completed_sessions_window} · completion ${overview.session_health.completion_rate}%`
                            : undefined}
                        icon={<Activity className="h-4 w-4" />}
                    />
                    <SummaryCard
                        title="Blocking"
                        value={overview ? String(overview.release_health.blocking_count) : "-"}
                        description={overview
                            ? `${overview.release_health.blocking_count} 个阻塞异常，影响 ${overview.release_health.blocking_sessions_count} 个会话`
                            : "阻塞摘要暂不可用。"}
                        detail={overview ? formatAnomalySummary(overview.anomaly_summary.blocking) : undefined}
                        tone={overview?.release_health.blocking_count ? "blocking" : "neutral"}
                        icon={<ShieldAlert className="h-4 w-4" />}
                    />
                    <SummaryCard
                        title="Warning"
                        value={overview ? String(overview.release_health.warning_count) : "-"}
                        description={overview
                            ? `${overview.release_health.warning_count} 个 warning 异常，影响 ${overview.release_health.warning_sessions_count} 个会话`
                            : "警告摘要暂不可用。"}
                        detail={overview
                            ? `${formatAnomalySummary(overview.anomaly_summary.warning)}${overview.release_health.supplemental_warning_log_count ? ` · supplemental logs ${overview.release_health.supplemental_warning_log_count}` : ""}`
                            : undefined}
                        tone={overview?.release_health.warning_count ? "warning" : "neutral"}
                        icon={<AlertTriangle className="h-4 w-4" />}
                    />
                </section>
            )}

            <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
                    <div>
                        <h2 className="font-bold text-slate-900">最近需要处理的异常</h2>
                        <p className="mt-1 text-xs text-slate-500 text-pretty">
                            直接展示 typed severity / kind / session / scenario / detected_at，不再回退到 raw log count。
                        </p>
                    </div>
                    <Badge
                        variant="secondary"
                        className={cn(
                            "border px-3 py-1 text-xs",
                            releaseMeta.tone === "blocking"
                                ? "border-red-200 bg-red-50 text-red-700"
                                : releaseMeta.tone === "warning"
                                    ? "border-amber-200 bg-amber-50 text-amber-700"
                                    : "border-emerald-200 bg-emerald-50 text-emerald-700",
                        )}
                    >
                        {releaseMeta.label}
                    </Badge>
                </div>

                {faultsError ? (
                    <div className="border-b border-red-100 bg-red-50 px-5 py-3 text-sm text-red-700 text-pretty">
                        异常列表加载失败：{faultsError}
                    </div>
                ) : null}

                {!faults.length && faultsLoading ? <FaultListSkeleton /> : null}

                {!faults.length && !faultsLoading && !faultsError ? (
                    <div className="px-5 py-8">
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-600 text-pretty">
                            最近没有需要处理的 blocking / warning 异常。
                            <div className="mt-2 text-xs text-slate-500">
                                可继续观察上方发布状态卡片，必要时点击顶部“刷新”。
                            </div>
                        </div>
                    </div>
                ) : null}

                {faults.length ? (
                    <ul className="divide-y divide-slate-100">
                        {faults.map((item, index) => {
                            const diagnostics = formatDiagnosticEntries(item.diagnostics || {});
                            const rowKey = `${item.kind}-${item.session_id ?? item.detected_at ?? index}`;

                            return (
                                <li key={rowKey} className="px-5 py-4">
                                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                        <div className="min-w-0 space-y-2">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <Badge variant="secondary" className={cn("border", severityBadgeClass(item.severity))}>
                                                    {item.severity}
                                                </Badge>
                                                <code className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                                                    {item.kind}
                                                </code>
                                                <span className="text-xs text-slate-500">
                                                    {formatDateTime(item.detected_at)}
                                                </span>
                                            </div>

                                            <p className="text-sm font-medium text-slate-900 text-pretty">{item.summary}</p>

                                            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                                                {item.session_id ? (
                                                    <span className="font-medium text-slate-700">{item.session_id}</span>
                                                ) : null}
                                                <span>
                                                    {(item.scenario_type ?? "-")} · {(item.session_status ?? "-")} · {(item.report_status ?? "-")}
                                                </span>
                                                <span>source: {item.source}</span>
                                            </div>

                                            {diagnostics.length ? (
                                                <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                                                    {diagnostics.map((entry) => (
                                                        <span
                                                            key={entry}
                                                            className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 tabular-nums"
                                                        >
                                                            {entry}
                                                        </span>
                                                    ))}
                                                </div>
                                            ) : null}
                                        </div>
                                    </div>
                                </li>
                            );
                        })}
                    </ul>
                ) : null}
            </section>
        </div>
    );
}
