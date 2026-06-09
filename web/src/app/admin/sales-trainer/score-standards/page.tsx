"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

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
import type { SalesTrainerAudioScorePrompt } from "@/lib/api/types";

export default function SalesTrainerScoreStandardsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [items, setItems] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [publishingPrompt, setPublishingPrompt] = useState<SalesTrainerAudioScorePrompt | null>(null);
    const [isPublishing, setIsPublishing] = useState(false);

    const loadPrompts = useCallback(async () => {
        setIsLoading(true);
        try {
            const result = await api.admin.salesTrainer.listScorePrompts({ include_archived: true });
            setItems(result.items);
        } catch (loadError) {
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        void loadPrompts();
    }, [loadPrompts]);

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
                    title="新人训练路径录音评分标准"
                    description="评分方案同时管理 AI 评分 prompt 和学员可见 rubric；创建与编辑都在独立页面。"
                    primaryAction={(
                        <Button
                            className="rounded-full bg-slate-900 text-white"
                            onClick={() => router.push("/admin/sales-trainer/score-standards/new")}
                        >
                            新建评分标准
                        </Button>
                    )}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
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
                                        <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/score-standards/${item.prompt_id}/edit`)}>
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
        </AdminIndexShell>
    );
}
