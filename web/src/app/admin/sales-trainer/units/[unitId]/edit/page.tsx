"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerUnitForm } from "@/components/admin/sales-trainer/unit-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { normalizeNewcomerUnitDisplay } from "@/lib/sales-trainer/admin-display";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerAdminCapabilities,
    SalesTrainerMaterial,
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
    const [materials, setMaterials] = useState<SalesTrainerMaterial[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessUnitForm = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

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

    const loadDependencies = useCallback(async () => {
        if (!canAccessUnitForm) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const [unitsResult, questionsResult, promptsResult, materialsResult] = await Promise.all([
                api.admin.newcomerTraining.listUnits({ include_archived: true, limit: 100 }),
                api.admin.salesTrainer.listQuestions({ status: "published", tag: NEWCOMER_QUESTION_TAG }),
                api.admin.salesTrainer.listScorePrompts({ include_archived: true }),
                api.admin.salesTrainer.listMaterials({ include_archived: true, limit: 100 }),
            ]);
            setUnits(unitsResult.items);
            setQuestions(questionsResult.items);
            setPrompts(promptsResult.items);
            setMaterials(materialsResult.items);
        } catch (error) {
            const message = getApiErrorMessage(error);
            setUnits([]);
            setQuestions([]);
            setPrompts([]);
            setMaterials([]);
            setLoadError(message);
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessUnitForm, toast]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessUnitForm) {
            setUnits([]);
            setQuestions([]);
            setPrompts([]);
            setMaterials([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadDependencies();
    }, [canAccessUnitForm, isCapabilityLoading, loadDependencies]);

    const unit = useMemo(
        () => units.find((item) => item.unit_id === params.unitId) ?? null,
        [params.unitId, units],
    );
    const displayUnit = useMemo(
        () => (unit ? normalizeNewcomerUnitDisplay(unit) : null),
        [unit],
    );

    async function handleSubmit(payload: SalesTrainerUnitUpdateRequest) {
        if (!canAccessUnitForm) {
            return;
        }
        setIsSubmitting(true);
        try {
            await api.admin.newcomerTraining.updateUnit(params.unitId, payload);
            toast.success("训练单元修订已保存，发布后只影响后续学员");
            router.refresh();
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/units"
            title={displayUnit ? `编辑训练单元：${displayUnit.name}` : "编辑训练单元"}
            description="已发布训练单元可以直接编辑；保存会生成待发布修订，发布后只影响后续学员。归档版本仅用于审计追溯。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验模块单元管理权限...</div>
            ) : capabilityError || !canAccessUnitForm ? (
                <AdminLoadErrorCard
                    title="模块单元权限不足"
                    description="当前页不会在权限未确认时加载训练单元或开放编辑表单。请联系管理员开通模块管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载训练单元...</div>
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="训练单元加载失败"
                    description="当前页不会在训练单元、题目、评分 Prompt 或材料依赖缺失时开放编辑表单。请核对权限、配置发布状态或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载训练单元"
                    onRetry={() => void loadDependencies()}
                />
            ) : unit ? (
                <SalesTrainerUnitForm
                    mode="edit"
                    initialUnit={displayUnit}
                    availableQuestions={questions}
                    availablePrompts={prompts}
                    availableMaterials={materials}
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
