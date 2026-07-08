"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerUnitForm } from "@/components/admin/sales-trainer/unit-form";
import { buildUnitTemplateForModule } from "@/components/admin/sales-trainer/unit-module-template";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { audioEvaluationScenarioForSlug } from "@/lib/sales-trainer/audio-evaluation-scenarios";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerAdminCapabilities,
    SalesTrainerMaterial,
    SalesTrainerQuestion,
    SalesTrainerUnitCreateRequest,
} from "@/lib/api/types";

export default function NewSalesTrainerUnitPage() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const { error: showError, success: showSuccess } = useToast();
    const scenario = audioEvaluationScenarioForSlug(searchParams.get("scenario"));
    const moduleKey = scenario?.moduleKey ?? searchParams.get("module");
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [prompts, setPrompts] = useState<SalesTrainerAudioScorePrompt[]>([]);
    const [materials, setMaterials] = useState<SalesTrainerMaterial[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
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
            const [questionsResult, promptsResult, materialsResult] = await Promise.all([
                api.admin.salesTrainer.listQuestions({ status: "published", tag: NEWCOMER_QUESTION_TAG }),
                api.admin.salesTrainer.listScorePrompts({ include_archived: false }),
                api.admin.salesTrainer.listMaterials({ include_archived: false, limit: 100 }),
            ]);
            setQuestions(questionsResult.items);
            setPrompts(promptsResult.items);
            setMaterials(materialsResult.items);
        } catch (loadError) {
            const message = getApiErrorMessage(loadError);
            setQuestions([]);
            setPrompts([]);
            setMaterials([]);
            setLoadError(message);
            showError(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessUnitForm, showError]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessUnitForm) {
            setQuestions([]);
            setPrompts([]);
            setMaterials([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadDependencies();
    }, [canAccessUnitForm, isCapabilityLoading, loadDependencies]);

    async function handleSubmit(payload: SalesTrainerUnitCreateRequest) {
        if (!canAccessUnitForm) {
            return;
        }
        setIsSubmitting(true);
        try {
            const result = await api.admin.newcomerTraining.createUnit(payload);
            showSuccess("训练单元已创建");
            router.push(`/admin/sales-trainer/units/${result.unit_id}/edit`);
        } catch (submitError) {
            showError(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/units"
            title="新建新人训练路径模块单元"
            description="支持 quiz 与 audio_scoring 两类训练单元。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验模块单元管理权限...</div>
            ) : capabilityError || !canAccessUnitForm ? (
                <AdminLoadErrorCard
                    title="模块单元权限不足"
                    description="当前页不会在权限未确认时加载表单依赖或开放新建表单。请联系管理员开通模块管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载表单依赖...</div>
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="表单依赖加载失败"
                    description="当前页不会在题目、评分 Prompt 或材料依赖缺失时开放新建表单。请核对权限、配置发布状态或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载表单依赖"
                    onRetry={() => void loadDependencies()}
                />
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
