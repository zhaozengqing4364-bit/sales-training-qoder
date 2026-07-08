"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerQuestionForm } from "@/components/admin/sales-trainer/question-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerQuestion,
    SalesTrainerQuestionCategory,
    SalesTrainerQuestionUpdateRequest,
} from "@/lib/api/types";

export default function EditSalesTrainerQuestionPage() {
    const params = useParams<{ questionId: string }>();
    const pathname = usePathname();
    const toast = useToast();
    const isLearningTopicsPath = pathname.startsWith("/admin/sales-trainer/learning-topics");
    const [question, setQuestion] = useState<SalesTrainerQuestion | null>(null);
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
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

    const loadQuestion = useCallback(async () => {
        if (!canAccessQuestionForm) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const [questionResult, categoryResult] = await Promise.all([
                api.admin.salesTrainer.getQuestion(params.questionId),
                api.admin.salesTrainer.listQuestionCategories(),
            ]);
            setQuestion(questionResult);
            setCategories(categoryResult.items);
        } catch (error) {
            const message = getApiErrorMessage(error);
            setQuestion(null);
            setCategories([]);
            setLoadError(message);
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessQuestionForm, params.questionId, toast]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessQuestionForm) {
            setQuestion(null);
            setCategories([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadQuestion();
    }, [canAccessQuestionForm, isCapabilityLoading, loadQuestion]);

    async function handleSubmit(payload: SalesTrainerQuestionUpdateRequest) {
        if (!canAccessQuestionForm) {
            return;
        }
        setIsSubmitting(true);
        try {
            const updated = await api.admin.salesTrainer.updateQuestion(params.questionId, payload);
            setQuestion(updated);
            toast.success("题目修订已保存，发布后只影响后续组卷和学员作答");
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref={isLearningTopicsPath
                ? "/admin/sales-trainer/learning-topics/questions"
                : "/admin/sales-trainer/questions"}
            title={question ? `编辑题目：${question.title}` : "编辑题目"}
            description="已发布题目也可以编辑；保存会生成待发布修订，发布后只影响后续组卷和后续学员作答。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验题库管理权限...</div>
            ) : capabilityError || !canAccessQuestionForm ? (
                <AdminLoadErrorCard
                    title="题库管理权限不足"
                    description="当前页不会在权限未确认时加载题目或开放编辑表单。请联系管理员开通题库管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载题目...</div>
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="题目加载失败"
                    description="当前页不会在题目或分类依赖缺失时开放编辑表单。请核对权限、题库配置或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载题目"
                    onRetry={() => void loadQuestion()}
                />
            ) : question ? (
                <SalesTrainerQuestionForm
                    mode="edit"
                    initialQuestion={question}
                    categories={categories}
                    isSubmitting={isSubmitting}
                    onSubmit={(payload) => void handleSubmit(payload as SalesTrainerQuestionUpdateRequest)}
                />
            ) : (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">未找到对应题目。</div>
            )}
        </AdminFormShell>
    );
}
