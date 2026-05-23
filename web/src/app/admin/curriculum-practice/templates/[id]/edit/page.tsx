"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { TemplateForm } from "@/components/admin/curriculum-practice/template-form";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PracticeTemplateRecord } from "@/lib/api/types";

export default function EditPracticeTemplatePage() {
    const router = useRouter();
    const params = useParams();
    const templateId = params.id as string;
    const [template, setTemplate] = useState<PracticeTemplateRecord | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        void (async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await api.admin.listPracticeTemplates();
                const found = response.items.find((item) => item.template_id === templateId);
                if (!found) {
                    setError("模板不存在或已被删除。");
                    return;
                }
                if (found.status !== "draft") {
                    setError("仅草稿模板可编辑。");
                    return;
                }
                setTemplate(found);
            } catch (err) {
                setError(getApiErrorMessage(err));
            } finally {
                setLoading(false);
            }
        })();
    }, [templateId]);

    if (loading) {
        return <GlassCard className="p-8 text-slate-600">正在加载模板...</GlassCard>;
    }

    if (error || !template) {
        return (
            <GlassCard className="space-y-4 p-8">
                <p className="text-red-700">{error || "无法加载模板"}</p>
                <Button variant="outline" onClick={() => router.push("/admin/curriculum-practice/templates")}>返回列表</Button>
            </GlassCard>
        );
    }

    return (
        <AdminFormShell
            backHref="/admin/curriculum-practice/templates"
            backLabel="返回列表"
            title={`编辑：${template.name}`}
            description="草稿模板编辑完成后可返回列表发布。"
        >
            <TemplateForm
                mode="edit"
                templateId={templateId}
                initialTemplate={template}
                onSaved={() => router.push("/admin/curriculum-practice/templates")}
                onCancel={() => router.push("/admin/curriculum-practice/templates")}
            />
        </AdminFormShell>
    );
}
