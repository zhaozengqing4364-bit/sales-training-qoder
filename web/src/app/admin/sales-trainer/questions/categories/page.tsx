"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerQuestionCategory } from "@/lib/api/types";

export default function SalesTrainerQuestionCategoriesPage() {
    const pathname = usePathname();
    const toast = useToast();
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const loadCategories = useCallback(async () => {
        setIsLoading(true);
        try {
            setCategories((await api.admin.salesTrainer.listQuestionCategories()).items);
        } catch (loadError) {
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [toast]);

    useEffect(() => {
        void loadCategories();
    }, [loadCategories]);

    async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!name.trim()) return;
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.createQuestionCategory({
                name: name.trim(),
                description: description.trim() || null,
            });
            setName("");
            setDescription("");
            toast.success("分类已创建");
            await loadCategories();
        } catch (submitError) {
            toast.error(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/questions"
            title="销售题库分类"
            description="分类只写入 sales_trainer 范围，不影响通用题库。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            <GlassCard className="space-y-4 p-6">
                <h2 className="text-lg font-bold text-slate-900">新建分类</h2>
                <form className="grid gap-3 md:grid-cols-[1fr_2fr_auto]" onSubmit={(event) => void handleCreate(event)}>
                    <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="分类名称" disabled={isSubmitting} />
                    <Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="分类说明" disabled={isSubmitting} />
                    <Button type="submit" disabled={isSubmitting || !name.trim()}>创建</Button>
                </form>
            </GlassCard>

            <GlassCard className="overflow-hidden p-0">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                            <th className="px-6 py-4">名称</th>
                            <th className="px-6 py-4">说明</th>
                            <th className="px-6 py-4">范围</th>
                            <th className="px-6 py-4">更新时间</th>
                        </tr>
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr><td colSpan={4} className="px-6 py-10 text-center text-slate-500">正在加载分类...</td></tr>
                        ) : categories.length === 0 ? (
                            <tr><td colSpan={4} className="px-6 py-10 text-center text-slate-500">暂无分类</td></tr>
                        ) : categories.map((category) => (
                            <tr key={category.category_id} className="border-b border-slate-100 last:border-b-0">
                                <td className="px-6 py-4 font-medium text-slate-900">{category.name}</td>
                                <td className="px-6 py-4 text-slate-600">{category.description || "未填写"}</td>
                                <td className="px-6 py-4">{category.usage_scope}</td>
                                <td className="px-6 py-4">{new Date(category.updated_at).toLocaleString()}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </GlassCard>
        </AdminFormShell>
    );
}
