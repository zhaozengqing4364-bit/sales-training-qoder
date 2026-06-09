"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerQuestionForm } from "@/components/admin/sales-trainer/question-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerQuestion, SalesTrainerQuestionCategory, SalesTrainerQuestionUpdateRequest } from "@/lib/api/types";

export default function EditSalesTrainerQuestionPage() {
    const params = useParams<{ questionId: string }>();
    const pathname = usePathname();
    const toast = useToast();
    const [question, setQuestion] = useState<SalesTrainerQuestion | null>(null);
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadQuestion() {
            setIsLoading(true);
            try {
                const [questionResult, categoryResult] = await Promise.all([
                    api.admin.salesTrainer.getQuestion(params.questionId),
                    api.admin.salesTrainer.listQuestionCategories(),
                ]);
                setQuestion(questionResult);
                setCategories(categoryResult.items);
            } catch (loadError) {
                toast.error(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadQuestion();
    }, [params.questionId, toast]);

    async function handleSubmit(payload: SalesTrainerQuestionUpdateRequest) {
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
            backHref="/admin/sales-trainer/questions"
            title={question ? `编辑题目：${question.title}` : "编辑题目"}
            description="已发布题目也可以编辑；保存会生成待发布修订，发布后只影响后续组卷和后续学员作答。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载题目...</div>
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
