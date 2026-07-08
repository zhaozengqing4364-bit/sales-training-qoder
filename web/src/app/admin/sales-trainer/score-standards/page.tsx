"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import {
    formatAdminStatus,
    formatScorePromptPurpose,
} from "@/lib/sales-trainer/admin-display";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerAudioScorePrompt,
} from "@/lib/api/types";

export default function SalesTrainerScoreStandardsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const isAudioManagementPath = pathname.startsWith("/admin/sales-trainer/audio");
    const toast = useToast();
    const [items, setItems] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [publishingPrompt, setPublishingPrompt] = useState<SalesTrainerAudioScorePrompt | null>(null);
    const [isPublishing, setIsPublishing] = useState(false);
    const [capabilities, setCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessScoreStandards = isSalesTrainerAdminPathAllowedForCapabilities(pathname, capabilities);

    const loadPrompts = useCallback(async () => {
        if (!canAccessScoreStandards) {
            return;
        }
        setIsLoading(true);
        try {
            const result = await api.admin.salesTrainer.listScorePrompts({ include_archived: true });
            setItems(result.items);
        } catch (loadError) {
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [canAccessScoreStandards, toast]);

    useEffect(() => {
        let isCurrent = true;
        void api.admin.salesTrainer.getCapabilities()
            .then((result) => {
                if (!isCurrent) return;
                setCapabilities(result);
                setCapabilityError(null);
            })
            .catch((error) => {
                if (!isCurrent) return;
                setCapabilities(null);
                setCapabilityError(getApiErrorMessage(error));
            })
            .finally(() => {
                if (!isCurrent) return;
                setIsCapabilityLoading(false);
            });
        return () => {
            isCurrent = false;
        };
    }, []);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessScoreStandards) {
            setItems([]);
            setPublishingPrompt(null);
            setIsLoading(false);
            return;
        }
        void loadPrompts();
    }, [canAccessScoreStandards, isCapabilityLoading, loadPrompts]);

    async function publishPrompt() {
        if (!publishingPrompt) {
            return;
        }
        setIsPublishing(true);
        try {
            await api.admin.salesTrainer.publishScorePrompt(publishingPrompt.prompt_id);
            toast.success("录音评分标准已发布并对后续评分生效");
            setPublishingPrompt(null);
            await loadPrompts();
        } catch (publishError) {
            toast.error(getApiErrorMessage(publishError));
        } finally {
            setIsPublishing(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title={isAudioManagementPath ? "录音评分标准" : "新人训练路径录音评分标准"}
                    description={isAudioManagementPath
                        ? "管理录音任务使用的 AI 评分 prompt、学员可见 rubric 和发布版本。"
                        : "评分方案同时管理 AI 评分 prompt 和学员可见 rubric；创建与编辑都在独立页面。"}
                    primaryAction={canAccessScoreStandards ? (
                        <Button
                            className="rounded-full bg-slate-900 text-white"
                            onClick={() => router.push(isAudioManagementPath
                                ? "/admin/sales-trainer/audio/score-standards/new"
                                : "/admin/sales-trainer/score-standards/new")}
                        >
                            新建评分标准
                        </Button>
                    ) : null}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={capabilities} />}
                />
            )}
        >
            <ConfirmDialog
                open={Boolean(publishingPrompt)}
                onOpenChange={(open) => !open && setPublishingPrompt(null)}
                title="发布并生效"
                description={`发布“${publishingPrompt?.name ?? ""}”的新修订后，只影响后续学员和后续评分；已提交录音、转写和评分结果继续保留当时快照。`}
                confirmText="发布并生效"
                onConfirm={() => void publishPrompt()}
                isLoading={isPublishing}
            />

            {isCapabilityLoading ? (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
                    正在校验评分标准管理权限...
                </div>
            ) : capabilityError || !canAccessScoreStandards ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
                    <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-5 w-5" aria-hidden />
                        <div>
                            <h2 className="font-bold text-amber-950">评分标准管理权限不足</h2>
                            <p className="mt-1 text-sm leading-6">
                                当前页不会在权限未确认时展示评分标准写入入口。请联系管理员开通内容管理权限后重试。
                            </p>
                            {capabilityError ? (
                                <p className="mt-2 text-sm font-medium">{capabilityError}</p>
                            ) : null}
                        </div>
                    </div>
                </div>
            ) : null}

            {canAccessScoreStandards ? (
                <GlassCard className="overflow-hidden p-0">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                            <th className="px-6 py-4">名称</th>
                            <th className="px-6 py-4">适用用途</th>
                            <th className="px-6 py-4">状态</th>
                            <th className="px-6 py-4">版本</th>
                            <th className="px-6 py-4">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10 text-center text-slate-500">正在加载录音评分标准...</td>
                            </tr>
                        ) : items.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10 text-center text-slate-500">暂无录音评分标准</td>
                            </tr>
                        ) : items.map((item) => (
                            <tr key={item.prompt_id} className="border-b border-slate-100 last:border-b-0">
                                <td className="px-6 py-4">
                                    <div>
                                        <p className="font-medium text-slate-900">{item.name}</p>
                                        <p className="mt-1 text-xs text-slate-500 line-clamp-2">{item.system_prompt}</p>
                                    </div>
                                </td>
                                <td className="px-6 py-4">{formatScorePromptPurpose(item.purpose)}</td>
                                <td className="px-6 py-4">
                                    <Badge className="bg-slate-100 text-slate-700">{formatAdminStatus(item.status)}</Badge>
                                </td>
                                <td className="px-6 py-4">{item.version}</td>
                                <td className="px-6 py-4">
                                    <div className="flex flex-wrap gap-2">
                                        <Button variant="outline" size="sm" onClick={() => router.push(isAudioManagementPath
                                            ? `/admin/sales-trainer/audio/score-standards/${item.prompt_id}/edit`
                                            : `/admin/sales-trainer/score-standards/${item.prompt_id}/edit`)}>
                                            编辑
                                        </Button>
                                        {item.status !== "published" ? (
                                            <Button variant="outline" size="sm" onClick={() => setPublishingPrompt(item)}>
                                                发布
                                            </Button>
                                        ) : null}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </GlassCard>
            ) : null}
        </AdminIndexShell>
    );
}
