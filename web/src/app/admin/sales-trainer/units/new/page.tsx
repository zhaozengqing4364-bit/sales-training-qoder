"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerUnitForm } from "@/components/admin/sales-trainer/unit-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioScorePrompt, SalesTrainerQuestion, SalesTrainerUnitCreateRequest } from "@/lib/api/types";

export default function NewSalesTrainerUnitPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [prompts, setPrompts] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadDependencies() {
            setIsLoading(true);
            try {
                const [questionsResult, promptsResult] = await Promise.all([
                    api.admin.salesTrainer.listQuestions({ status: "published" }),
                    api.admin.salesTrainer.listScorePrompts({ include_archived: false }),
                ]);
                setQuestions(questionsResult.items);
                setPrompts(promptsResult.items);
            } catch (loadError) {
                toast.error(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadDependencies();
    }, [toast]);

    async function handleSubmit(payload: SalesTrainerUnitCreateRequest) {
        setIsSubmitting(true);
        try {
            const result = await api.admin.salesTrainer.createUnit(payload);
            toast.success("训练单元已创建");
            router.push(`/admin/sales-trainer/units/${result.unit_id}/edit`);
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/units"
            title="新建销售训练单元"
            description="支持 quiz 与 audio_scoring 两类训练单元。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载表单依赖...</div>
            ) : (
                <SalesTrainerUnitForm
                    mode="create"
                    availableQuestions={questions}
                    availablePrompts={prompts}
                    isSubmitting={isSubmitting}
                    onSubmit={(payload) => void handleSubmit(payload as SalesTrainerUnitCreateRequest)}
                />
            )}
        </AdminFormShell>
    );
}
