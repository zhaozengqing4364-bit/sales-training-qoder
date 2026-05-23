"use client";

import { useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { TemplateForm } from "@/components/admin/curriculum-practice/template-form";

export default function NewPracticeTemplatePage() {
    const router = useRouter();

    return (
        <AdminFormShell
            backHref="/admin/curriculum-practice/templates"
            backLabel="返回列表"
            title="新建课程训练模板"
            description="配置智能体、Persona、评分规则与可选 CurriculumPlan 阶段图。"
        >
            <TemplateForm
                mode="create"
                onSaved={() => router.push("/admin/curriculum-practice/templates")}
                onCancel={() => router.push("/admin/curriculum-practice/templates")}
            />
        </AdminFormShell>
    );
}
