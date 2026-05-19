"use client";
import { debug } from "@/lib/debug";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Filter, Plus, Edit2, Trash2, Presentation } from "lucide-react";

import { api } from "@/lib/api/client";
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

interface PresentationItem {
    presentation_id: string;
    title: string;
    status: "processing" | "ready" | "failed";
    file_size_bytes: number;
    page_count: number;
    uploaded_by_admin_id: string;
    created_at: string;
    governance_summary?: AssetGovernanceSummary | null;
}

type PresentationStatus = "processing" | "ready" | "failed";

const STATUS_OPTIONS: { value: PresentationStatus; label: string; color: string; dotColor: string }[] = [
    { value: "ready", label: "可用", color: "text-emerald-600", dotColor: "bg-emerald-500" },
    { value: "processing", label: "处理中", color: "text-blue-600", dotColor: "bg-blue-500" },
    { value: "failed", label: "失败", color: "text-red-600", dotColor: "bg-red-500" },
];

function getStatusStyle(status: string) {
    const option = STATUS_OPTIONS.find((item) => item.value === status);
    return option || STATUS_OPTIONS[1];
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PresentationsPage() {
    const toast = useToast();
    const [presentations, setPresentations] = useState<PresentationItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);

    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [page, setPage] = useState(1);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [newTitle, setNewTitle] = useState("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isCreating, setIsCreating] = useState(false);

    const [deleteTarget, setDeleteTarget] = useState<PresentationItem | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = async () => {
        setIsLoading(true);
        setLoadError(null);
        try {
            const data = await api.presentations.list({
                status: statusFilter !== "all" ? statusFilter : undefined,
                limit: 20,
            });
            setPresentations((data || []) as PresentationItem[]);
        } catch (err) {
            debug.error("Failed to load presentations:", err);
            const message = err instanceof Error ? err.message : "PPT 列表加载失败";
            setLoadError(message);
            toast.error(message);
            setPresentations([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, statusFilter, searchQuery]);

    const handleCreate = async () => {
        if (!newTitle.trim()) {
            toast.error("请输入PPT标题");
            return;
        }
        if (!selectedFile) {
            toast.error("请选择PPT文件");
            return;
        }

        setIsCreating(true);
        try {
            await api.presentations.upload({ title: newTitle, file: selectedFile });
            setIsCreateOpen(false);
            setNewTitle("");
            setSelectedFile(null);
            toast.success("PPT上传成功");
            await loadData();
        } catch (err) {
            debug.error("Failed to upload presentation:", err);
            toast.error(`上传失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await api.presentations.delete(deleteTarget.presentation_id);
            setPresentations((prev) => prev.filter((item) => item.presentation_id !== deleteTarget.presentation_id));
            toast.success("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            debug.error("Failed to delete presentation:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleApplyFilter = () => {
        setIsFilterOpen(false);
        setPage(1);
    };

    const filteredPresentations = presentations.filter((presentation) =>
        presentation.title.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除PPT"
                description={`确定要删除「${deleteTarget?.title}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">PPT演练管理</h1>
                    <p className="mt-1 text-slate-500">管理PPT演示文稿和演练配置</p>
                </div>
                <div className="flex gap-3">
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button type="button" className="rounded-full bg-slate-900 text-white shadow-lg shadow-slate-900/20 hover:bg-slate-800">
                                <Plus className="mr-2 h-4 w-4" /> 上传PPT
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>上传PPT</DialogTitle>
                                <DialogDescription>上传一个新的PPT演示文稿用于演练。</DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-6">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">PPT标题</label>
                                    <input
                                        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="例如：产品发布演讲"
                                        value={newTitle}
                                        onChange={(event) => setNewTitle(event.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold uppercase text-slate-500">PPT文件</label>
                                    <input
                                        type="file"
                                        accept=".ppt,.pptx"
                                        className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500 file:mr-4 file:rounded-full file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-blue-700 hover:file:bg-blue-100"
                                        onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                                    />
                                    <p className="text-xs text-slate-400">支持 .ppt 和 .pptx 格式</p>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button type="button" variant="ghost" className="rounded-full" onClick={() => setIsCreateOpen(false)}>
                                    取消
                                </Button>
                                <Button type="button" className="rounded-full bg-slate-900 text-white" onClick={handleCreate} disabled={isCreating}>
                                    {isCreating ? "上传中..." : "上传"}
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
                        placeholder="搜索PPT..."
                        value={searchQuery}
                        onChange={(event) => setSearchQuery(event.target.value)}
                        className="h-10 w-full rounded-full border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm transition-all focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/10"
                    />
                </div>
                <div className="flex gap-2">
                    <Dialog open={isFilterOpen} onOpenChange={setIsFilterOpen}>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-900">
                                <Filter className="mr-2 h-4 w-4" /> 筛选
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>筛选PPT</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-6">
                                <div>
                                    <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-400">状态</label>
                                    <div className="flex flex-wrap gap-2">
                                        <Badge variant={statusFilter === "all" ? "blue" : "secondary"} className="cursor-pointer" onClick={() => setStatusFilter("all")}>全部</Badge>
                                        <Badge variant={statusFilter === "ready" ? "blue" : "secondary"} className="cursor-pointer" onClick={() => setStatusFilter("ready")}>可用</Badge>
                                        <Badge variant={statusFilter === "processing" ? "blue" : "secondary"} className="cursor-pointer" onClick={() => setStatusFilter("processing")}>处理中</Badge>
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="w-full rounded-full bg-slate-900 text-white" onClick={handleApplyFilter}>应用筛选</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </GlassCard>

            {!isLoading ? <AssetGovernanceOverview assetType="presentation" items={filteredPresentations} /> : null}

            <GlassCard className="overflow-hidden">
                {loadError ? (
                    <div className="m-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                        <p className="font-semibold">PPT 列表加载失败</p>
                        <p className="mt-1">{loadError}</p>
                        <Button variant="outline" className="mt-3 rounded-full" onClick={() => void loadData()}>重试</Button>
                    </div>
                ) : null}
                <div className="space-y-4 p-4 md:hidden">
                    {filteredPresentations.map((presentation) => {
                        const statusStyle = getStatusStyle(presentation.status);
                        return (
                            <MobileTableCard
                                key={presentation.presentation_id}
                                title={<div className="font-bold text-slate-900">{presentation.title}</div>}
                                icon={
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-50 text-orange-600">
                                        <Presentation className="h-5 w-5" />
                                    </div>
                                }
                                columns={[
                                    {
                                        label: "状态",
                                        value: (
                                            <div className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium ${statusStyle.color}`}>
                                                <div className={`h-1.5 w-1.5 rounded-full ${statusStyle.dotColor}`} />
                                                {statusStyle.label}
                                            </div>
                                        ),
                                    },
                                    { label: "页数", value: `${presentation.page_count || 0} 页` },
                                    { label: "大小", value: formatFileSize(presentation.file_size_bytes) },
                                ]}
                                actions={
                                    <div className="absolute right-4 top-4 flex gap-1">
                                        <Link href={`/admin/presentations/${presentation.presentation_id}`}>
                                            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-slate-400 hover:bg-blue-50 hover:text-blue-600">
                                                <Edit2 className="h-4 w-4" />
                                            </Button>
                                        </Link>
                                        <Button
                                            onClick={() => setDeleteTarget(presentation)}
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 rounded-full text-slate-400 hover:bg-red-50 hover:text-red-600"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                }
                                className="relative"
                            >
                                <div className="pt-2">
                                    <AssetGovernanceSummaryCard summary={presentation.governance_summary} />
                                </div>
                            </MobileTableCard>
                        );
                    })}
                </div>

                <div className="hidden overflow-x-auto md:block">
                    <table className="w-full text-left text-sm">
                        <thead className="border-b border-slate-100 bg-slate-50/50 text-xs font-bold uppercase tracking-wider text-slate-400">
                            <tr>
                                <th className="px-6 py-4">PPT标题</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">页数</th>
                                <th className="px-6 py-4">文件大小</th>
                                <th className="px-6 py-4">上传时间</th>
                                <th className="min-w-[22rem] px-6 py-4">治理上下文</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filteredPresentations.map((presentation) => {
                                const statusStyle = getStatusStyle(presentation.status);
                                return (
                                    <tr key={presentation.presentation_id} className="group transition-colors hover:bg-slate-50/50">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-orange-50 text-orange-600 transition-colors group-hover:bg-orange-100">
                                                    <Presentation className="h-5 w-5" />
                                                </div>
                                                <div className="font-bold text-slate-900">{presentation.title}</div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className={`inline-flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1.5 text-sm font-medium ${statusStyle.color}`}>
                                                <div className={`h-1.5 w-1.5 rounded-full ${statusStyle.dotColor}`} />
                                                {statusStyle.label}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 font-medium text-slate-700">{presentation.page_count || 0} 页</td>
                                        <td className="px-6 py-4 text-slate-500">{formatFileSize(presentation.file_size_bytes)}</td>
                                        <td className="px-6 py-4 text-slate-500">{new Date(presentation.created_at).toLocaleDateString("zh-CN")}</td>
                                        <td className="px-6 py-4 align-top">
                                            <AssetGovernanceSummaryCard summary={presentation.governance_summary} className="min-w-[20rem]" />
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex justify-end gap-1">
                                                <Link href={`/admin/presentations/${presentation.presentation_id}`}>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-slate-400 hover:bg-blue-50 hover:text-blue-600">
                                                        <Edit2 className="h-4 w-4" />
                                                    </Button>
                                                </Link>
                                                <Button
                                                    onClick={() => setDeleteTarget(presentation)}
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 rounded-full text-slate-400 hover:bg-red-50 hover:text-red-600"
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {filteredPresentations.length === 0 && !isLoading ? (
                    <div className="py-16 text-center">
                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100">
                            <Presentation className="h-8 w-8 text-slate-400" />
                        </div>
                        <h3 className="mb-1 text-lg font-medium text-slate-900">暂无PPT</h3>
                        <p className="text-sm text-slate-500">点击“上传PPT”按钮添加第一个演示文稿</p>
                    </div>
                ) : null}

                {isLoading ? (
                    <div className="py-16 text-center">
                        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500" />
                        <p className="text-sm text-slate-500">加载中...</p>
                    </div>
                ) : null}

                <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4">
                    <span className="text-xs font-medium text-slate-400">
                        显示 {filteredPresentations.length > 0 ? `${(page - 1) * 10 + 1}-${(page - 1) * 10 + filteredPresentations.length}` : "0"} 个PPT
                    </span>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" className="h-8 rounded-full text-xs" disabled={page === 1} onClick={() => setPage((prev) => prev - 1)}>
                            上一页
                        </Button>
                        <Button variant="outline" size="sm" className="h-8 rounded-full text-xs" onClick={() => setPage((prev) => prev + 1)} disabled={filteredPresentations.length < 10}>
                            下一页
                        </Button>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}
