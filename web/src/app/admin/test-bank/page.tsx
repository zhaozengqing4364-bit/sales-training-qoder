"use client";

import { useEffect, useState } from "react";
import { RefreshCcw, Plus, Edit2, Trash2, BookOpen, Filter, Archive, X } from "lucide-react";

import { api } from "@/lib/api/client";
import type { QuestionCategory, QuestionItem, CreateCategoryRequest, UpdateCategoryRequest } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

const STATUS_LABELS: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
};

const STATUS_VARIANTS: Record<string, "blue" | "green" | "gray" | "red"> = {
    draft: "blue",
    published: "green",
    archived: "gray",
};

const DIFFICULTY_LABELS: Record<string, string> = {
    easy: "简单",
    medium: "中等",
    hard: "困难",
};

function parseScoringCriteria(raw: string): Record<string, unknown> | null {
    const trimmed = raw.trim();
    if (!trimmed) return {};
    try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed !== "object" || Array.isArray(parsed) || parsed === null) {
            return null;
        }
        return parsed as Record<string, unknown>;
    } catch {
        return null;
    }
}

export default function TestBankPage() {
    const toast = useToast();

    // ── Categories ──
    const [categories, setCategories] = useState<QuestionCategory[]>([]);
    const [catLoading, setCatLoading] = useState(true);
    const [catError, setCatError] = useState<string | null>(null);
    const [newCatName, setNewCatName] = useState("");
    const [newCatParentId, setNewCatParentId] = useState("");
    const [catCreating, setCatCreating] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<QuestionCategory | null>(null);
    const [catDeleting, setCatDeleting] = useState(false);
    const [catDeleteError, setCatDeleteError] = useState<string | null>(null);

    // ── Category Edit ──
    const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
    const [editCatName, setEditCatName] = useState("");
    const [editCatDescription, setEditCatDescription] = useState("");
    const [editCatParentId, setEditCatParentId] = useState("");
    const [editCatOrderIndex, setEditCatOrderIndex] = useState("0");
    const [catSaving, setCatSaving] = useState(false);

    // ── Questions ──
    const [questions, setQuestions] = useState<QuestionItem[]>([]);
    const [qLoading, setQLoading] = useState(true);
    const [qError, setQError] = useState<string | null>(null);
    const [filterCategoryId, setFilterCategoryId] = useState("");
    const [filterDifficulty, setFilterDifficulty] = useState("");
    const [filterStatus, setFilterStatus] = useState("");
    const [filterTag, setFilterTag] = useState("");
    const [actionError, setActionError] = useState<string | null>(null);

    // ── Question Form ──
    const [showForm, setShowForm] = useState(false);
    const [editingQuestion, setEditingQuestion] = useState<QuestionItem | null>(null);
    const [formTitle, setFormTitle] = useState("");
    const [formStem, setFormStem] = useState("");
    const [formReferenceAnswer, setFormReferenceAnswer] = useState("");
    const [formCategoryId, setFormCategoryId] = useState("");
    const [formDifficulty, setFormDifficulty] = useState<"easy" | "medium" | "hard">("medium");
    const [formTags, setFormTags] = useState("");
    const [formScoringDimensions, setFormScoringDimensions] = useState("");
    const [formScoringCriteria, setFormScoringCriteria] = useState("");
    const [formSafetyFlagged, setFormSafetyFlagged] = useState(false);
    const [formDepartment, setFormDepartment] = useState("");
    const [formSubmitting, setFormSubmitting] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);

    const loadCategories = async () => {
        setCatLoading(true);
        setCatError(null);
        try {
            const result = await api.testBank.listCategories();
            setCategories(result.items || []);
        } catch (err) {
            setCatError(err instanceof Error ? err.message : "加载分类失败");
        } finally {
            setCatLoading(false);
        }
    };

    const loadQuestions = async () => {
        setQLoading(true);
        setQError(null);
        try {
            const filters: Record<string, string> = {};
            if (filterCategoryId) filters.category_id = filterCategoryId;
            if (filterDifficulty) filters.difficulty = filterDifficulty;
            if (filterStatus) filters.status = filterStatus;
            if (filterTag) filters.tag = filterTag;

            const result = await api.testBank.listQuestions(
                Object.keys(filters).length > 0 ? filters : undefined,
            );
            setQuestions(result.items || []);
        } catch (err) {
            setQError(err instanceof Error ? err.message : "加载题目失败");
            setQuestions([]);
        } finally {
            setQLoading(false);
        }
    };

    useEffect(() => {
        void loadCategories();
        void loadQuestions();
    }, []);

    useEffect(() => {
        void loadQuestions();
    }, [filterCategoryId, filterDifficulty, filterStatus, filterTag]);

    const handleCreateCategory = async () => {
        if (!newCatName.trim()) return;
        setCatCreating(true);
        setCatError(null);
        try {
            const payload: CreateCategoryRequest = { name: newCatName.trim() };
            if (newCatParentId) payload.parent_id = newCatParentId;
            await api.testBank.createCategory(payload);
            setNewCatName("");
            setNewCatParentId("");
            toast.success("分类创建成功");
            void loadCategories();
        } catch (err) {
            setCatError(err instanceof Error ? err.message : "创建分类失败");
        } finally {
            setCatCreating(false);
        }
    };

    const startEditCategory = (cat: QuestionCategory) => {
        setEditingCategoryId(cat.category_id);
        setEditCatName(cat.name);
        setEditCatDescription(cat.description || "");
        setEditCatParentId(cat.parent_id || "");
        setEditCatOrderIndex(String(cat.order_index));
    };

    const cancelEditCategory = () => {
        setEditingCategoryId(null);
    };

    const handleUpdateCategory = async () => {
        if (!editingCategoryId || !editCatName.trim()) return;
        setCatSaving(true);
        setCatError(null);
        try {
            const payload: UpdateCategoryRequest = {
                name: editCatName.trim(),
                description: editCatDescription.trim() || undefined,
                parent_id: editCatParentId || null,
            };
            if (editCatOrderIndex) {
                (payload as Record<string, unknown>).order_index = parseInt(editCatOrderIndex, 10) || 0;
            }
            await api.testBank.updateCategory(editingCategoryId, payload);
            toast.success("分类已更新");
            setEditingCategoryId(null);
            void loadCategories();
        } catch (err) {
            setCatError(err instanceof Error ? err.message : "更新分类失败");
        } finally {
            setCatSaving(false);
        }
    };

    const handleDeleteCategory = async () => {
        if (!deleteTarget) return;
        setCatDeleting(true);
        setCatDeleteError(null);
        try {
            await api.testBank.deleteCategory(deleteTarget.category_id);
            toast.success("删除成功");
            setDeleteTarget(null);
            void loadCategories();
        } catch (err) {
            const msg = err instanceof Error ? err.message : "删除失败";
            setCatDeleteError(msg);
        } finally {
            setCatDeleting(false);
        }
    };

    const startEditQuestion = (q: QuestionItem) => {
        setEditingQuestion(q);
        setFormTitle(q.title);
        setFormStem(q.stem);
        setFormReferenceAnswer(q.reference_answer || "");
        setFormCategoryId(q.category_id);
        setFormDifficulty(q.difficulty);
        setFormTags(q.tags.join(", "));
        setFormScoringDimensions(q.scoring_dimensions.join(", "));
        setFormScoringCriteria(JSON.stringify(q.scoring_criteria));
        setFormSafetyFlagged(q.safety_flagged);
        setFormDepartment(q.department || "");
        setFormError(null);
        setShowForm(true);
    };

    const resetForm = () => {
        setFormTitle("");
        setFormStem("");
        setFormReferenceAnswer("");
        setFormCategoryId("");
        setFormDifficulty("medium");
        setFormTags("");
        setFormScoringDimensions("");
        setFormScoringCriteria("");
        setFormSafetyFlagged(false);
        setFormDepartment("");
        setFormError(null);
        setEditingQuestion(null);
        setShowForm(false);
    };

    const handleSubmitQuestion = async () => {
        if (!formTitle.trim() || !formStem.trim() || !formCategoryId) {
            setFormError("标题、题干和分类为必填项");
            return;
        }

        const criteria = parseScoringCriteria(formScoringCriteria);
        if (criteria === null) {
            setFormError("评分标准格式无效，请输入有效的 JSON 对象");
            return;
        }

        setFormSubmitting(true);
        setFormError(null);
        try {
            const payload = {
                title: formTitle.trim(),
                stem: formStem.trim(),
                reference_answer: formReferenceAnswer.trim() || null,
                category_id: formCategoryId,
                difficulty: formDifficulty,
                tags: formTags.split(",").map((t) => t.trim()).filter(Boolean),
                scoring_dimensions: formScoringDimensions
                    .split(",")
                    .map((d) => d.trim())
                    .filter(Boolean),
                scoring_criteria: criteria,
                safety_flagged: formSafetyFlagged,
                department: formDepartment.trim() || null,
            };

            if (editingQuestion) {
                await api.testBank.updateQuestion(editingQuestion.question_id, payload);
                toast.success("题目已更新");
            } else {
                await api.testBank.createQuestion(payload);
                toast.success("题目已创建");
            }
            resetForm();
            void loadQuestions();
        } catch (err) {
            setFormError(err instanceof Error ? err.message : "保存失败");
        } finally {
            setFormSubmitting(false);
        }
    };

    const handlePublish = async (questionId: string) => {
        setActionError(null);
        try {
            await api.testBank.publishQuestion(questionId);
            toast.success("已发布");
            void loadQuestions();
        } catch (err) {
            setActionError(err instanceof Error ? err.message : "发布失败");
        }
    };

    const handleArchive = async (questionId: string) => {
        setActionError(null);
        try {
            await api.testBank.archiveQuestion(questionId);
            toast.success("已归档");
            void loadQuestions();
        } catch (err) {
            setActionError(err instanceof Error ? err.message : "归档失败");
        }
    };

    const getCategoryName = (categoryId: string) => {
        return categories.find((c) => c.category_id === categoryId)?.name || categoryId;
    };

    const getCategoryPath = (cat: QuestionCategory): string => {
        if (!cat.parent_id) return cat.name;
        const parent = categories.find((c) => c.category_id === cat.parent_id);
        return parent ? `${parent.name} > ${cat.name}` : cat.name;
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除分类"
                description={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDeleteCategory}
                isLoading={catDeleting}
            />

            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">题库管理</h1>
                    <p className="mt-1 text-slate-500">管理试题分类与题目</p>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        className="rounded-full"
                        onClick={() => { void loadCategories(); void loadQuestions(); }}
                    >
                        <RefreshCcw className="mr-2 h-4 w-4" /> 刷新
                    </Button>
                </div>
            </div>

            {/* ── Categories Section ── */}
            <GlassCard className="p-6">
                <h2 className="mb-4 text-lg font-bold text-slate-900 flex items-center gap-2">
                    <BookOpen className="h-5 w-5" /> 分类管理
                </h2>

                {/* Create Form */}
                <div className="mb-4 flex flex-wrap items-end gap-2">
                    <input
                        type="text"
                        placeholder="分类名称"
                        className="h-10 rounded-full border border-slate-200 bg-slate-50 px-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/10 w-48"
                        value={newCatName}
                        onChange={(e) => setNewCatName(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleCreateCategory()}
                    />
                    <select
                        className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm focus:border-blue-500 focus:outline-none"
                        value={newCatParentId}
                        onChange={(e) => setNewCatParentId(e.target.value)}
                    >
                        <option value="">无父分类</option>
                        {categories.map((c) => (
                            <option key={c.category_id} value={c.category_id}>{c.name}</option>
                        ))}
                    </select>
                    <Button
                        className="rounded-full"
                        onClick={handleCreateCategory}
                        disabled={catCreating || !newCatName.trim()}
                    >
                        <Plus className="mr-2 h-4 w-4" /> 新建分类
                    </Button>
                </div>

                {catError && (
                    <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{catError}</div>
                )}

                {catDeleteError && (
                    <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{catDeleteError}</div>
                )}

                {catLoading ? (
                    <div className="py-6 text-center text-slate-400">加载分类中...</div>
                ) : (
                    <div className="overflow-x-auto">
                        {categories.length === 0 ? (
                            <div className="py-6 text-center text-slate-400">暂无分类</div>
                        ) : (
                            <table className="w-full text-left text-sm">
                                <thead className="border-b border-slate-100 text-xs font-bold uppercase text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3">名称</th>
                                        <th className="px-4 py-3">描述</th>
                                        <th className="px-4 py-3">父分类</th>
                                        <th className="px-4 py-3">排序</th>
                                        <th className="px-4 py-3 text-right">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {categories.map((cat) => (
                                        <tr key={cat.category_id} className="transition-colors hover:bg-slate-50/50">
                                            {editingCategoryId === cat.category_id ? (
                                                <>
                                                    <td className="px-4 py-3">
                                                        <input
                                                            type="text"
                                                            placeholder="分类名称"
                                                            className="h-9 w-full rounded border border-slate-200 bg-white px-2 text-sm focus:border-blue-500 focus:outline-none"
                                                            value={editCatName}
                                                            onChange={(e) => setEditCatName(e.target.value)}
                                                        />
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <input
                                                            type="text"
                                                            placeholder="描述"
                                                            className="h-9 w-full rounded border border-slate-200 bg-white px-2 text-sm focus:border-blue-500 focus:outline-none"
                                                            value={editCatDescription}
                                                            onChange={(e) => setEditCatDescription(e.target.value)}
                                                        />
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <select
                                                            className="h-9 w-full rounded border border-slate-200 bg-white px-2 text-sm focus:border-blue-500 focus:outline-none"
                                                            value={editCatParentId}
                                                            onChange={(e) => setEditCatParentId(e.target.value)}
                                                        >
                                                            <option value="">无</option>
                                                            {categories.filter((c) => c.category_id !== cat.category_id).map((c) => (
                                                                <option key={c.category_id} value={c.category_id}>{c.name}</option>
                                                            ))}
                                                        </select>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <input
                                                            type="number"
                                                            className="h-9 w-16 rounded border border-slate-200 bg-white px-2 text-sm focus:border-blue-500 focus:outline-none"
                                                            value={editCatOrderIndex}
                                                            onChange={(e) => setEditCatOrderIndex(e.target.value)}
                                                        />
                                                    </td>
                                                    <td className="px-4 py-3 text-right">
                                                        <div className="flex justify-end gap-1">
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="rounded-full text-xs text-blue-600 hover:text-blue-800"
                                                                onClick={handleUpdateCategory}
                                                                disabled={catSaving}
                                                            >
                                                                保存
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="rounded-full text-slate-400 hover:text-slate-600"
                                                                onClick={cancelEditCategory}
                                                            >
                                                                <X className="h-4 w-4" />
                                                            </Button>
                                                        </div>
                                                    </td>
                                                </>
                                            ) : (
                                                <>
                                                    <td className="px-4 py-3 font-medium text-slate-900">{getCategoryPath(cat)}</td>
                                                    <td className="px-4 py-3 text-slate-500">{cat.description || "-"}</td>
                                                    <td className="px-4 py-3 text-slate-500">{cat.parent_id ? getCategoryName(cat.parent_id) : "-"}</td>
                                                    <td className="px-4 py-3 text-slate-500">{cat.order_index}</td>
                                                    <td className="px-4 py-3 text-right">
                                                        <div className="flex justify-end gap-1">
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="rounded-full text-slate-400 hover:text-blue-500"
                                                                onClick={() => startEditCategory(cat)}
                                                            >
                                                                <Edit2 className="h-4 w-4" />
                                                            </Button>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="rounded-full text-slate-400 hover:text-red-500"
                                                                onClick={() => setDeleteTarget(cat)}
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </div>
                                                    </td>
                                                </>
                                            )}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                )}
            </GlassCard>

            {/* ── Questions Section ── */}
            <GlassCard className="p-6">
                <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                        <Filter className="h-5 w-5" /> 题目管理
                    </h2>
                    <Button
                        className="rounded-full"
                        onClick={() => {
                            resetForm();
                            setShowForm(true);
                        }}
                    >
                        <Plus className="mr-2 h-4 w-4" /> 新建题目
                    </Button>
                </div>

                {/* Filters */}
                <div className="mb-4 flex flex-wrap items-end gap-2">
                    <select
                        className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm focus:border-blue-500 focus:outline-none"
                        value={filterCategoryId}
                        onChange={(e) => setFilterCategoryId(e.target.value)}
                        aria-label="分类"
                    >
                        <option value="">全部分类</option>
                        {categories.map((c) => (
                            <option key={c.category_id} value={c.category_id}>{c.name}</option>
                        ))}
                    </select>
                    <select
                        className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm focus:border-blue-500 focus:outline-none"
                        value={filterDifficulty}
                        onChange={(e) => setFilterDifficulty(e.target.value)}
                        aria-label="难度"
                    >
                        <option value="">全部难度</option>
                        <option value="easy">简单</option>
                        <option value="medium">中等</option>
                        <option value="hard">困难</option>
                    </select>
                    <select
                        className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm focus:border-blue-500 focus:outline-none"
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value)}
                        aria-label="状态"
                    >
                        <option value="">全部状态</option>
                        <option value="draft">草稿</option>
                        <option value="published">已发布</option>
                        <option value="archived">已归档</option>
                    </select>
                    <input
                        type="text"
                        placeholder="标签筛选..."
                        className="h-10 w-32 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm focus:border-blue-500 focus:outline-none"
                        value={filterTag}
                        onChange={(e) => setFilterTag(e.target.value)}
                    />
                </div>

                {actionError && (
                    <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{actionError}</div>
                )}

                {qError && (
                    <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{qError}</div>
                )}

                {/* Question Form */}
                {showForm && (
                    <GlassCard className="mb-4 border border-blue-200 bg-blue-50/30 p-4">
                        <h3 className="mb-3 font-bold text-slate-900">
                            {editingQuestion ? "编辑题目" : "新建题目"}
                        </h3>
                        {formError && (
                            <div className="mb-3 rounded-lg bg-red-50 p-2 text-sm text-red-600">{formError}</div>
                        )}
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <input
                                type="text"
                                placeholder="题目标题 *"
                                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none"
                                value={formTitle}
                                onChange={(e) => setFormTitle(e.target.value)}
                            />
                            <select
                                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none"
                                value={formCategoryId}
                                onChange={(e) => setFormCategoryId(e.target.value)}
                                data-testid="form-category"
                            >
                                <option value="">选择分类 *</option>
                                {categories.map((c) => (
                                    <option key={c.category_id} value={c.category_id}>{c.name}</option>
                                ))}
                            </select>
                            <textarea
                                placeholder="题干 *"
                                className="h-20 rounded-lg border border-slate-200 bg-white p-3 text-sm focus:border-blue-500 focus:outline-none md:col-span-2"
                                value={formStem}
                                onChange={(e) => setFormStem(e.target.value)}
                            />
                            <textarea
                                placeholder="参考答案"
                                className="h-16 rounded-lg border border-slate-200 bg-white p-3 text-sm focus:border-blue-500 focus:outline-none md:col-span-2"
                                value={formReferenceAnswer}
                                onChange={(e) => setFormReferenceAnswer(e.target.value)}
                            />
                            <select
                                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none"
                                value={formDifficulty}
                                onChange={(e) => setFormDifficulty(e.target.value as "easy" | "medium" | "hard")}
                                aria-label="题目难度"
                            >
                                <option value="easy">简单</option>
                                <option value="medium">中等</option>
                                <option value="hard">困难</option>
                            </select>
                            <input
                                type="text"
                                placeholder="标签（逗号分隔）"
                                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none"
                                value={formTags}
                                onChange={(e) => setFormTags(e.target.value)}
                            />
                            <input
                                type="text"
                                placeholder="评分维度（逗号分隔）"
                                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none"
                                value={formScoringDimensions}
                                onChange={(e) => setFormScoringDimensions(e.target.value)}
                            />
                            <input
                                type="text"
                                placeholder="部门"
                                className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:border-blue-500 focus:outline-none"
                                value={formDepartment}
                                onChange={(e) => setFormDepartment(e.target.value)}
                            />
                            <label className="flex items-center gap-2 text-sm text-slate-700">
                                <input
                                    type="checkbox"
                                    className="h-4 w-4"
                                    checked={formSafetyFlagged}
                                    onChange={(e) => setFormSafetyFlagged(e.target.checked)}
                                />
                                安全标记
                            </label>
                            <textarea
                                placeholder="评分标准 JSON"
                                className="h-16 rounded-lg border border-slate-200 bg-white p-3 text-sm font-mono focus:border-blue-500 focus:outline-none md:col-span-2"
                                value={formScoringCriteria}
                                onChange={(e) => setFormScoringCriteria(e.target.value)}
                            />
                        </div>
                        <div className="mt-3 flex gap-2">
                            <Button className="rounded-full" onClick={handleSubmitQuestion} disabled={formSubmitting}>
                                {formSubmitting ? "保存中..." : editingQuestion ? "更新" : "创建"}
                            </Button>
                            <Button variant="outline" className="rounded-full" onClick={resetForm}>
                                取消
                            </Button>
                        </div>
                    </GlassCard>
                )}

                {qLoading ? (
                    <div className="py-8 text-center text-slate-400">加载题目中...</div>
                ) : (
                    <div className="overflow-x-auto">
                        {questions.length === 0 ? (
                            <div className="py-8 text-center text-slate-400">暂无题目</div>
                        ) : (
                            <table className="w-full text-left text-sm">
                                <thead className="border-b border-slate-100 text-xs font-bold uppercase text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3">标题</th>
                                        <th className="px-4 py-3">分类</th>
                                        <th className="px-4 py-3">难度</th>
                                        <th className="px-4 py-3">状态</th>
                                        <th className="px-4 py-3">标签</th>
                                        <th className="px-4 py-3">版本</th>
                                        <th className="px-4 py-3 text-right">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {questions.map((q) => (
                                        <tr key={q.question_id} className="transition-colors hover:bg-slate-50/50">
                                            <td className="px-4 py-3 font-medium text-slate-900">{q.title}</td>
                                            <td className="px-4 py-3 text-slate-500">{q.category_name || getCategoryName(q.category_id)}</td>
                                            <td className="px-4 py-3">
                                                <Badge
                                                    variant={
                                                        q.difficulty === "easy" ? "green" :
                                                        q.difficulty === "hard" ? "red" : "blue"
                                                    }
                                                >
                                                    {DIFFICULTY_LABELS[q.difficulty] || q.difficulty}
                                                </Badge>
                                            </td>
                                            <td className="px-4 py-3">
                                                <Badge variant={STATUS_VARIANTS[q.status] || "gray"}>
                                                    {STATUS_LABELS[q.status] || q.status}
                                                </Badge>
                                            </td>
                                            <td className="px-4 py-3 max-w-[120px] truncate text-slate-500">
                                                {q.tags.join(", ") || "-"}
                                            </td>
                                            <td className="px-4 py-3 text-slate-500">v{q.version}</td>
                                            <td className="px-4 py-3 text-right">
                                                <div className="flex justify-end gap-1">
                                                    {q.status === "draft" && (
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="rounded-full text-slate-400 hover:text-blue-500"
                                                            onClick={() => startEditQuestion(q)}
                                                        >
                                                            <Edit2 className="h-4 w-4" />
                                                        </Button>
                                                    )}
                                                    {q.status !== "published" && (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="rounded-full text-xs text-green-600 hover:text-green-800"
                                                            onClick={() => handlePublish(q.question_id)}
                                                        >
                                                            发布
                                                        </Button>
                                                    )}
                                                    {q.status !== "archived" && (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="rounded-full text-xs text-amber-600 hover:text-amber-800"
                                                            onClick={() => handleArchive(q.question_id)}
                                                        >
                                                            <Archive className="mr-1 h-3 w-3" /> 归档
                                                        </Button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                )}
            </GlassCard>
        </div>
    );
}
