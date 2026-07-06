"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    SalesTrainerAdminCapabilities,
    SalesTrainerQuestionCategory,
} from "@/lib/api/types";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";

export default function SalesTrainerQuestionCategoriesPage() {
    const pathname = usePathname();
    const { error: showToastError, success: showToastSuccess } = useToast();
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessCategories = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

    const loadCapabilities = useCallback(async () => {
        setIsCapabilityLoading(true);
        setCapabilityError(null);
        try {
            setAdminCapabilities(await api.admin.salesTrainer.getCapabilities());
        } catch (error) {
            setAdminCapabilities(null);
            setCapabilityError(getApiErrorMessage(error));
        } finally {
            setIsCapabilityLoading(false);
        }
    }, []);

    const fetchCategories = useCallback(async () => {
        return (await api.admin.salesTrainer.listQuestionCategories()).items;
    }, []);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    const loadCategories = useCallback(async () => {
        if (!canAccessCategories) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            setCategories(await fetchCategories());
        } catch (loadError) {
            const message = getApiErrorMessage(loadError);
            setCategories([]);
            setLoadError(message);
            showToastError(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessCategories, fetchCategories, showToastError]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessCategories) {
            setCategories([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadCategories();
    }, [canAccessCategories, isCapabilityLoading, loadCategories]);

    async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canAccessCategories || !name.trim()) return;
        setIsSubmitting(true);
        try {
            await api.admin.salesTrainer.createQuestionCategory({
                name: name.trim(),
                description: description.trim() || null,
            });
            setName("");
            setDescription("");
            showToastSuccess("分类已创建");
            await loadCategories();
        } catch (submitError) {
            showToastError(getApiErrorMessage(submitError));
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/questions"
            title="题目分类"
            description="分类只是正式题目的管理维度；学员小测按已发布题目和能力点抽题，不按分类抽题。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <div className="py-12 text-center text-sm text-slate-500">正在校验题库管理权限...</div>
            ) : capabilityError || !canAccessCategories ? (
                <AdminLoadErrorCard
                    title="题目分类权限不足"
                    description="当前页不会在权限未确认时加载分类或开放新建分类表单。请联系管理员开通题库管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="分类加载失败"
                    description="当前页不会在分类依赖读取失败时开放新建分类表单，避免把权限或接口异常伪装成空列表。"
                    message={loadError}
                    retryLabel="重新加载分类"
                    onRetry={() => void loadCategories()}
                />
            ) : (
                <>
                    <GlassCard className="space-y-4 p-6">
                        <h2 className="text-lg font-bold text-slate-900">新建分类</h2>
                        <p className="text-sm leading-6 text-slate-500">
                            分类用于运营筛选、审核入库和后续维护，不是学员端的组卷规则。要检查小测会抽到哪些题，请使用“小测预览”。
                        </p>
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
                                        <td className="px-6 py-4">
                                            {category.usage_scope === "sales_trainer" ? "新人训练路径" : category.usage_scope}
                                        </td>
                                        <td className="px-6 py-4">{new Date(category.updated_at).toLocaleString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </GlassCard>
                </>
            )}
        </AdminFormShell>
    );
}
