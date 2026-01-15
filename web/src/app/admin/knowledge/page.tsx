"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { AdminKnowledgeBase } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Search, Filter, MoreHorizontal, Plus, Database, Edit2, Trash2, FolderOpen, AlertCircle, RefreshCcw } from "lucide-react";
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

// Category display mapping
const categoryLabels: Record<string, string> = {
    product: "产品",
    competitor: "竞品",
    faq: "FAQ",
    policy: "政策",
};

export default function KnowledgePage() {
    const toast = useToast();
    const [kbs, setKbs] = useState<AdminKnowledgeBase[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // Create dialog state
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [newKb, setNewKb] = useState({
        name: "",
        description: "",
        category: "product" as "product" | "competitor" | "faq" | "policy",
    });
    
    // Delete confirm dialog
    const [deleteTarget, setDeleteTarget] = useState<AdminKnowledgeBase | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.admin.getKnowledgeBases();
            setKbs(data);
        } catch (err) {
            console.error("Failed to load knowledge bases:", err);
            setError(err instanceof Error ? err.message : "加载失败");
            setKbs([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleCreate = async () => {
        if (!newKb.name.trim()) {
            toast.error("请输入知识库名称");
            return;
        }
        
        setIsCreating(true);
        try {
            await api.admin.createKnowledgeBase({
                name: newKb.name,
                description: newKb.description || undefined,
                category: newKb.category,
            });
            setIsCreateOpen(false);
            setNewKb({ name: "", description: "", category: "product" });
            toast.success("知识库创建成功");
            loadData();
        } catch (err) {
            console.error("Failed to create knowledge base:", err);
            toast.error(`创建失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        
        setIsDeleting(true);
        try {
            await api.admin.deleteKnowledgeBase(deleteTarget.id);
            setKbs(prev => prev.filter(k => k.id !== deleteTarget.id));
            toast.success("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            console.error("Failed to delete knowledge base:", err);
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
                title="删除知识库"
                description={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销，所有关联文档也将被删除。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />
            
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">知识库管理</h1>
                    <p className="text-slate-500 mt-1">管理产品手册、销售话术等文档</p>
                </div>
                <div className="flex gap-3">
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button className="rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20">
                                <Plus className="w-4 h-4 mr-2" /> 新建知识库
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>新建知识库</DialogTitle>
                                <DialogDescription>创建一个新的知识库来管理您的文档。</DialogDescription>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">名称</label>
                                    <input 
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none" 
                                        placeholder="例如：产品手册 V1.0"
                                        value={newKb.name}
                                        onChange={(e) => setNewKb(prev => ({ ...prev, name: e.target.value }))}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">类别</label>
                                    <select 
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                        value={newKb.category}
                                        onChange={(e) => setNewKb(prev => ({ ...prev, category: e.target.value as typeof newKb.category }))}
                                    >
                                        <option value="product">产品</option>
                                        <option value="competitor">竞品</option>
                                        <option value="faq">FAQ</option>
                                        <option value="policy">政策</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">描述</label>
                                    <textarea 
                                        className="w-full h-24 rounded-lg border border-slate-200 p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none" 
                                        placeholder="描述该知识库的用途和内容..."
                                        value={newKb.description}
                                        onChange={(e) => setNewKb(prev => ({ ...prev, description: e.target.value }))}
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
                        placeholder="搜索知识库..."
                        className="w-full h-10 pl-10 pr-4 bg-slate-50 border border-slate-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/10 focus:border-blue-500 transition-all"
                    />
                </div>
                <div className="flex gap-2">
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900">
                                <Filter className="w-4 h-4 mr-2" /> 筛选
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>筛选知识库</DialogTitle>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">类型</label>
                                    <div className="flex flex-wrap gap-2">
                                        <Badge variant="blue" className="cursor-pointer">全部</Badge>
                                        <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-600 hover:bg-slate-200">产品</Badge>
                                        <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-600 hover:bg-slate-200">竞品</Badge>
                                        <Badge variant="secondary" className="cursor-pointer bg-slate-100 text-slate-600 hover:bg-slate-200">FAQ</Badge>
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="w-full rounded-full bg-slate-900 text-white">应用筛选</Button>
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

            {/* Knowledge Bases Table */}
            {!isLoading && !error && (
            <GlassCard className="overflow-hidden">
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4 p-4">
                    {kbs.length === 0 ? (
                        <div className="text-center py-8 text-slate-500">暂无知识库数据</div>
                    ) : kbs.map((kb) => (
                        <MobileTableCard
                            key={kb.id}
                            title={
                                <div>
                                    <div className="font-bold text-slate-900">{kb.name}</div>
                                </div>
                            }
                            icon={
                                <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
                                    <Database className="w-5 h-5" />
                                </div>
                            }
                            columns={[
                                {
                                    label: "类别",
                                    value: categoryLabels[kb.category] || kb.category
                                },
                                {
                                    label: "文档数",
                                    value: kb.document_count || 0
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
                            <div className="text-xs text-slate-500 pt-2">{kb.description}</div>
                        </MobileTableCard>
                    ))}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    {kbs.length === 0 ? (
                        <div className="text-center py-12 text-slate-500">暂无知识库数据</div>
                    ) : (
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                            <tr>
                                <th className="px-6 py-4">知识库名称</th>
                                <th className="px-6 py-4">描述</th>
                                <th className="px-6 py-4">类别</th>
                                <th className="px-6 py-4">文档数量</th>
                                <th className="px-6 py-4">分块数</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {kbs.map((kb) => (
                                <tr key={kb.id} className="hover:bg-slate-50/50 transition-colors group">
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 group-hover:bg-blue-100 transition-colors">
                                                <Database className="w-5 h-5" />
                                            </div>
                                            <div className="font-bold text-slate-900">{kb.name}</div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-slate-500 max-w-xs truncate">
                                        {kb.description || "-"}
                                    </td>
                                    <td className="px-6 py-4 font-medium text-slate-700">
                                        <Badge variant="secondary" className="bg-slate-100 text-slate-600">
                                            {categoryLabels[kb.category] || kb.category}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4 font-medium text-slate-700">
                                        {kb.document_count || 0}
                                    </td>
                                    <td className="px-6 py-4 font-medium text-slate-700">
                                        {kb.total_chunks || 0}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex justify-end gap-2">
                                            <Link href={`/admin/knowledge/${kb.id}`}>
                                                <Button variant="ghost" size="sm" className="h-8 rounded-full text-slate-500 hover:text-blue-600 hover:bg-blue-50 px-3">
                                                    <FolderOpen className="w-4 h-4 mr-2" /> 管理文档
                                                </Button>
                                            </Link>
                                            <Link href={`/admin/knowledge/${kb.id}`}>
                                                <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                    <Edit2 className="w-4 h-4" />
                                                </Button>
                                            </Link>
                                            <Button onClick={() => setDeleteTarget(kb)} variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full">
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
                 <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-medium">显示 {kbs.length > 0 ? `1-${kbs.length}` : '0'} 共 {kbs.length} 个知识库</span>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" className="h-8 text-xs rounded-full" disabled>上一页</Button>
                        <Button variant="outline" size="sm" className="h-8 text-xs rounded-full" disabled>下一页</Button>
                    </div>
                </div>
            </GlassCard>
            )}
        </div>
    );
}