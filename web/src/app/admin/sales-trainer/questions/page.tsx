"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerQuestion, SalesTrainerQuestionCategory } from "@/lib/api/types";

type ConfirmState =
    | { type: "publish"; question: SalesTrainerQuestion }
    | { type: "archive"; question: SalesTrainerQuestion }
    | null;

function typeLabel(type: SalesTrainerQuestion["question_type"]): string {
    const labels = {
        single_choice: "单选题",
        multiple_choice: "多选题",
        true_false: "判断题",
        short_answer: "简答题",
    };
    return labels[type];
}

export default function SalesTrainerQuestionsPage() {
    const pathname = usePathname();
    const router = useRouter();
    const toast = useToast();
    const [questions, setQuestions] = useState<SalesTrainerQuestion[]>([]);
    const [categories, setCategories] = useState<SalesTrainerQuestionCategory[]>([]);
    const [categoryId, setCategoryId] = useState("");
    const [status, setStatus] = useState("");
    const [difficulty, setDifficulty] = useState("");
    const [tag, setTag] = useState("");
    const [isLoading, setIsLoading] = useState(true);
    const [isOperating, setIsOperating] = useState(false);
    const [confirmState, setConfirmState] = useState<ConfirmState>(null);

    const categoryNameById = useMemo(
        () => new Map(categories.map((category) => [category.category_id, category.name])),
        [categories],
    );

    const loadData = useCallback(async () => {
        setIsLoading(true);
        try {
            const [questionResult, categoryResult] = await Promise.all([
                api.admin.salesTrainer.listQuestions({
                    category_id: categoryId || undefined,
                    status: status || undefined,
                    difficulty: difficulty || undefined,
                    tag: tag || undefined,
                }),
                api.admin.salesTrainer.listQuestionCategories(),
            ]);
            setQuestions(questionResult.items);
            setCategories(categoryResult.items);
        } catch (loadError) {
            toast.error(getApiErrorMessage(loadError));
        } finally {
            setIsLoading(false);
        }
    }, [categoryId, difficulty, status, tag, toast]);

    useEffect(() => {
        void loadData();
    }, [loadData]);

    async function handleConfirm() {
        if (!confirmState) return;
        setIsOperating(true);
        try {
            if (confirmState.type === "publish") {
                await api.admin.salesTrainer.publishQuestion(confirmState.question.question_id);
                toast.success("题目已发布");
            } else {
                await api.admin.salesTrainer.archiveQuestion(confirmState.question.question_id);
                toast.success("题目已归档");
            }
            setConfirmState(null);
            await loadData();
        } catch (operateError) {
            toast.error(getApiErrorMessage(operateError));
        } finally {
            setIsOperating(false);
        }
    }

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="销售题库"
                    description="销售训练专用题库，底层复用通用题库数据，但只读写 sales_trainer 范围。"
                    primaryAction={(
                        <div className="flex flex-wrap gap-2">
                            <Button variant="outline" onClick={() => router.push("/admin/sales-trainer/questions/categories")}>分类管理</Button>
                            <Button onClick={() => router.push("/admin/sales-trainer/questions/new")}>新建题目</Button>
                        </div>
                    )}
                    secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} />}
                />
            )}
        >
            <ConfirmDialog
                open={Boolean(confirmState)}
                onOpenChange={(open) => !open && setConfirmState(null)}
                title={confirmState?.type === "publish" ? "发布题目" : "归档题目"}
                description={confirmState?.question.title || ""}
                confirmText={confirmState?.type === "publish" ? "确认发布" : "确认归档"}
                onConfirm={() => void handleConfirm()}
                isLoading={isOperating}
            />

            <GlassCard className="grid gap-3 p-4 md:grid-cols-5">
                <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm">
                    <option value="">全部分类</option>
                    {categories.map((category) => <option key={category.category_id} value={category.category_id}>{category.name}</option>)}
                </select>
                <select value={status} onChange={(event) => setStatus(event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm">
                    <option value="">全部状态</option>
                    <option value="draft">draft</option>
                    <option value="published">published</option>
                    <option value="archived">archived</option>
                </select>
                <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm">
                    <option value="">全部难度</option>
                    <option value="easy">简单</option>
                    <option value="medium">中等</option>
                    <option value="hard">困难</option>
                </select>
                <Input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="标签筛选" />
                <Button variant="outline" onClick={() => void loadData()}>刷新</Button>
            </GlassCard>

            <GlassCard className="overflow-hidden p-0">
                <div className="overflow-x-auto">
                    <table className="min-w-[760px] text-sm">
                        <thead>
                            <tr className="border-b border-slate-100 text-left text-slate-500">
                                <th className="px-6 py-4">题目</th>
                                <th className="px-6 py-4">题型</th>
                                <th className="px-6 py-4">分类</th>
                                <th className="px-6 py-4">难度</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={6} className="px-6 py-10 text-center text-slate-500">正在加载题目...</td></tr>
                            ) : questions.length === 0 ? (
                                <tr><td colSpan={6} className="px-6 py-10 text-center text-slate-500">暂无题目</td></tr>
                            ) : questions.map((question) => (
                                <tr key={question.question_id} className="border-b border-slate-100 last:border-b-0">
                                    <td className="px-6 py-4">
                                        <p className="font-medium text-slate-900">{question.title}</p>
                                        <p className="mt-1 line-clamp-2 text-xs text-slate-500">{question.stem}</p>
                                    </td>
                                    <td className="px-6 py-4">{typeLabel(question.question_type)}</td>
                                    <td className="px-6 py-4">{categoryNameById.get(question.category_id) || question.category_id}</td>
                                    <td className="px-6 py-4">{question.difficulty}</td>
                                    <td className="px-6 py-4"><Badge className="bg-slate-100 text-slate-700">{question.status}</Badge></td>
                                    <td className="px-6 py-4">
                                        <div className="flex flex-wrap gap-2">
                                            <Button variant="outline" size="sm" onClick={() => router.push(`/admin/sales-trainer/questions/${question.question_id}/edit`)}>编辑</Button>
                                            {question.status !== "published" ? (
                                                <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "publish", question })}>发布</Button>
                                            ) : null}
                                            {question.status !== "archived" ? (
                                                <Button variant="outline" size="sm" onClick={() => setConfirmState({ type: "archive", question })}>归档</Button>
                                            ) : null}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </GlassCard>
        </AdminIndexShell>
    );
}
