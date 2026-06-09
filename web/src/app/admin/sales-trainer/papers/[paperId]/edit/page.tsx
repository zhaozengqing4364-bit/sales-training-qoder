"use client";

import { useEffect, useState } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { NewcomerExamPaper, SalesTrainerQuestion } from "@/lib/api/types";
import { NEWCOMER_QUESTION_TAG } from "@/lib/sales-trainer/question-scope";
import {
    BUSINESS_SKILLS_MODULE_KEY,
    buildPaperQuestionBindings,
    defaultPaperQuestionPoints,
    selectedPaperQuestionIds,
} from "../../paper-form-model";
import { PaperQuestionPicker } from "../../paper-question-picker";

export default function NewcomerPaperEditPage() {
    const params = useParams();
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const paperId = paramValue(params.paperId);
    const [paper, setPaper] = useState<NewcomerExamPaper | null>(null);
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [selectedQuestionIds, setSelectedQuestionIds] = useState<string[]>([]);
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [points, setPoints] = useState("10");
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        async function loadPaper() {
            setIsLoading(true);
            try {
                const [paperResult, questionResult] = await Promise.all([
                    api.admin.newcomerTraining.listPapers({ include_archived: true, limit: 100 }),
                    api.admin.salesTrainer.listQuestions({ status: "published", tag: NEWCOMER_QUESTION_TAG }),
                ]);
                const matchedPaper = paperResult.items.find((item) => item.paper_id === paperId) ?? null;
                setPaper(matchedPaper);
                setQuestions(questionResult.items);
                setTitle(matchedPaper?.title ?? "");
                setDescription(matchedPaper?.description ?? "");
                setPoints(matchedPaper ? defaultPaperQuestionPoints(matchedPaper) : "10");
                setSelectedQuestionIds(matchedPaper ? selectedPaperQuestionIds(matchedPaper) : []);
            } catch (error) {
                setPaper(null);
                setQuestions([]);
                toast.error(getApiErrorMessage(error));
            } finally {
                setIsLoading(false);
            }
        }
        void loadPaper();
    }, [paperId, toast]);

    function toggleQuestion(questionId: string) {
        setSelectedQuestionIds((current) =>
            current.includes(questionId)
                ? current.filter((item) => item !== questionId)
                : [...current, questionId],
        );
    }

    async function savePaper(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const parsedPoints = Number(points);
        if (!paperId || !paper) {
            toast.error("考卷不存在，请返回列表重新选择。");
            return;
        }
        if (paper.status === "archived") {
            toast.error("归档考卷只用于审计追溯，不能继续修改。");
            return;
        }
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
            await api.admin.newcomerTraining.updatePaper(paperId, {
                title: title.trim(),
                description: description.trim() || null,
                module_key: BUSINESS_SKILLS_MODULE_KEY,
                questions: buildPaperQuestionBindings(selectedQuestionIds, parsedPoints),
            });
            toast.success(paper.status === "published"
                ? "已保存为新修订，发布并生效后只影响后续学员"
                : "考卷草稿已保存");
            router.push("/admin/sales-trainer/papers");
        } catch (error) {
            toast.error(getApiErrorMessage(error));
            setIsSubmitting(false);
        }
    }

    return (
        <AdminFormShell
            backHref="/admin/sales-trainer/papers"
            title={paper?.status === "published" ? "编辑商务技巧考卷" : "编辑商务技巧考卷草稿"}
            description={paper?.status === "published"
                ? "保存后生成新修订；发布并生效前，学员仍使用当前已发布版本。"
                : "草稿保存后可发布并生效；历史考试记录会继续保留提交时快照。"}
            actions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
        >
            {isLoading ? (
                <GlassCard className="p-8 text-center text-sm text-slate-500">正在加载考卷草稿...</GlassCard>
            ) : paper?.status === "archived" ? (
                <GlassCard className="space-y-3 p-6">
                    <h2 className="text-lg font-bold text-slate-900">归档考卷只读</h2>
                    <p className="text-sm text-slate-600">归档版本用于审计追溯；需要恢复时请在历史版本中回滚。</p>
                </GlassCard>
            ) : (
                <form className="space-y-6" onSubmit={(event) => void savePaper(event)}>
                    <GlassCard className="space-y-4 p-6">
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-slate-700" htmlFor="paper-title">考卷标题</label>
                                <Input id="paper-title" value={title} onChange={(event) => setTitle(event.target.value)} disabled={isSubmitting} />
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
                        isLoading={false}
                        questions={questions}
                        selectedQuestionIds={selectedQuestionIds}
                        toggleQuestion={toggleQuestion}
                    />
                    <div className="flex justify-end">
                        <Button type="submit" disabled={isSubmitting} className="rounded-full bg-slate-900 text-white">
                            {paper?.status === "published" ? "保存修改" : "保存草稿"}
                        </Button>
                    </div>
                </form>
            )}
        </AdminFormShell>
    );
}

function paramValue(value: string | string[] | undefined): string {
    if (typeof value === "string") {
        return value;
    }
    return value?.[0] ?? "";
}
