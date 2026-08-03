"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerScorePromptForm } from "@/components/admin/sales-trainer/score-prompt-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptUpdateRequest,
} from "@/lib/api/types";

type SubmitFeedback = {
    tone: "success" | "warning" | "error";
    message: string;
};

export default function EditSalesTrainerScoreStandardPage() {
    const params = useParams<{ id: string }>();
    const pathname = usePathname();
    const toast = useToast();
    const isAudioManagementPath = pathname.startsWith("/admin/sales-trainer/audio");
    const [items, setItems] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const [submitFeedback, setSubmitFeedback] = useState<SubmitFeedback | null>(null);
    const canAccessScorePromptForm = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

    const loadCapabilities = useCallback(async () => {
        setIsCapabilityLoading(true);
        setCapabilityError(null);
        try {
            const result = await api.admin.salesTrainer.getCapabilities();
            setAdminCapabilities(result);
        } catch (error) {
            setAdminCapabilities(null);
            setCapabilityError(getApiErrorMessage(error));
        } finally {
            setIsCapabilityLoading(false);
        }
    }, []);

    const loadPrompt = useCallback(async () => {
        if (!canAccessScorePromptForm) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const result = await api.admin.salesTrainer.listScorePrompts({ include_archived: true });
            setItems(result.items);
        } catch (error) {
            const message = getApiErrorMessage(error);
            setItems([]);
            setLoadError(message);
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessScorePromptForm, toast]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessScorePromptForm) {
            setItems([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadPrompt();
    }, [canAccessScorePromptForm, isCapabilityLoading, loadPrompt]);

    const prompt = useMemo(
        () => items.find((item) => item.prompt_id === params.id) ?? null,
        [items, params.id],
    );

    async function handleSubmit(payload: SalesTrainerAudioScorePromptUpdateRequest) {
        if (!canAccessScorePromptForm) {
            return;
        }
        setIsSubmitting(true);
        setSubmitFeedback(null);
        let revisionSaved = false;
        try {
            await api.admin.salesTrainer.updateScorePrompt(params.id, payload);
            revisionSaved = true;
            const published = await api.admin.salesTrainer.publishScorePrompt(params.id);
            setItems((current) => current.map((item) => (
                item.prompt_id === published.prompt_id ? published : item
            )));
            setSubmitFeedback({
                tone: "success",
                message: "评分标准已保存并发布。后续录音评分将使用本修订；已提交录音仍保留原评分快照。",
            });
            toast.success("录音评分标准已保存并发布");
        } catch (submitError) {
            const message = getApiErrorMessage(submitError);
            if (revisionSaved) {
                setSubmitFeedback({
                    tone: "warning",
                    message: `修订已保存，但发布未完成：${message}。当前评分仍使用上一已发布版本，可直接重试“保存并发布”。`,
                });
            } else {
                setSubmitFeedback({
                    tone: "error",
                    message: `评分标准保存失败：${message}。当前输入已保留，可修正后重试。`,
                });
            }
            toast.error(message);
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref={isAudioManagementPath
                ? "/admin/sales-trainer/audio/score-standards"
                : "/admin/sales-trainer/score-standards"}
            title={prompt ? `编辑评分标准：${prompt.name}` : "编辑评分标准"}
            description="保存并发布会生成可审计的新修订，并立即用于后续学员和后续评分；历史提交继续使用原快照。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验内容管理权限...</div>
            ) : capabilityError || !canAccessScorePromptForm ? (
                <AdminLoadErrorCard
                    title="评分标准管理权限不足"
                    description="当前页不会在权限未确认时加载评分标准或开放编辑表单。请联系管理员开通内容管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载评分标准...</div>
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="评分标准加载失败"
                    description="当前页不会在评分标准依赖缺失时开放编辑表单。请核对权限、配置发布状态或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载评分标准"
                    onRetry={() => void loadPrompt()}
                />
            ) : prompt ? (
                <div className="space-y-4">
                    {submitFeedback ? (
                        <div
                            role={submitFeedback.tone === "success" ? "status" : "alert"}
                            className={submitFeedback.tone === "success"
                                ? "rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"
                                : submitFeedback.tone === "warning"
                                    ? "rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                                    : "rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"}
                        >
                            {submitFeedback.message}
                        </div>
                    ) : null}
                    <SalesTrainerScorePromptForm
                        mode="edit"
                        initialPrompt={prompt}
                        isSubmitting={isSubmitting}
                        onSubmit={(payload) => void handleSubmit(payload as SalesTrainerAudioScorePromptUpdateRequest)}
                    />
                </div>
            ) : (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    未找到对应录音评分标准。
                </div>
            )}
        </AdminFormShell>
    );
}
