"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerOperationLog } from "@/lib/api/types";
import { buildOperationLogDisplay } from "@/lib/sales-trainer/operation-log-display";

function RawMetadataToggle({ rawJson }: { readonly rawJson: string }) {
    const [isExpanded, setIsExpanded] = useState(false);
    return (
        <div className="space-y-2">
            <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => setIsExpanded((current) => !current)}
            >
                {isExpanded ? "收起原始数据" : "查看原始数据"}
            </Button>
            {isExpanded ? (
                <pre className="whitespace-pre-wrap break-all rounded-2xl bg-slate-50 p-3 text-xs text-slate-500">
                    {rawJson}
                </pre>
            ) : null}
        </div>
    );
}

export default function SalesTrainerOperationLogsPage() {
    const pathname = usePathname();
    const [items, setItems] = useState<SalesTrainerOperationLog[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function loadLogs() {
            setIsLoading(true);
            setError(null);
            try {
                const result = await api.admin.salesTrainer.listOperationLogs({ limit: 100 });
                setItems(result.items);
            } catch (loadError) {
                setItems([]);
                setError(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadLogs();
    }, []);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径操作日志"
                    description="集中追踪发布、回滚、绑定变更、历史重评和学员关键操作，原始诊断数据可按需展开。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <GlassCard className="overflow-hidden p-0">
                {error ? (
                    <div className="border-b border-red-100 bg-red-50 px-6 py-4 text-sm text-red-700">
                        {error}
                    </div>
                ) : null}
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                            <th className="px-6 py-4">时间</th>
                            <th className="px-6 py-4">动作</th>
                            <th className="px-6 py-4">操作者</th>
                            <th className="px-6 py-4">目标</th>
                            <th className="px-6 py-4">变更摘要</th>
                        </tr>
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10 text-center text-slate-500">正在加载操作日志...</td>
                            </tr>
                        ) : items.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10 text-center text-slate-500">暂无操作日志</td>
                            </tr>
                        ) : items.map((item) => {
                            const display = buildOperationLogDisplay(item);
                            return (
                                <tr key={item.log_id} className="border-b border-slate-100 last:border-b-0 align-top">
                                    <td className="px-6 py-4">{new Date(item.created_at).toLocaleString()}</td>
                                    <td className="px-6 py-4 font-medium text-slate-900">{display.actionLabel}</td>
                                    <td className="px-6 py-4">{display.actorLabel}</td>
                                    <td className="px-6 py-4">{display.targetLabel}</td>
                                    <td className="space-y-3 px-6 py-4">
                                        <div className="space-y-1 text-slate-600">
                                            {display.summaryLines.map((line) => (
                                                <p key={line}>{line}</p>
                                            ))}
                                        </div>
                                        <RawMetadataToggle rawJson={display.rawJson} />
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </GlassCard>
        </AdminIndexShell>
    );
}
