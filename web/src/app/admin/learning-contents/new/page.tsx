"use client";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { LearningContentCreateForm } from "@/components/admin/learning-contents/learning-content-create-form";

export default function NewLearningContentPage() {
    return (
        <AdminFormShell
            backHref="/admin/learning-contents"
            backLabel="返回列表"
            title="新建学习内容"
            description="创建草稿后可在详情页继续编辑章节与发布配置。"
        >
            <LearningContentCreateForm />
        </AdminFormShell>
    );
}
