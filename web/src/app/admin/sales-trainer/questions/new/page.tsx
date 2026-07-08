"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerQuestionForm } from "@/components/admin/sales-trainer/question-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerQuestionCategory,
    SalesTrainerQuestionCreateRequest,
} from "@/lib/api/types";

export default function NewSalesTrainerQuestionPage() {
    const pathname = usePathname();
    const router = useRouter();
    const isLearningTopicsPath = pathname.startsWith("/admin/sales-trainer/learning-topics");
    const { error: showError, success: showSuccess } = useToast();
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessQuestionForm = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

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

    const loadCategories = useCallback(async () => {
        if (!canAccessQuestionForm) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            setCategories((await api.admin.salesTrainer.listQuestionCategories()).items);
        } catch (loadError) {
            const message = getApiErrorMessage(loadError);
            setCategories([]);
            setLoadError(message);
            showError(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessQuestionForm, showError]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessQuestionForm) {
            setCategories([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadCategories();
    }, [canAccessQuestionForm, isCapabilityLoading, loadCategories]);

    async function handleSubmit(payload: SalesTrainerQuestionCreateRequest) {
        if (!canAccessQuestionForm) {
            return;
        }
        setIsSubmitting(true);
        try {
            const question = await api.admin.salesTrainer.createQuestion(payload);
            showSuccess("题目已创建");
            router.push(isLearningTopicsPath
                ? `/admin/sales-trainer/learning-topics/questions/${question.question_id}/edit`
                : `/admin/sales-trainer/questions/${question.question_id}/edit`);
        } catch (submitError) {
            showError(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref={isLearningTopicsPath
                ? "/admin/sales-trainer/learning-topics/questions"
                : "/admin/sales-trainer/questions"}
            title="新建销售题目"
            description="业务字段会由后端转换成标准 scoring_criteria，不需要手写 JSON。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验题库管理权限...</div>
            ) : capabilityError || !canAccessQuestionForm ? (
                <AdminLoadErrorCard
                    title="题库管理权限不足"
                    description="当前页不会在权限未确认时加载分类或开放新建题目表单。请联系管理员开通题库管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载分类...</div>
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="分类加载失败"
                    description="当前页不会在分类依赖缺失时开放新建表单。请核对权限、题库配置或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载分类"
                    onRetry={() => void loadCategories()}
                />
            ) : (
                <SalesTrainerQuestionForm
                    mode="create"
                    categories={categories}
                    isSubmitting={isSubmitting}
                    onSubmit={(payload) => void handleSubmit(payload as SalesTrainerQuestionCreateRequest)}
                />
            )}
        </AdminFormShell>
    );
}
