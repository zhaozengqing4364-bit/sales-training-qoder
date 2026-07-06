"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { formatAdminRecordStatus, formatAudioSourceLabel } from "@/lib/sales-trainer/admin-display";
import type { SalesTrainerAudioSubmission } from "@/lib/api/types";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

function formatSubmissionUser(item: SalesTrainerAudioSubmission): string {
    const primary = item.user_name || item.user_email || item.user_id;
    const secondary = item.user_email && item.user_email !== primary ? item.user_email : item.user_department;
    return secondary ? `${primary} · ${secondary}` : primary;
}

export default function SalesTrainerAudioSubmissionsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const [items, setItems] = useState<SalesTrainerAudioSubmission[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);

    const loadItems = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.admin.salesTrainer.listAudioSubmissions({ limit: 100 });
            setItems(result.items);
        } catch (loadError) {
            setItems([]);
            setError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (routeAccess.isLoading) {
            return;
        }
        if (!routeAccess.canAccess) {
            setItems([]);
            setError(null);
            setIsLoading(false);
            return;
        }
        void loadItems();
    }, [loadItems, routeAccess.canAccess, routeAccess.isLoading]);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径录音记录"
                    description="查看录音状态、转写和评分入口。详情页提供重试和授权文件访问。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />}
                />
            )}
        >
            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="页面访问受限"
                    description="当前页不会在能力接口失败或权限不足时继续加载录音记录，避免把不可访问状态伪装成空列表。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : error ? (
                <AdminLoadErrorCard
                    title="录音记录加载失败"
                    description="当前页不会在录音列表读取失败时渲染空列表，避免把权限、任务服务或后端异常伪装成暂无录音。"
                    message={error}
                    retryLabel="重新加载录音记录"
                    onRetry={() => void loadItems()}
                />
            ) : (
                <GlassCard className="overflow-hidden p-0">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                            <th className="px-6 py-4">文件</th>
                            <th className="px-6 py-4">用户</th>
                            <th className="px-6 py-4">状态</th>
                            <th className="px-6 py-4">上传时间</th>
                            <th className="px-6 py-4">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10 text-center text-slate-500">正在加载录音记录...</td>
                            </tr>
                        ) : items.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10 text-center text-slate-500">暂无录音记录</td>
                            </tr>
                        ) : items.map((item) => (
                            <tr key={item.submission_id} className="border-b border-slate-100 last:border-b-0">
                                <td className="px-6 py-4">
                                    <div>
                                        <p className="font-medium text-slate-900">{item.original_filename}</p>
                                        <p className="mt-1 text-xs text-slate-500">
                                            {item.content_type} · {formatAudioSourceLabel(item.source_page)}
                                        </p>
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <p className="font-medium text-slate-900">{formatSubmissionUser(item)}</p>
                                    <p className="mt-1 text-xs text-slate-400">{item.user_id}</p>
                                </td>
                                <td className="px-6 py-4">
                                    <Badge className="bg-slate-100 text-slate-700">{formatAdminRecordStatus(item.status)}</Badge>
                                </td>
                                <td className="px-6 py-4">{new Date(item.created_at).toLocaleString()}</td>
                                <td className="px-6 py-4">
                                    <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/audio-submissions/${item.submission_id}`)}>
                                        查看详情
                                    </Button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                </GlassCard>
            )}
        </AdminIndexShell>
    );
}
