"use client";

import { useEffect, useState } from "react";
import { AlertCircle, RefreshCw, Search } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { AdminSystemLog, AdminSystemLogDiagnosticItem, AdminSystemLogExposurePolicy } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

const PAGE_SIZE = 10;

function getStatusBadgeVariant(status: string): "green" | "red" | "orange" | "secondary" {
    const normalized = status.trim().toLowerCase();
    if (normalized === "success") return "green";
    if (normalized === "failed") return "red";
    if (normalized === "warning") return "orange";
    return "secondary";
}

function getStatusLabel(status: string): string {
    const normalized = status.trim().toLowerCase();
    if (normalized === "success") return "成功";
    if (normalized === "failed") return "失败";
    if (normalized === "warning") return "告警";
    return status || "未知";
}

function formatDate(iso: string): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString("zh-CN", { hour12: false });
}

function buildDiagnosticItems(log: AdminSystemLog): AdminSystemLogDiagnosticItem[] {
    return Array.isArray(log.diagnostics)
        ? log.diagnostics.filter((item): item is AdminSystemLogDiagnosticItem => Boolean(item?.key && item?.value))
        : [];
}

export default function AdminLogsPage() {
    const toast = useToast();
    const [logs, setLogs] = useState<AdminSystemLog[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "success" | "failed" | "warning">("all");
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [policy, setPolicy] = useState<AdminSystemLogExposurePolicy | null>(null);

    const loadLogs = async (targetPage = page) => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.adminTools.getSystemLogs({
                search: searchQuery || undefined,
                status: statusFilter === "all" ? undefined : statusFilter,
                page: targetPage,
                page_size: PAGE_SIZE,
            });
            setLogs(result.items || []);
            setTotal(result.total || 0);
            setPolicy(result.policy || null);
        } catch (err) {
            const message = getApiErrorMessage(err);
            setError(message);
            setLogs([]);
            setPolicy(null);
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadLogs();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, statusFilter]);

    const handleSearch = () => {
        setPage(1);
        void loadLogs(1);
    };

    const maxPage = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">操作日志</h1>
                    <p className="text-slate-500 mt-1">查看系统关键操作与审计轨迹</p>
                </div>
                <Button
                    variant="outline"
                    className="rounded-full"
                    onClick={() => void loadLogs()}
                    disabled={isLoading}
                >
                    <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
                    刷新
                </Button>
            </div>

            <GlassCard className="p-4 space-y-4">
                <div className="flex flex-col md:flex-row gap-3">
                    <div className="relative flex-1">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <Input
                            value={searchQuery}
                            onChange={(event) => setSearchQuery(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter") {
                                    handleSearch();
                                }
                            }}
                            className="pl-9"
                            placeholder="按操作名或用户标识搜索"
                        />
                    </div>
                    <select
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                        value={statusFilter}
                        onChange={(event) => {
                            setStatusFilter(event.target.value as typeof statusFilter);
                            setPage(1);
                        }}
                    >
                        <option value="all">全部状态</option>
                        <option value="success">成功</option>
                        <option value="warning">告警</option>
                        <option value="failed">失败</option>
                    </select>
                    <Button className="rounded-full bg-slate-900 text-white" onClick={handleSearch}>
                        查询
                    </Button>
                </div>

                {policy && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                        <div className="font-medium">日志可见性策略：{policy.version}</div>
                        <div>{policy.redaction_summary}</div>
                    </div>
                )}

                {error && (
                    <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}
            </GlassCard>

            <GlassCard className="overflow-hidden">
                {isLoading ? (
                    <div className="py-20 text-center text-slate-500">加载中...</div>
                ) : logs.length === 0 ? (
                    <div className="py-20 text-center text-slate-500">暂无日志数据</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                                <tr>
                                    <th className="px-5 py-3 text-left">时间</th>
                                    <th className="px-5 py-3 text-left">操作</th>
                                    <th className="px-5 py-3 text-left">用户标识</th>
                                    <th className="px-5 py-3 text-left">来源 IP</th>
                                    <th className="px-5 py-3 text-left">状态</th>
                                    <th className="px-5 py-3 text-left">诊断上下文</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map((log) => {
                                    const diagnostics = buildDiagnosticItems(log);
                                    return (
                                        <tr key={log.id} className="border-b border-slate-100 last:border-0">
                                            <td className="px-5 py-4 text-slate-600 whitespace-nowrap">
                                                {formatDate(log.created_at)}
                                            </td>
                                            <td className="px-5 py-4 font-medium text-slate-800 whitespace-nowrap">
                                                {log.action}
                                            </td>
                                            <td className="px-5 py-4 text-slate-600 whitespace-nowrap">
                                                {log.user_identifier}
                                            </td>
                                            <td className="px-5 py-4 text-slate-500 whitespace-nowrap">
                                                {log.ip_address || "-"}
                                            </td>
                                            <td className="px-5 py-4 whitespace-nowrap">
                                                <Badge variant={getStatusBadgeVariant(log.status)}>
                                                    {getStatusLabel(log.status)}
                                                </Badge>
                                            </td>
                                            <td className="px-5 py-4 text-slate-500 max-w-[420px]">
                                                {diagnostics.length > 0 ? (
                                                    <div className="flex flex-wrap gap-2">
                                                        {diagnostics.map((item) => (
                                                            <span
                                                                key={`${log.id}-${item.key}`}
                                                                className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700"
                                                            >
                                                                {item.value}
                                                            </span>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <span className="text-slate-400">-</span>
                                                )}
                                                {log.details && (
                                                    <div className="mt-2 text-xs text-slate-400 break-words">{log.details}</div>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </GlassCard>

            <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">
                    显示 {logs.length > 0 ? `${(page - 1) * PAGE_SIZE + 1}-${(page - 1) * PAGE_SIZE + logs.length}` : "0"} / {total}
                </span>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        className="rounded-full"
                        disabled={page <= 1}
                        onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                    >
                        上一页
                    </Button>
                    <span className="text-xs text-slate-400">第 {page} / {maxPage} 页</span>
                    <Button
                        variant="ghost"
                        className="rounded-full"
                        disabled={page >= maxPage}
                        onClick={() => setPage((prev) => Math.min(maxPage, prev + 1))}
                    >
                        下一页
                    </Button>
                </div>
            </div>
        </div>
    );
}
