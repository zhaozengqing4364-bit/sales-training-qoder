"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerQuestionForm } from "@/components/admin/sales-trainer/question-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerQuestionCategory, SalesTrainerQuestionCreateRequest } from "@/lib/api/types";

export default function NewSalesTrainerQuestionPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadCategories() {
            try {
                setCategories((await api.admin.salesTrainer.listQuestionCategories()).items);
            } catch (loadError) {
                toast.error(getApiErrorMessage(loadError));
            } finally {
                setIsLoading(false);
            }
        }
        void loadCategories();
    }, [toast]);

    async function handleSubmit(payload: SalesTrainerQuestionCreateRequest) {
        setIsSubmitting(true);
        try {
            const question = await api.admin.salesTrainer.createQuestion(payload);
            toast.success("题目已创建");
            router.push(`/admin/sales-trainer/questions/${question.question_id}/edit`);
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/questions"
            title="新建销售题目"
            description="业务字段会由后端转换成标准 scoring_criteria，不需要手写 JSON。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在加载分类...</div>
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
