"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerOperationLog } from "@/lib/api/types";

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
                    title="销售训练操作日志"
                    description="MVP 只提供只读列表，便于追踪学员与管理员关键操作。"
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
                            <th className="px-6 py-4">metadata</th>
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
                        ) : items.map((item) => (
                            <tr key={item.log_id} className="border-b border-slate-100 last:border-b-0 align-top">
                                <td className="px-6 py-4">{new Date(item.created_at).toLocaleString()}</td>
                                <td className="px-6 py-4">{item.action}</td>
                                <td className="px-6 py-4">{item.actor_role ? `${item.actor_role} · ${item.actor_id || "-"}` : item.actor_id || "-"}</td>
                                <td className="px-6 py-4">{item.target_type}{item.target_id ? ` · ${item.target_id}` : ""}</td>
                                <td className="px-6 py-4">
                                    <pre className="whitespace-pre-wrap break-all text-xs text-slate-500">
                                        {JSON.stringify(item.metadata, null, 2)}
                                    </pre>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </GlassCard>
        </AdminIndexShell>
    );
}
