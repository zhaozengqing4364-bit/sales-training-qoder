"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Activity, ShieldCheck, RefreshCcw } from "lucide-react";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuthProtection } from "@/hooks/use-auth-protection";
import type { SupportRuntimeFaultItem, SupportRuntimeOverview } from "@/lib/api/types";

function formatDateTime(value: string | null): string {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("zh-CN", { hour12: false });
}

export default function SupportRuntimeStatusPage() {
    const { isLoading: authLoading, isAuthorized } = useAuthProtection({ requiredRoles: ["support", "admin"] });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [overview, setOverview] = useState<SupportRuntimeOverview | null>(null);
    const [faults, setFaults] = useState<SupportRuntimeFaultItem[]>([]);

    const failedOrWarningFaults = useMemo(
        () => faults.filter((item) => item.status === "failed" || item.status === "warning"),
        [faults],
    );

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [overviewData, faultsData] = await Promise.all([
                api.supportRuntime.getOverview({ window_hours: 24 }),
                api.supportRuntime.getFaults({ limit: 20 }),
            ]);
            setOverview(overviewData);
            setFaults(faultsData.items || []);
        } catch (err) {
            const nextError = err instanceof Error ? err.message : "运行状态加载失败";
            setError(nextError);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (!authLoading && isAuthorized) {
            loadData();
        }
    }, [authLoading, isAuthorized]);

    if (authLoading || !isAuthorized) {
        return (
            <div className="min-h-[40vh] flex items-center justify-center text-slate-500">
                权限验证中...
            </div>
        );
    }

    return (
        <div className="space-y-6 pb-16">
            <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">运行状态（只读）</h1>
                    <p className="text-slate-500 mt-1">支持角色可查看健康与故障摘要，不提供策略改动能力。</p>
                </div>
                <Button
                    variant="outline"
                    className="rounded-full border-slate-200"
                    onClick={loadData}
                    disabled={loading}
                >
                    <RefreshCcw className="w-4 h-4 mr-2" />
                    刷新
                </Button>
            </header>

            {error && (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-600 text-sm">
                    {error}
                </div>
            )}

            <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-500 text-sm">
                        <Activity className="w-4 h-4" />
                        活跃会话
                    </div>
                    <div className="text-3xl font-black text-slate-900 mt-3">
                        {loading ? "-" : (overview?.session_health.active_sessions ?? 0)}
                    </div>
                </article>

                <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-500 text-sm">
                        <ShieldCheck className="w-4 h-4" />
                        24h 完成率
                    </div>
                    <div className="text-3xl font-black text-slate-900 mt-3">
                        {loading ? "-" : `${overview?.session_health.completion_rate ?? 0}%`}
                    </div>
                </article>

                <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex items-center gap-2 text-slate-500 text-sm">
                        <AlertTriangle className="w-4 h-4" />
                        24h 异常日志
                    </div>
                    <div className="text-3xl font-black text-slate-900 mt-3">
                        {loading ? "-" : (overview?.fault_health.failed_or_warning_logs_window ?? 0)}
                    </div>
                </article>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                    <div>
                        <h2 className="font-bold text-slate-900">故障摘要</h2>
                        <p className="text-xs text-slate-500 mt-1">最近日志记录（只读）</p>
                    </div>
                    <Badge variant="secondary" className="bg-slate-100 text-slate-700 border-slate-200">
                        异常 {failedOrWarningFaults.length}
                    </Badge>
                </div>

                <div className="divide-y divide-slate-100">
                    {!loading && faults.length === 0 && (
                        <div className="px-5 py-6 text-sm text-slate-500">暂无故障记录</div>
                    )}
                    {faults.map((item) => (
                        <div key={item.log_id} className="px-5 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                            <div className="min-w-0">
                                <div className="font-medium text-slate-900 truncate">{item.action}</div>
                                <div className="text-xs text-slate-500 mt-1">
                                    {item.user_identifier} · {formatDateTime(item.created_at)}
                                </div>
                            </div>
                            <Badge
                                variant={item.status === "failed" ? "destructive" : "secondary"}
                                className={item.status === "warning" ? "bg-amber-100 text-amber-700 border-amber-200" : ""}
                            >
                                {item.status}
                            </Badge>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}

