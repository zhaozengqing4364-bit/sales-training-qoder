"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Archive, Edit2, Filter, Plus, RefreshCcw } from "lucide-react";

import { AdminIndexShell, AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { api } from "@/lib/api/client";
import type { QuestionCategory, QuestionItem } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

const STATUS_LABELS: Record<string, string> = { draft: "草稿", published: "已发布", archived: "已归档" };
const STATUS_VARIANTS: Record<string, "blue" | "green" | "gray" | "red"> = { draft: "blue", published: "green", archived: "gray" };
const DIFFICULTY_LABELS: Record<string, string> = { easy: "简单", medium: "中等", hard: "困难" };

type QuestionAction = { type: "publish" | "archive"; question: QuestionItem } | null;

export default function TestBankPage() {
    const router = useRouter();
    const toast = useToast();
    const [categories, setCategories] = useState<QuestionCategory[]>([]);
    const [questions, setQuestions] = useState<QuestionItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [filterCategoryId, setFilterCategoryId] = useState("");
    const [filterDifficulty, setFilterDifficulty] = useState("");
    const [filterStatus, setFilterStatus] = useState("");
    const [filterTag, setFilterTag] = useState("");
    const [actionError, setActionError] = useState<string | null>(null);
    const [questionAction, setQuestionAction] = useState<QuestionAction>(null);

    const loadCategories = useCallback(async () => {
        const result = await api.testBank.listCategories();
        setCategories(result.items || []);
    }, []);

    const loadQuestions = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const filters: Record<string, string> = {};
            if (filterCategoryId) filters.category_id = filterCategoryId;
            if (filterDifficulty) filters.difficulty = filterDifficulty;
            if (filterStatus) filters.status = filterStatus;
            if (filterTag) filters.tag = filterTag;
            const result = await api.testBank.listQuestions(Object.keys(filters).length > 0 ? filters : undefined);
            setQuestions(result.items || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "加载题目失败");
            setQuestions([]);
        } finally {
            setLoading(false);
        }
    }, [filterCategoryId, filterDifficulty, filterStatus, filterTag]);

    useEffect(() => { void loadCategories(); }, [loadCategories]);
    useEffect(() => { void loadQuestions(); }, [loadQuestions]);

    const getCategoryName = (categoryId: string) => categories.find((c) => c.category_id === categoryId)?.name || categoryId;

    const handleConfirmQuestionAction = async () => {
        const action = questionAction;
        setQuestionAction(null);
        if (!action) return;
        setActionError(null);
        try {
            if (action.type === "publish") await api.testBank.publishQuestion(action.question.question_id);
            else await api.testBank.archiveQuestion(action.question.question_id);
            toast.success(action.type === "publish" ? "已发布" : "已归档");
            void loadQuestions();
        } catch (err) {
            setActionError(err instanceof Error ? err.message : "操作失败");
        }
    };

    return (
        <AdminIndexShell
            header={(
                <AdminPageHeader
                    title="题库管理"
                    description="浏览与筛选题目；创建、分类与批量导入请使用独立入口。"
                    primaryAction={<Button className="rounded-full" onClick={() => router.push("/admin/test-bank/questions/new")}><Plus className="mr-2 h-4 w-4" />新建题目</Button>}
                    secondaryActions={(
                        <>
                            <Button variant="outline" className="rounded-full" onClick={() => router.push("/admin/test-bank/categories")}>分类管理</Button>
                            <Button variant="outline" className="rounded-full" onClick={() => router.push("/admin/test-bank/import")}>批量导入</Button>
                            <Button variant="outline" className="rounded-full" onClick={() => { void loadCategories(); void loadQuestions(); }}><RefreshCcw className="mr-2 h-4 w-4" />刷新</Button>
                        </>
                    )}
                />
            )}
        >
            <ConfirmDialog open={!!questionAction} onOpenChange={(open) => !open && setQuestionAction(null)} title={questionAction?.type === "archive" ? "归档题目" : "发布题目"} description={questionAction ? (questionAction.type === "archive" ? `确定要归档「${questionAction.question.title}」吗？` : `确定要发布「${questionAction.question.title}」吗？`) : ""} confirmText={questionAction?.type === "archive" ? "确认归档" : "确认发布"} variant={questionAction?.type === "archive" ? "warning" : "danger"} onConfirm={() => void handleConfirmQuestionAction()} />
            <GlassCard className="p-6">
                <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-900"><Filter className="h-5 w-5" />题目列表</h2>
                <div className="mb-4 flex flex-wrap items-end gap-2">
                    <select className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm" value={filterCategoryId} onChange={(e) => setFilterCategoryId(e.target.value)} aria-label="分类"><option value="">全部分类</option>{categories.map((c) => (<option key={c.category_id} value={c.category_id}>{c.name}</option>))}</select>
                    <select className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm" value={filterDifficulty} onChange={(e) => setFilterDifficulty(e.target.value)} aria-label="难度"><option value="">全部难度</option><option value="easy">简单</option><option value="medium">中等</option><option value="hard">困难</option></select>
                    <select className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} aria-label="状态"><option value="">全部状态</option><option value="draft">草稿</option><option value="published">已发布</option><option value="archived">已归档</option></select>
                    <input type="text" placeholder="标签筛选..." className="h-10 w-32 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm" value={filterTag} onChange={(e) => setFilterTag(e.target.value)} />
                </div>
                {actionError && <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{actionError}</div>}
                {error && <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
                {loading ? <div className="py-8 text-center text-slate-400">加载题目中...</div> : questions.length === 0 ? <div className="py-8 text-center text-slate-400">暂无题目</div> : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="border-b border-slate-100 text-xs font-bold uppercase text-slate-400"><tr><th className="px-4 py-3">标题</th><th className="px-4 py-3">分类</th><th className="px-4 py-3">难度</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">标签</th><th className="px-4 py-3">版本</th><th className="px-4 py-3 text-right">操作</th></tr></thead>
                            <tbody className="divide-y divide-slate-100">
                                {questions.map((q) => (
                                    <tr key={q.question_id}>
                                        <td className="px-4 py-3 font-medium">{q.title}</td>
                                        <td className="px-4 py-3 text-slate-500">{q.category_name || getCategoryName(q.category_id)}</td>
                                        <td className="px-4 py-3"><Badge variant={q.difficulty === "easy" ? "green" : q.difficulty === "hard" ? "red" : "blue"}>{DIFFICULTY_LABELS[q.difficulty] || q.difficulty}</Badge></td>
                                        <td className="px-4 py-3"><Badge variant={STATUS_VARIANTS[q.status] || "gray"}>{STATUS_LABELS[q.status] || q.status}</Badge></td>
                                        <td className="max-w-[120px] truncate px-4 py-3 text-slate-500">{q.tags.join(", ") || "-"}</td>
                                        <td className="px-4 py-3 text-slate-500">v{q.version}</td>
                                        <td className="px-4 py-3 text-right">
                                            <div className="flex justify-end gap-1">
                                                {q.status === "draft" && <Button variant="ghost" size="icon" onClick={() => router.push(`/admin/test-bank/questions/${q.question_id}/edit`)}><Edit2 className="h-4 w-4" /></Button>}
                                                {q.status !== "published" && <Button variant="ghost" size="sm" onClick={() => setQuestionAction({ type: "publish", question: q })}>发布</Button>}
                                                {q.status !== "archived" && <Button variant="ghost" size="sm" onClick={() => setQuestionAction({ type: "archive", question: q })}><Archive className="mr-1 h-3 w-3" />归档</Button>}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </GlassCard>
        </AdminIndexShell>
    );
}
