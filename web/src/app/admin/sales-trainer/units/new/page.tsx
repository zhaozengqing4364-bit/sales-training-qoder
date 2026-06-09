"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerUnitForm } from "@/components/admin/sales-trainer/unit-form";
import { buildUnitTemplateForModule } from "@/components/admin/sales-trainer/unit-module-template";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerMaterial,
    SalesTrainerQuestion,
    SalesTrainerUnitCreateRequest,
} from "@/lib/api/types";

export default function NewSalesTrainerUnitPage() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const toast = useToast();
    const moduleKey = searchParams.get("module");
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [prompts, setPrompts] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [materials, setMaterials] = useState<SalesTrainerMaterial[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadDependencies() {
            setIsLoading(true);
            try {
                const [questionsResult, promptsResult, materialsResult] = await Promise.all([
                    api.admin.salesTrainer.listQuestions({ status: "published", tag: NEWCOMER_QUESTION_TAG }),
                    api.admin.salesTrainer.listScorePrompts({ include_archived: false }),
                    api.admin.salesTrainer.listMaterials({ include_archived: false, limit: 100 }),
                ]);
                setQuestions(questionsResult.items);
                setPrompts(promptsResult.items);
                setMaterials(materialsResult.items);
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
            const result = await api.admin.newcomerTraining.createUnit(payload);
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
            title="新建新人训练路径模块单元"
            description="支持 quiz 与 audio_scoring 两类训练单元。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载表单依赖...</div>
            ) : (
                <SalesTrainerUnitForm
                    mode="create"
                    initialUnit={buildUnitTemplateForModule({
                        materials,
                        moduleKey,
                        prompts,
                    })}
                    availableQuestions={questions}
                    availablePrompts={prompts}
                    availableMaterials={materials}
                    isSubmitting={isSubmitting}
                    onSubmit={(payload) => void handleSubmit(payload as SalesTrainerUnitCreateRequest)}
                />
            )}
        </AdminFormShell>
    );
}
