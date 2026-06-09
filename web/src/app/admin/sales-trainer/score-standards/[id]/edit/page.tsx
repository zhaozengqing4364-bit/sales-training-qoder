"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerScorePromptForm } from "@/components/admin/sales-trainer/score-prompt-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioScorePrompt, SalesTrainerAudioScorePromptUpdateRequest } from "@/lib/api/types";

export default function EditSalesTrainerScoreStandardPage() {
    const params = useParams<{ id: string }>();
    const pathname = usePathname();
    const toast = useToast();
    const [items, setItems] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadPrompt() {
            setIsLoading(true);
            try {
                const result = await api.admin.salesTrainer.listScorePrompts({ include_archived: true });
                setItems(result.items);
            } catch (loadError) {
                toast.error(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadPrompt();
    }, [toast]);

    const prompt = useMemo(
        () => items.find((item) => item.prompt_id === params.id) ?? null,
        [items, params.id],
    );

    async function handleSubmit(payload: SalesTrainerAudioScorePromptUpdateRequest) {
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.updateScorePrompt(params.id, payload);
            toast.success("录音评分标准修订已保存，发布后只影响后续评分");
            setIsSubmitting(false);
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/score-standards"
            title={prompt ? `编辑评分标准：${prompt.name}` : "编辑评分标准"}
            description="已发布评分标准也可以直接编辑；保存会生成待发布修订，发布后只影响后续学员和后续评分。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载评分标准...</div>
            ) : prompt ? (
                <SalesTrainerScorePromptForm
                    mode="edit"
                    initialPrompt={prompt}
                    isSubmitting={isSubmitting}
                    onSubmit={(payload) => void handleSubmit(payload as SalesTrainerAudioScorePromptUpdateRequest)}
                />
            ) : (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    未找到对应录音评分标准。
                </div>
            )}
        </AdminFormShell>
    );
}
