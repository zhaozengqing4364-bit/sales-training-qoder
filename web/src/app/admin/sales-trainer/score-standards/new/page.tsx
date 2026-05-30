"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { SalesTrainerScorePromptForm } from "@/components/admin/sales-trainer/score-prompt-form";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioScorePromptCreateRequest } from "@/lib/api/types";

export default function NewSalesTrainerScoreStandardPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [isSubmitting, setIsSubmitting] = useState(false);

    async function handleSubmit(payload: SalesTrainerAudioScorePromptCreateRequest) {
        setIsSubmitting(true);
        try {
            const result = await api.admin.salesTrainer.createScorePrompt(payload);
            toast.success("录音评分标准已创建");
            router.push(`/admin/sales-trainer/score-standards/${result.prompt_id}/edit`);
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/score-standards"
            title="新建录音评分标准"
            description="后续评分单元通过 published 评分标准绑定。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            <SalesTrainerScorePromptForm
                mode="create"
                isSubmitting={isSubmitting}
                onSubmit={(payload) => void handleSubmit(payload as SalesTrainerAudioScorePromptCreateRequest)}
            />
        </AdminFormShell>
    );
}
