"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Edit2, Plus, Trash2, X } from "lucide-react";

import { AdminFormShell } from "@/components/admin/admin-layout-shells";
import { api } from "@/lib/api/client";
import type { CreateCategoryRequest, QuestionCategory, UpdateCategoryRequest } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export function TestBankCategoryPanel() {
    const toast = useToast();
    const [categories, setCategories] = useState<QuestionCategory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [newCatName, setNewCatName] = useState("");
    const [newCatParentId, setNewCatParentId] = useState("");
    const [creating, setCreating] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<QuestionCategory | null>(null);
    const [deleting, setDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
    const [editCatName, setEditCatName] = useState("");
    const [editCatDescription, setEditCatDescription] = useState("");
    const [editCatParentId, setEditCatParentId] = useState("");
    const [editCatOrderIndex, setEditCatOrderIndex] = useState("0");
    const [saving, setSaving] = useState(false);

    const loadCategories = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await api.testBank.listCategories();
            setCategories(result.items || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : "加载分类失败");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void loadCategories(); }, [loadCategories]);

    const getCategoryName = (categoryId: string) => categories.find((c) => c.category_id === categoryId)?.name || categoryId;
    const getCategoryPath = (cat: QuestionCategory) => {
        if (!cat.parent_id) return cat.name;
        const parent = categories.find((c) => c.category_id === cat.parent_id);
        return parent ? `${parent.name} > ${cat.name}` : cat.name;
    };

    const handleCreate = async () => {
        if (!newCatName.trim()) return;
        setCreating(true);
        setError(null);
        try {
            const payload: CreateCategoryRequest = { name: newCatName.trim() };
            if (newCatParentId) payload.parent_id = newCatParentId;
            await api.testBank.createCategory(payload);
            setNewCatName("");
            setNewCatParentId("");
            toast.success("分类创建成功");
            void loadCategories();
        } catch (err) {
            setError(err instanceof Error ? err.message : "创建分类失败");
        } finally {
            setCreating(false);
        }
    };

    const startEdit = (cat: QuestionCategory) => {
        setEditingCategoryId(cat.category_id);
        setEditCatName(cat.name);
        setEditCatDescription(cat.description || "");
        setEditCatParentId(cat.parent_id || "");
        setEditCatOrderIndex(String(cat.order_index));
    };

    const handleUpdate = async () => {
        if (!editingCategoryId || !editCatName.trim()) return;
        setSaving(true);
        setError(null);
        try {
            const payload: UpdateCategoryRequest = {
                name: editCatName.trim(),
                description: editCatDescription.trim() || undefined,
                parent_id: editCatParentId || null,
            };
            const orderIndex = parseInt(editCatOrderIndex, 10);
            if (!Number.isNaN(orderIndex)) payload.order_index = orderIndex;
            await api.testBank.updateCategory(editingCategoryId, payload);
            toast.success("分类已更新");
            setEditingCategoryId(null);
            void loadCategories();
        } catch (err) {
            setError(err instanceof Error ? err.message : "更新分类失败");
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleting(true);
        setDeleteError(null);
        try {
            await api.testBank.deleteCategory(deleteTarget.category_id);
            toast.success("删除成功");
            setDeleteTarget(null);
            void loadCategories();
        } catch (err) {
            setDeleteError(err instanceof Error ? err.message : "删除失败");
        } finally {
            setDeleting(false);
        }
    };

    return (
        <AdminFormShell backHref="/admin/test-bank" backLabel="返回题目列表" title="题库分类管理" description="维护试题分类层级，供题目创建与筛选使用。">
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除分类"
                description={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={deleting}
            />
            <GlassCard className="p-6">
                <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-900">
                    <BookOpen className="h-5 w-5" /> 分类管理
                </h2>
                <div className="mb-4 flex flex-wrap items-end gap-2">
                    <input type="text" placeholder="分类名称" className="h-10 w-48 rounded-full border border-slate-200 bg-slate-50 px-4 text-sm" value={newCatName} onChange={(e) => setNewCatName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void handleCreate()} />
                    <select className="h-10 rounded-full border border-slate-200 bg-slate-50 px-3 text-sm" value={newCatParentId} onChange={(e) => setNewCatParentId(e.target.value)}>
                        <option value="">无父分类</option>
                        {categories.map((c) => (<option key={c.category_id} value={c.category_id}>{c.name}</option>))}
                    </select>
                    <Button className="rounded-full" onClick={() => void handleCreate()} disabled={creating || !newCatName.trim()}>
                        <Plus className="mr-2 h-4 w-4" /> 新建分类
                    </Button>
                </div>
                {error && <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
                {deleteError && <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-600">{deleteError}</div>}
                {loading ? <div className="py-6 text-center text-slate-400">加载分类中...</div> : categories.length === 0 ? <div className="py-6 text-center text-slate-400">暂无分类</div> : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead className="border-b border-slate-100 text-xs font-bold uppercase text-slate-400">
                                <tr><th className="px-4 py-3">名称</th><th className="px-4 py-3">描述</th><th className="px-4 py-3">父分类</th><th className="px-4 py-3">排序</th><th className="px-4 py-3 text-right">操作</th></tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {categories.map((cat) => (
                                    <tr key={cat.category_id}>
                                        {editingCategoryId === cat.category_id ? (
                                            <>
                                                <td className="px-4 py-3"><input className="h-9 w-full rounded border px-2 text-sm" value={editCatName} onChange={(e) => setEditCatName(e.target.value)} /></td>
                                                <td className="px-4 py-3"><input className="h-9 w-full rounded border px-2 text-sm" value={editCatDescription} onChange={(e) => setEditCatDescription(e.target.value)} /></td>
                                                <td className="px-4 py-3"><select className="h-9 w-full rounded border px-2 text-sm" value={editCatParentId} onChange={(e) => setEditCatParentId(e.target.value)}><option value="">无</option>{categories.filter((c) => c.category_id !== cat.category_id).map((c) => (<option key={c.category_id} value={c.category_id}>{c.name}</option>))}</select></td>
                                                <td className="px-4 py-3"><input type="number" className="h-9 w-16 rounded border px-2 text-sm" value={editCatOrderIndex} onChange={(e) => setEditCatOrderIndex(e.target.value)} /></td>
                                                <td className="px-4 py-3 text-right"><Button variant="ghost" size="sm" onClick={() => void handleUpdate()} disabled={saving}>保存</Button><Button variant="ghost" size="icon" onClick={() => setEditingCategoryId(null)}><X className="h-4 w-4" /></Button></td>
                                            </>
                                        ) : (
                                            <>
                                                <td className="px-4 py-3 font-medium">{getCategoryPath(cat)}</td>
                                                <td className="px-4 py-3 text-slate-500">{cat.description || "-"}</td>
                                                <td className="px-4 py-3 text-slate-500">{cat.parent_id ? getCategoryName(cat.parent_id) : "-"}</td>
                                                <td className="px-4 py-3 text-slate-500">{cat.order_index}</td>
                                                <td className="px-4 py-3 text-right"><Button variant="ghost" size="icon" onClick={() => startEdit(cat)}><Edit2 className="h-4 w-4" /></Button><Button variant="ghost" size="icon" onClick={() => setDeleteTarget(cat)}><Trash2 className="h-4 w-4" /></Button></td>
                                            </>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </GlassCard>
        </AdminFormShell>
    );
}
