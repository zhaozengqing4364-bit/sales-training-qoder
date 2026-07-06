"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerOperationLog,
} from "@/lib/api/types";
import { buildOperationLogDisplay } from "@/lib/sales-trainer/operation-log-display";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";

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
    const [loadError, setLoadError] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessLogs = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

    const loadCapabilities = useCallback(async () => {
        setIsCapabilityLoading(true);
        setCapabilityError(null);
        try {
            setAdminCapabilities(await api.admin.salesTrainer.getCapabilities());
        } catch (error) {
            setAdminCapabilities(null);
            setCapabilityError(getApiErrorMessage(error));
        } finally {
            setIsCapabilityLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    const loadLogs = useCallback(async () => {
        if (!canAccessLogs) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const result = await api.admin.salesTrainer.listOperationLogs({ limit: 100 });
            setItems(result.items);
        } catch (loadError) {
            setItems([]);
            setLoadError(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [canAccessLogs]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessLogs) {
            setItems([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadLogs();
    }, [canAccessLogs, isCapabilityLoading, loadLogs]);

    const content = (() => {
        if (isCapabilityLoading) {
            return <div className="py-12 text-center text-sm text-slate-500">正在校验操作日志权限...</div>;
        }
        if (capabilityError || !canAccessLogs) {
            return (
                <AdminLoadErrorCard
                    title="操作日志权限不足"
                    description="当前页不会在权限未确认时加载审计日志，避免把权限异常伪装为空日志。请联系管理员开通操作日志权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            );
        }
        if (loadError) {
            return (
                <AdminLoadErrorCard
                    title="操作日志加载失败"
                    description="当前页不会在审计日志读取失败时渲染空状态。请检查权限、日志服务或后端接口后重试。"
                    message={loadError}
                    retryLabel="重新加载日志"
                    onRetry={() => void loadLogs()}
                />
            );
        }
        return (
            <GlassCard className="overflow-hidden p-0">
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
        );
    })();

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径操作日志"
                    description="集中追踪发布、回滚、绑定变更、历史重评和学员关键操作，原始诊断数据可按需展开。"
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
                />
            )}
        >
            {content}
        </AdminIndexShell>
    );
}
