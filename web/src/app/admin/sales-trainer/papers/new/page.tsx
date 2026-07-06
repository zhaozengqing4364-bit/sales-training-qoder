"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { AdminLoadErrorCard } from "@/components/admin/sales-trainer/admin-load-error-card";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import { isSalesTrainerAdminPathAllowedForCapabilities } from "@/lib/sales-trainer/routes";
import type { SalesTrainerAdminCapabilities, SalesTrainerQuestion } from "@/lib/api/types";
import { PaperQuestionPicker } from "../paper-question-picker";
import {
    BUSINESS_SKILLS_MODULE_KEY,
    buildBusinessSkillsPaperKey,
    buildPaperQuestionBindings,
} from "../paper-form-model";

export default function NewcomerPaperNewPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [selectedQuestionIds, setSelectedQuestionIds] = useState<string[]>([]);
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [points, setPoints] = useState("10");
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [adminCapabilities, setAdminCapabilities] = useState<SalesTrainerAdminCapabilities | null>(null);
    const [capabilityError, setCapabilityError] = useState<string | null>(null);
    const [isCapabilityLoading, setIsCapabilityLoading] = useState(true);
    const canAccessPaperForm = isSalesTrainerAdminPathAllowedForCapabilities(pathname, adminCapabilities);

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

    const loadQuestions = useCallback(async () => {
        if (!canAccessPaperForm) {
            return;
        }
        setIsLoading(true);
        setLoadError(null);
        try {
            const result = await api.admin.salesTrainer.listQuestions({
                status: "published",
                tag: NEWCOMER_QUESTION_TAG,
            });
            setQuestions(result.items);
        } catch (error) {
            const message = getApiErrorMessage(error);
            setQuestions([]);
            setLoadError(message);
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    }, [canAccessPaperForm, toast]);

    useEffect(() => {
        void loadCapabilities();
    }, [loadCapabilities]);

    useEffect(() => {
        if (isCapabilityLoading) {
            return;
        }
        if (!canAccessPaperForm) {
            setQuestions([]);
            setLoadError(null);
            setIsLoading(false);
            return;
        }
        void loadQuestions();
    }, [canAccessPaperForm, isCapabilityLoading, loadQuestions]);

    function toggleQuestion(questionId: string) {
        setSelectedQuestionIds((current) =>
            current.includes(questionId)
                ? current.filter((item) => item !== questionId)
                : [...current, questionId],
        );
    }

    async function createPaper(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canAccessPaperForm) {
            return;
        }
        const parsedPoints = Number(points);
        if (!title.trim()) {
            toast.error("考卷标题不能为空。");
            return;
        }
        if (selectedQuestionIds.length === 0) {
            toast.error("请至少选择一道题目。");
            return;
        }
        if (!Number.isFinite(parsedPoints) || parsedPoints <= 0) {
            toast.error("题目分值必须大于 0。");
            return;
        }
        setIsSubmitting(true);
        try {
            await api.admin.newcomerTraining.createPaper({
                paper_key: buildBusinessSkillsPaperKey(Date.now()),
                title: title.trim(),
                description: description.trim() || null,
                module_key: BUSINESS_SKILLS_MODULE_KEY,
                questions: buildPaperQuestionBindings(selectedQuestionIds, parsedPoints),
            });
            toast.success("商务技巧考卷已创建");
            router.push("/admin/sales-trainer/papers");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/papers"
            title="新建商务技巧考卷"
            description="从新人训练路径正式题目库选择题目组卷；内部考卷编号由系统自动生成。"
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={adminCapabilities} />}
        >
            {isCapabilityLoading ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">正在校验内容管理权限...</GlassCard>
            ) : capabilityError || !canAccessPaperForm ? (
                <AdminLoadErrorCard
                    title="考卷管理权限不足"
                    description="当前页不会在权限未确认时加载题库或开放新建考卷表单。请联系管理员开通内容管理权限后重试。"
                    message={capabilityError}
                    retryLabel="重新校验权限"
                    onRetry={() => void loadCapabilities()}
                />
            ) : loadError ? (
                <AdminLoadErrorCard
                    title="题库加载失败"
                    description="当前页不会在正式题库依赖缺失时开放新建考卷表单。请核对权限、题库发布状态或后端服务状态后重试。"
                    message={loadError}
                    retryLabel="重新加载题库"
                    onRetry={() => void loadQuestions()}
                />
            ) : (
            <form className="space-y-6" onSubmit={(event) => void createPaper(event)}>
                <GlassCard className="space-y-4 p-6">
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="paper-title">考卷标题</label>
                            <Input id="paper-title" value={title} onChange={(event) => setTitle(event.target.value)} disabled={isSubmitting} placeholder="例如 商务礼仪入门考卷" />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="paper-points">每题默认分值</label>
                            <Input id="paper-points" type="number" min={1} value={points} onChange={(event) => setPoints(event.target.value)} disabled={isSubmitting} />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="paper-description">考卷说明</label>
                            <textarea id="paper-description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={isSubmitting} rows={3} className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm" />
                        </div>
                    </div>
                </GlassCard>
                <PaperQuestionPicker
                    isLoading={isLoading}
                    questions={questions}
                    selectedQuestionIds={selectedQuestionIds}
                    toggleQuestion={toggleQuestion}
                />
                <div className="flex justify-end">
                    <Button type="submit" disabled={isSubmitting} className="rounded-full bg-slate-900 text-white">
                        创建考卷
                    </Button>
                </div>
            </form>
            )}
        </AdminFormShell>
    );
}
