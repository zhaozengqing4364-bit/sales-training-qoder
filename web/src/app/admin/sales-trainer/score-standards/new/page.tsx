"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerScorePromptForm } from "@/components/admin/sales-trainer/score-prompt-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerAudioScorePromptCreateRequest,
} from "@/lib/api/types";

export default function NewSalesTrainerScoreStandardPage() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const toast = useToast();
    const initialPurpose = searchParams.get("purpose");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
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

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    async function handleSubmit(payload: SalesTrainerAudioScorePromptCreateRequest) {
        if (!canAccessScorePromptForm) {
            return;
        }
        setIsSubmitting(true);
        try {
            const result = await api.admin.salesTrainer.createScorePrompt(payload);
            toast.success("录音评分标准已创建");
            router.push(`/admin/sales-trainer/score-standards/${result.prompt_id}/edit`);
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/score-standards"
            title="新建录音评分标准"
            description="后续训练单元只能绑定已发布的评分标准；发布后仍可编辑，保存会生成待发布修订，只影响后续学员。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验内容管理权限...</div>
            ) : capabilityError || !canAccessScorePromptForm ? (
                <AdminLoadErrorCard
                    title="评分标准管理权限不足"
                    description="当前页不会在权限未确认时开放新建评分标准表单。请联系管理员开通内容管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : (
            <SalesTrainerScorePromptForm
                mode="create"
                initialPurpose={initialPurpose}
                isSubmitting={isSubmitting}
                onSubmit={(payload) => void handleSubmit(payload as SalesTrainerAudioScorePromptCreateRequest)}
            />
            )}
        </AdminFormShell>
    );
}
