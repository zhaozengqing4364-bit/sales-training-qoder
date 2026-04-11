"use client";
import { debug } from "@/lib/debug";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Filter, MoreHorizontal, Plus, Database, Edit2, Trash2, FolderOpen, AlertCircle, RefreshCcw } from "lucide-react";

import { api } from "@/lib/api/client";
import { AdminKnowledgeBase } from "@/lib/api/types";
import { AssetGovernanceOverview, AssetGovernanceSummaryCard, type AssetGovernanceSummary } from "@/components/admin/asset-governance";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/glass-modal";
import { MobileTableCard } from "@/components/ui/mobile-table-card";

const categoryLabels: Record<string, string> = {
    product: "产品",
    competitor: "竞品",
    faq: "FAQ",
    policy: "政策",
};

type KnowledgeBaseWithGovernance = AdminKnowledgeBase & {
    governance_summary?: AssetGovernanceSummary | null;
};

export default function KnowledgePage() {
    const toast = useToast();
    const [kbs, setKbs] = useState<KnowledgeBaseWithGovernance[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isCreating, setIsCreating] = useState(false);
    const [newKb, setNewKb] = useState({
        name: "",
        description: "",
        category: "product" as "product" | "competitor" | "faq" | "policy",
    });

    const [deleteTarget, setDeleteTarget] = useState<KnowledgeBaseWithGovernance | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.admin.getKnowledgeBases();
            setKbs((data.items || []) as KnowledgeBaseWithGovernance[]);
        } catch (err) {
            debug.error("Failed to load knowledge bases:", err);
            setError(err instanceof Error ? err.message : "加载失败");
            setKbs([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadData();
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
            await loadData();
        } catch (err) {
            debug.error("Failed to create knowledge base:", err);
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
            setKbs((prev) => prev.filter((kb) => kb.id !== deleteTarget.id));
            toast.success("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            debug.error("Failed to delete knowledge base:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
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

            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">知识库管理</h1>
                    <p className="mt-1 text-slate-500">管理产品手册、销售话术等文档</p>
                </div>
                <div className="flex gap-3">
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button className="rounded-full bg-slate-900 text-white shadow-lg shadow-slate-900/20 hover:bg-slate-800">
                                <Plus className="mr-2 h-4 w-4" /> 新建知识库
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>新建知识库</DialogTitle>
                                <DialogDescription>创建一个新的知识库来管理您的文档。</DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-6">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">名称</label>
                                    <input
                                        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="例如：产品手册 V1.0"
                                        value={newKb.name}
                                        onChange={(event) => setNewKb((prev) => ({ ...prev, name: event.target.value }))}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">类别</label>
                                    <select
                                        className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                                        value={newKb.category}
                                        onChange={(event) => setNewKb((prev) => ({ ...prev, category: event.target.value as typeof newKb.category }))}
                                    >
                                        <option value="product">产品</option>
                                        <option value="competitor">竞品</option>
                                        <option value="faq">FAQ</option>
                                        <option value="policy">政策</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">描述</label>
                                    <textarea
                                        className="h-24 w-full resize-none rounded-lg border border-slate-200 p-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="描述该知识库的用途和内容..."
                                        value={newKb.description}
                                        onChange={(event) => setNewKb((prev) => ({ ...prev, description: event.target.value }))}
                                    />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="w-full rounded-full bg-slate-900 text-white" onClick={handleCreate} disabled={isCreating}>
                                    {isCreating ? "创建中..." : "创建"}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            <GlassCard className="flex flex-col items-center justify-between gap-4 p-4 md:flex-row">
                <div className="group relative w-full md:w-96">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 transition-colors group-focus-within:text-blue-500" />
                    <input
                        type="text"
                        placeholder="搜索知识库..."
                        className="h-10 w-full rounded-full border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm transition-all focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/10"
                    />
                </div>
                <div className="flex gap-2">
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900">
                                <Filter className="mr-2 h-4 w-4" /> 筛选
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>筛选知识库</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-6">
                                <div>
                                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-400">类型</label>
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

            {!isLoading && !error ? <AssetGovernanceOverview assetType="knowledge_base" items={kbs} /> : null}

            {error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-500">
                        <AlertCircle className="h-8 w-8" />
                    </div>
                    <h3 className="mb-2 text-lg font-bold text-slate-900">加载失败</h3>
                    <p className="mb-4 text-sm text-slate-500">{error}</p>
                    <Button onClick={() => void loadData()} className="rounded-full">
                        <RefreshCcw className="mr-2 h-4 w-4" /> 重试
                    </Button>
                </GlassCard>
            ) : null}

            {isLoading && !error ? (
                <GlassCard className="p-8 text-center">
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
                    <p className="text-slate-500">加载中...</p>
                </GlassCard>
            ) : null}

            {!isLoading && !error ? (
                <GlassCard className="overflow-hidden">
                    <div className="space-y-4 p-4 md:hidden">
                        {kbs.length === 0 ? (
                            <div className="py-8 text-center text-slate-500">暂无知识库数据</div>
                        ) : kbs.map((kb) => (
                            <MobileTableCard
                                key={kb.id}
                                title={<div className="font-bold text-slate-900">{kb.name}</div>}
                                icon={
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                                        <Database className="h-5 w-5" />
                                    </div>
                                }
                                columns={[
                                    { label: "类别", value: categoryLabels[kb.category] || kb.category },
                                    { label: "文档数", value: kb.document_count || 0 },
                                ]}
                                actions={
                                    <div className="absolute right-4 top-4">
                                        <Button variant="ghost" size="icon" className="rounded-full text-slate-400 hover:text-slate-900">
                                            <MoreHorizontal className="h-4 w-4" />
                                        </Button>
                                    </div>
                                }
                                className="relative"
                            >
                                <div className="space-y-3 pt-2">
                                    <div className="text-xs text-slate-500">{kb.description || "-"}</div>
                                    <AssetGovernanceSummaryCard summary={kb.governance_summary} />
                                </div>
                            </MobileTableCard>
                        ))}
                    </div>

                    <div className="hidden overflow-x-auto md:block">
                        {kbs.length === 0 ? (
                            <div className="py-12 text-center text-slate-500">暂无知识库数据</div>
                        ) : (
                            <table className="w-full text-left text-sm">
                                <thead className="border-b border-slate-100 bg-slate-50/50 text-xs font-bold uppercase tracking-wider text-slate-400">
                                    <tr>
                                        <th className="px-6 py-4">知识库名称</th>
                                        <th className="px-6 py-4">描述</th>
                                        <th className="px-6 py-4">类别</th>
                                        <th className="px-6 py-4">文档数量</th>
                                        <th className="px-6 py-4">分块数</th>
                                        <th className="min-w-[22rem] px-6 py-4">治理上下文</th>
                                        <th className="px-6 py-4 text-right">操作</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {kbs.map((kb) => (
                                        <tr key={kb.id} className="group transition-colors hover:bg-slate-50/50">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-blue-600 transition-colors group-hover:bg-blue-100">
                                                        <Database className="h-5 w-5" />
                                                    </div>
                                                    <div className="font-bold text-slate-900">{kb.name}</div>
                                                </div>
                                            </td>
                                            <td className="max-w-xs truncate px-6 py-4 text-slate-500">{kb.description || "-"}</td>
                                            <td className="px-6 py-4 font-medium text-slate-700">
                                                <Badge variant="secondary" className="bg-slate-100 text-slate-600">
                                                    {categoryLabels[kb.category] || kb.category}
                                                </Badge>
                                            </td>
                                            <td className="px-6 py-4 font-medium text-slate-700">{kb.document_count || 0}</td>
                                            <td className="px-6 py-4 font-medium text-slate-700">{kb.total_chunks || 0}</td>
                                            <td className="px-6 py-4 align-top">
                                                <AssetGovernanceSummaryCard summary={kb.governance_summary} className="min-w-[20rem]" />
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <div className="flex justify-end gap-2">
                                                    <Link href={`/admin/knowledge/${kb.id}`}>
                                                        <Button variant="ghost" size="sm" className="h-8 rounded-full px-3 text-slate-500 hover:bg-blue-50 hover:text-blue-600">
                                                            <FolderOpen className="mr-2 h-4 w-4" /> 管理文档
                                                        </Button>
                                                    </Link>
                                                    <Link href={`/admin/knowledge/${kb.id}`}>
                                                        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-slate-400 hover:bg-blue-50 hover:text-blue-600">
                                                            <Edit2 className="h-4 w-4" />
                                                        </Button>
                                                    </Link>
                                                    <Button
                                                        onClick={() => setDeleteTarget(kb)}
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 rounded-full text-slate-400 hover:bg-red-50 hover:text-red-600"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4">
                        <span className="text-xs font-medium text-slate-400">
                            显示 {kbs.length > 0 ? `1-${kbs.length}` : "0"} 共 {kbs.length} 个知识库
                        </span>
                        <div className="flex gap-2">
                            <Button variant="outline" size="sm" className="h-8 rounded-full text-xs" disabled>上一页</Button>
                            <Button variant="outline" size="sm" className="h-8 rounded-full text-xs" disabled>下一页</Button>
                        </div>
                    </div>
                </GlassCard>
            ) : null}
        </div>
    );
}
