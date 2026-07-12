"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerSettings } from "@/lib/api/types";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";


function StatusBadge({ ok }: { ok: boolean }) {
    return (
        <Badge className={ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}>
            {ok ? "已配置" : "未配置"}
        </Badge>
    );
}

function policyValue(value: unknown): string {
    return value == null ? "--" : String(value);
}

export default function SalesTrainerSettingsPage() {
    const pathname = usePathname();
    const [settings, setSettings] = useState<SalesTrainerSettings | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);

    const loadSettings = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const loadedSettings = await api.admin.salesTrainer.getSettings();
            setSettings(loadedSettings);
        } catch (loadError) {
            setSettings(null);
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
            setSettings(null);
            setError(null);
            setIsLoading(false);
            return;
        }
        void loadSettings();
    }, [loadSettings, routeAccess.canAccess, routeAccess.isLoading]);

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="新人训练路径配置"
                    description="展示存储、ASR 和评分服务的健康状态；密钥仍由部署环境管理，页面不展示密钥值。"
                    secondaryActions={(
                        <div className="flex flex-wrap items-center gap-2">
                            <Button asChild variant="outline" className="rounded-full">
                                <Link href="/support/runtime">打开运行时健康</Link>
                            </Button>
                            <SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />
                        </div>
                    )}
                />
            )}
        >
            {routeAccess.denialMessage ? (
                <AdminLoadErrorCard
                    title="页面访问受限"
                    description="当前页不会在能力接口失败或权限不足时继续加载配置诊断，避免把不可访问状态伪装成配置缺失。"
                    message={routeAccess.denialMessage}
                    retryLabel="重新检查权限"
                    onRetry={routeAccess.reloadCapabilities}
                />
            ) : isLoading ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500" role="status" aria-live="polite" aria-busy="true">
                    正在加载配置诊断...
                </GlassCard>
            ) : error ? (
                <AdminLoadErrorCard
                    title="配置诊断加载失败"
                    description="当前页不会在配置、路径修订或任务诊断读取失败时渲染空白状态。请检查权限、配置服务或后端接口后重试。"
                    message={error}
                    retryLabel="重新加载配置"
                    onRetry={() => void loadSettings()}
                />
            ) : null}
            {!isLoading && !error && settings ? (
                <div className="grid gap-4 lg:grid-cols-2">
                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">音频上传</h2>
                        <div className="space-y-3 text-sm">
                            <div className="flex justify-between gap-4"><span className="text-slate-500">存储后端</span><span className="font-medium">{settings.storage_backend}</span></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">浏览器直传</span><StatusBadge ok={settings.direct_upload_supported} /></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">COS 配置</span><StatusBadge ok={settings.cos_configured} /></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">COS 公共读</span><StatusBadge ok={settings.cos_public_read} /></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">OSS 配置</span><StatusBadge ok={settings.oss_configured} /></div>
                        </div>
                    </GlassCard>
                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">识别与评分</h2>
                        <div className="space-y-3 text-sm">
                            <div className="flex justify-between gap-4"><span className="text-slate-500">ASR 模式</span><span className="font-medium">{settings.asr_mode}</span></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">ASR 模型</span><span className="font-medium">{settings.asr_model}</span></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">DashScope</span><StatusBadge ok={settings.dashscope_configured} /></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">Deucate</span><StatusBadge ok={settings.deucate_configured} /></div>
                            <div className="flex justify-between gap-4"><span className="text-slate-500">Deucate 模型</span><span className="font-medium">{settings.deucate_model || "未设置"}</span></div>
                        </div>
                    </GlassCard>
                    <GlassCard className="space-y-4 p-6 lg:col-span-2">
                        <h2 className="text-lg font-bold text-slate-900">上传限制</h2>
                        <div className="grid gap-3 text-sm md:grid-cols-3">
                            <div><span className="block text-slate-500">最大文件</span><span className="font-medium">{settings.max_file_size_mb} MB</span></div>
                            <div><span className="block text-slate-500">访问链接有效期</span><span className="font-medium">{settings.file_url_expires_seconds} 秒</span></div>
                            <div><span className="block text-slate-500">允许格式</span><span className="font-medium">{settings.allowed_mime_types.join(", ")}</span></div>
                        </div>
                    </GlassCard>
                    <GlassCard className="space-y-4 p-6 lg:col-span-2">
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                            <h2 className="text-lg font-bold text-slate-900">阶段 2 训练闭环策略</h2>
                            {settings.phase2_policy?.management_entry ? (
                                <Link href={settings.phase2_policy.management_entry}>
                                    <Button variant="outline" size="sm">打开策略治理</Button>
                                </Link>
                            ) : null}
                        </div>
                        <div className="grid gap-3 text-sm md:grid-cols-4">
                            <div><span className="block text-slate-500">弱项阈值</span><span className="font-medium">{policyValue(settings.phase2_policy?.low_score_threshold)}</span></div>
                            <div><span className="block text-slate-500">重复训练阈值</span><span className="font-medium">{policyValue(settings.phase2_policy?.repeat_practice_threshold)}</span></div>
                            <div><span className="block text-slate-500">看板记录上限</span><span className="font-medium">{policyValue(settings.phase2_policy?.dashboard_record_limit)}</span></div>
                            <div><span className="block text-slate-500">兜底状态</span><StatusBadge ok={!settings.phase2_policy?.fallback_applied} /></div>
                            <div><span className="block text-slate-500">来源</span><span className="font-medium">{policyValue(settings.phase2_policy?.source)}</span></div>
                            <div><span className="block text-slate-500">策略版本</span><span className="font-medium">{policyValue(settings.phase2_policy?.version)}</span></div>
                            <div><span className="block text-slate-500">配置版本</span><span className="font-medium">{policyValue(settings.phase2_policy?.config_version)}</span></div>
                            <div><span className="block text-slate-500">兜底原因</span><span className="font-medium">{policyValue(settings.phase2_policy?.fallback_reason)}</span></div>
                        </div>
                    </GlassCard>
                </div>
            ) : null}
        </AdminIndexShell>
    );
}
