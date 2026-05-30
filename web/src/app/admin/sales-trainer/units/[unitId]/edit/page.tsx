"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerUnitForm } from "@/components/admin/sales-trainer/unit-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerQuestion,
    SalesTrainerUnit,
    SalesTrainerUnitUpdateRequest,
} from "@/lib/api/types";

export default function EditSalesTrainerUnitPage() {
    const params = useParams<{ unitId: string }>();
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [units, setUnits] = useState<SalesTrainerUnit[]>([]);
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [prompts, setPrompts] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadDependencies() {
            setIsLoading(true);
            try {
                const [unitsResult, questionsResult, promptsResult] = await Promise.all([
                    api.admin.salesTrainer.listUnits({ include_archived: true, limit: 100 }),
                    api.admin.salesTrainer.listQuestions({ status: "published" }),
                    api.admin.salesTrainer.listScorePrompts({ include_archived: true }),
                ]);
                setUnits(unitsResult.items);
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

    const unit = useMemo(
        () => units.find((item) => item.unit_id === params.unitId) ?? null,
        [params.unitId, units],
    );

    async function handleSubmit(payload: SalesTrainerUnitUpdateRequest) {
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.updateUnit(params.unitId, payload);
            toast.success("训练单元已保存");
            router.refresh();
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/units"
            title={unit ? `编辑训练单元：${unit.name}` : "编辑训练单元"}
            description="只有 draft 状态允许修改；发布与归档请回到列表页操作。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载训练单元...</div>
            ) : unit ? (
                <SalesTrainerUnitForm
                    mode="edit"
                    initialUnit={unit}
                    availableQuestions={questions}
                    availablePrompts={prompts}
                    isSubmitting={isSubmitting}
                    onSubmit={(payload) => void handleSubmit(payload as SalesTrainerUnitUpdateRequest)}
                />
            ) : (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    未找到对应训练单元。
                </div>
            )}
        </AdminFormShell>
    );
}
