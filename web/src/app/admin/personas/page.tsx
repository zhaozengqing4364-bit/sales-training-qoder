"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { AdminPersona } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Search, Filter, MoreHorizontal, Plus, Star, Edit2, Trash2, AlertCircle, RefreshCcw } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import {
    MobileTableCard
} from "@/components/ui/mobile-table-card";
import Link from "next/link";

// Difficulty to stars mapping
const difficultyToStars = (difficulty: string): number => {
    switch (difficulty) {
        case "easy": return 2;
        case "medium": return 3;
        case "hard": return 5;
        default: return 3;
    }
};

// Category display mapping
const categoryLabels: Record<string, string> = {
    customer: "客户",
    interviewer: "面试官",
    coach: "教练",
    examiner: "考官",
};

export default function PersonasPage() {
    const toast = useToast();
    const [personas, setPersonas] = useState<AdminPersona[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Search & Filter States
    const [searchQuery, setSearchQuery] = useState("");
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    // Create dialog state
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [newPersona, setNewPersona] = useState({
        name: "",
        description: "",
        category: "customer" as "customer" | "interviewer" | "coach" | "examiner",
        difficulty: "medium" as "easy" | "medium" | "hard",
        system_prompt: "你是一个AI角色，请根据设定进行对话。",
    });

    // Delete confirm dialog
    const [deleteTarget, setDeleteTarget] = useState<AdminPersona | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await api.admin.getPersonas({
                search: searchQuery || undefined,
                page: page,
                page_size: 10
            });
            // result 是 AdminPersona[] 数组
            setPersonas(result.items || []);
            setTotal(result.total || 0);
        } catch (err) {
            console.error("Failed to load personas:", err);
            setError(err instanceof Error ? err.message : "加载失败");
            setPersonas([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, searchQuery]);

    const handleCreate = async () => {
        if (!newPersona.name.trim()) {
            toast.error("请输入角色名称");
            return;
        }

        setIsCreating(true);
        try {
            await api.admin.createPersona({
                name: newPersona.name,
                description: newPersona.description || undefined,
                category: newPersona.category,
                difficulty: newPersona.difficulty,
                system_prompt: newPersona.system_prompt,
            });
            setIsCreateOpen(false);
            setNewPersona({
                name: "",
                description: "",
                category: "customer",
                difficulty: "medium",
                system_prompt: "你是一个AI角色，请根据设定进行对话。",
            });
            toast.success("角色创建成功");
            loadData();
        } catch (err) {
            console.error("Failed to create persona:", err);
            toast.error(`创建失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await api.admin.deletePersona(deleteTarget.id);
            setPersonas(prev => prev.filter(p => p.id !== deleteTarget.id));
            toast.success("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            console.error("Failed to delete persona:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Delete Confirm Dialog */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除角色"
                description={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">角色管理</h1>
                    <p className="text-slate-500 mt-1">管理不同场景下的 AI 角色配置</p>
                </div>
                <div className="flex gap-3">
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button className="rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20">
                                <Plus className="w-4 h-4 mr-2" /> 新建角色
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>新建角色</DialogTitle>
                                <DialogDescription>配置一个新的 AI 角色性格和行为。</DialogDescription>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">角色名称</label>
                                    <input
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                        placeholder="例如：挑剔的客户"
                                        value={newPersona.name}
                                        onChange={(e) => setNewPersona(prev => ({ ...prev, name: e.target.value }))}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">描述</label>
                                    <input
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                        placeholder="角色的简短描述"
                                        value={newPersona.description}
                                        onChange={(e) => setNewPersona(prev => ({ ...prev, description: e.target.value }))}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">角色类型</label>
                                    <select
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                        value={newPersona.category}
                                        onChange={(e) => setNewPersona(prev => ({ ...prev, category: e.target.value as typeof newPersona.category }))}
                                    >
                                        <option value="customer">客户</option>
                                        <option value="interviewer">面试官</option>
                                        <option value="coach">教练</option>
                                        <option value="examiner">考官</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">难度</label>
                                    <select
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                        value={newPersona.difficulty}
                                        onChange={(e) => setNewPersona(prev => ({ ...prev, difficulty: e.target.value as typeof newPersona.difficulty }))}
                                    >
                                        <option value="easy">简单</option>
                                        <option value="medium">中等</option>
                                        <option value="hard">困难</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">系统提示词</label>
                                    <textarea
                                        className="w-full h-24 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                                        placeholder="定义角色的行为和性格..."
                                        value={newPersona.system_prompt}
                                        onChange={(e) => setNewPersona(prev => ({ ...prev, system_prompt: e.target.value }))}
                                    />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button
                                    className="w-full rounded-full bg-slate-900 text-white"
                                    onClick={handleCreate}
                                    disabled={isCreating}
                                >
                                    {isCreating ? "创建中..." : "创建"}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            {/* Filters Section */}
            <GlassCard className="p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
                <div className="relative w-full md:w-96 group">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                    <input
                        type="text"
                        placeholder="搜索角色..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full h-10 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/10 focus:border-blue-500 transition-all"
                    />
                </div>
                <div className="flex gap-2">
                    <Dialog open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900">
                                <Filter className="w-4 h-4 mr-2" /> 筛选
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>筛选角色</DialogTitle>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">难度</label>
                                    <div className="flex flex-wrap gap-2">
                                        <Badge variant="blue" className="cursor-pointer">全部</Badge>
                                        <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-600 hover:bg-slate-200">简单</Badge>
                                        <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-600 hover:bg-slate-200">中等</Badge>
                                        <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-600 hover:bg-slate-200">困难</Badge>
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="w-full rounded-full bg-slate-900 text-white" onClick={() => setIsFilterOpen(false)}>应用筛选</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </GlassCard>

            {/* Error State */}
            {error && (
                <GlassCard className="p-8 text-center">
                    <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center text-red-500 mb-4 mx-auto">
                        <AlertCircle className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 mb-2">加载失败</h3>
                    <p className="text-slate-500 text-sm mb-4">{error}</p>
                    <Button onClick={loadData} className="rounded-full">
                        <RefreshCcw className="w-4 h-4 mr-2" /> 重试
                    </Button>
                </GlassCard>
            )}

            {/* Loading State */}
            {isLoading && !error && (
                <GlassCard className="p-8 text-center">
                    <div className="animate-spin w-8 h-8 border-2 border-slate-200 border-t-slate-900 rounded-full mx-auto mb-4"></div>
                    <p className="text-slate-500">加载中...</p>
                </GlassCard>
            )}

            {/* Personas Table */}
            {!isLoading && !error && (
                <GlassCard className="overflow-hidden">
                    {/* Mobile Card View */}
                    <div className="md:hidden space-y-4 p-4">
                        {personas.length === 0 ? (
                            <div className="text-center py-8 text-slate-500">暂无角色数据</div>
                        ) : personas.map((p) => (
                            <MobileTableCard
                                key={p.id}
                                title={<div className="font-bold text-slate-900">{p.name}</div>}
                                icon={
                                    <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-xs font-bold">
                                        {p.name.charAt(0)}
                                    </div>
                                }
                                columns={[
                                    { label: "类型", value: categoryLabels[p.category] || p.category },
                                    {
                                        label: "难度",
                                        value: (
                                            <div className="flex">
                                                {Array.from({ length: 5 }).map((_, i) => (
                                                    <Star key={i} className={`w-3 h-3 ${i < difficultyToStars(p.difficulty) ? 'text-amber-400 fill-amber-400' : 'text-slate-200'}`} />
                                                ))}
                                            </div>
                                        )
                                    }
                                ]}
                                actions={
                                    <div className="absolute top-4 right-4">
                                        <Button variant="ghost" size="icon" className="text-slate-400 hover:text-slate-900 rounded-full">
                                            <MoreHorizontal className="w-4 h-4" />
                                        </Button>
                                    </div>
                                }
                                className="relative"
                            >
                                <div className="text-xs text-slate-500 pt-2">{p.description}</div>
                            </MobileTableCard>
                        ))}
                    </div>

                    {/* Desktop Table View */}
                    <div className="hidden md:block overflow-x-auto">
                        {personas.length === 0 ? (
                            <div className="text-center py-12 text-slate-500">暂无角色数据</div>
                        ) : (
                            <table className="w-full text-sm text-left">
                                <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                                    <tr>
                                        <th className="px-6 py-4">角色名称</th>
                                        <th className="px-6 py-4">描述</th>
                                        <th className="px-6 py-4">类型</th>
                                        <th className="px-6 py-4">难度</th>
                                        <th className="px-6 py-4 text-right">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {personas.map((p) => (
                                        <tr key={p.id} className="hover:bg-slate-50/50 transition-colors group">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-9 h-9 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600 text-xs font-bold group-hover:bg-indigo-100 transition-colors">
                                                        {p.name.charAt(0)}
                                                    </div>
                                                    <div className="font-bold text-slate-900">{p.name}</div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-slate-500 max-w-xs truncate">
                                                {p.description}
                                            </td>
                                            <td className="px-6 py-4 font-medium text-slate-700">
                                                {categoryLabels[p.category] || p.category}
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center">
                                                    {Array.from({ length: 5 }).map((_, i) => (
                                                        <Star key={i} className={`w-3.5 h-3.5 ${i < difficultyToStars(p.difficulty) ? 'text-amber-400 fill-amber-400' : 'text-slate-200'}`} />
                                                    ))}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <div className="flex justify-end gap-2">
                                                    <Link href={`/admin/personas/${p.id}`}>
                                                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                            <Edit2 className="w-4 h-4" />
                                                        </Button>
                                                    </Link>
                                                    <Button onClick={() => setDeleteTarget(p)} variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full">
                                                        <Trash2 className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    {/* Pagination */}
                    {personas.length > 0 && (
                        <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
                            <span className="text-xs text-slate-400 font-medium">
                                显示 {(page - 1) * 10 + 1}-{Math.min(page * 10, total || personas.length)} 共 {total || personas.length} 个角色
                            </span>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-8 text-xs rounded-full"
                                    disabled={page === 1}
                                    onClick={() => setPage(p => p - 1)}
                                >
                                    上一页
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="h-8 text-xs rounded-full"
                                    onClick={() => setPage(p => p + 1)}
                                    disabled={personas.length < 10}
                                >
                                    下一页
                                </Button>
                            </div>
                        </div>
                    )}
                </GlassCard>
            )}
        </div>
    );
}
