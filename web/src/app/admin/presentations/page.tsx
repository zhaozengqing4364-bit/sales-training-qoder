"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Search, Filter, Plus, Edit2, Trash2, Presentation } from "lucide-react";
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

// Presentation types (to be added to types.ts)
interface PresentationItem {
    presentation_id: string;
    title: string;
    status: "processing" | "ready" | "failed";
    file_size_bytes: number;
    page_count: number;
    uploaded_by_admin_id: string;
    created_at: string;
}

type PresentationStatus = "processing" | "ready" | "failed";

const STATUS_OPTIONS: { value: PresentationStatus; label: string; color: string; dotColor: string }[] = [
    { value: "ready", label: "可用", color: "text-emerald-600", dotColor: "bg-emerald-500" },
    { value: "processing", label: "处理中", color: "text-blue-600", dotColor: "bg-blue-500" },
    { value: "failed", label: "失败", color: "text-red-600", dotColor: "bg-red-500" },
];

function getStatusStyle(status: string) {
    const option = STATUS_OPTIONS.find(o => o.value === status);
    return option || STATUS_OPTIONS[1];
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export default function PresentationsPage() {
    const toast = useToast();
    const [presentations, setPresentations] = useState<PresentationItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Filter & Search States
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [page, setPage] = useState(1);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    // Create Dialog States
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [newTitle, setNewTitle] = useState("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isCreating, setIsCreating] = useState(false);

    // Delete Confirm Dialog
    const [deleteTarget, setDeleteTarget] = useState<PresentationItem | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const loadData = async () => {
        setIsLoading(true);
        try {
            // Use the presentations API
            const data = await api.presentations.list({
                status: statusFilter !== "all" ? statusFilter : undefined,
                limit: 20
            });
            setPresentations(data || []);
        } catch (err) {
            console.error("Failed to load presentations:", err);
            setPresentations([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
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
            await api.presentations.upload({
                title: newTitle,
                file: selectedFile
            });

            setIsCreateOpen(false);
            setNewTitle("");
            setSelectedFile(null);
            toast.success("PPT上传成功");
            loadData();
        } catch (err) {
            console.error("Failed to upload presentation:", err);
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
            setPresentations(prev => prev.filter(p => p.presentation_id !== deleteTarget.presentation_id));
            toast.success("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            console.error("Failed to delete presentation:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleApplyFilter = () => {
        setIsFilterOpen(false);
        setPage(1);
    };

    // Filter presentations by search query
    const filteredPresentations = presentations.filter(p =>
        p.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Delete Confirm Dialog */}
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

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">PPT演练管理</h1>
                    <p className="text-slate-500 mt-1">管理PPT演示文稿和演练配置</p>
                </div>
                <div className="flex gap-3">
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button
                                type="button"
                                className="rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20"
                            >
                                <Plus className="w-4 h-4 mr-2" /> 上传PPT
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>上传PPT</DialogTitle>
                                <DialogDescription>上传一个新的PPT演示文稿用于演练。</DialogDescription>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">PPT标题</label>
                                    <input
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                        placeholder="例如：产品发布演讲"
                                        value={newTitle}
                                        onChange={(e) => setNewTitle(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">PPT文件</label>
                                    <input
                                        type="file"
                                        accept=".ppt,.pptx"
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                                        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                                    />
                                    <p className="text-xs text-slate-400">支持 .ppt 和 .pptx 格式</p>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    className="rounded-full"
                                    onClick={() => setIsCreateOpen(false)}
                                >
                                    取消
                                </Button>
                                <Button
                                    type="button"
                                    className="rounded-full bg-slate-900 text-white"
                                    onClick={handleCreate}
                                    disabled={isCreating}
                                >
                                    {isCreating ? "上传中..." : "上传"}
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
                        placeholder="搜索PPT..."
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
                                <DialogTitle>筛选PPT</DialogTitle>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">状态</label>
                                    <div className="flex flex-wrap gap-2">
                                        <Badge
                                            variant={statusFilter === 'all' ? 'blue' : 'secondary'}
                                            className="cursor-pointer"
                                            onClick={() => setStatusFilter('all')}
                                        >
                                            全部
                                        </Badge>
                                        <Badge
                                            variant={statusFilter === 'ready' ? 'blue' : 'secondary'}
                                            className="cursor-pointer"
                                            onClick={() => setStatusFilter('ready')}
                                        >
                                            可用
                                        </Badge>
                                        <Badge
                                            variant={statusFilter === 'processing' ? 'blue' : 'secondary'}
                                            className="cursor-pointer"
                                            onClick={() => setStatusFilter('processing')}
                                        >
                                            处理中
                                        </Badge>
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

            {/* Presentations Table */}
            <GlassCard className="overflow-hidden">
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4 p-4">
                    {filteredPresentations.map((presentation) => {
                        const statusStyle = getStatusStyle(presentation.status);
                        return (
                            <MobileTableCard
                                key={presentation.presentation_id}
                                title={
                                    <div>
                                        <div className="font-bold text-slate-900">{presentation.title}</div>
                                    </div>
                                }
                                icon={
                                    <div className="w-10 h-10 rounded-full bg-orange-50 flex items-center justify-center text-orange-600">
                                        <Presentation className="w-5 h-5" />
                                    </div>
                                }
                                columns={[
                                    {
                                        label: "状态",
                                        value: (
                                            <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${statusStyle.color}`}>
                                                <div className={`w-1.5 h-1.5 rounded-full ${statusStyle.dotColor}`} />
                                                {statusStyle.label}
                                            </div>
                                        )
                                    },
                                    {
                                        label: "页数",
                                        value: `${presentation.page_count || 0} 页`
                                    },
                                    {
                                        label: "大小",
                                        value: formatFileSize(presentation.file_size_bytes)
                                    }
                                ]}
                                actions={
                                    <div className="absolute top-4 right-4 flex gap-1">
                                        <Link href={`/admin/presentations/${presentation.presentation_id}`}>
                                            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                <Edit2 className="w-4 h-4" />
                                            </Button>
                                        </Link>
                                        <Button
                                            onClick={() => setDeleteTarget(presentation)}
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                }
                                className="relative"
                            />
                        );
                    })}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                            <tr>
                                <th className="px-6 py-4">PPT标题</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">页数</th>
                                <th className="px-6 py-4">文件大小</th>
                                <th className="px-6 py-4">上传时间</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filteredPresentations.map((presentation) => {
                                const statusStyle = getStatusStyle(presentation.status);
                                return (
                                    <tr key={presentation.presentation_id} className="hover:bg-slate-50/50 transition-colors group">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-full bg-orange-50 flex items-center justify-center text-orange-600 group-hover:bg-orange-100 transition-colors">
                                                    <Presentation className="w-5 h-5" />
                                                </div>
                                                <div className="font-bold text-slate-900">{presentation.title}</div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${statusStyle.color} bg-slate-50`}>
                                                <div className={`w-1.5 h-1.5 rounded-full ${statusStyle.dotColor}`} />
                                                {statusStyle.label}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 font-medium text-slate-700">
                                            {presentation.page_count || 0} 页
                                        </td>
                                        <td className="px-6 py-4 text-slate-500">
                                            {formatFileSize(presentation.file_size_bytes)}
                                        </td>
                                        <td className="px-6 py-4 text-slate-500">
                                            {new Date(presentation.created_at).toLocaleDateString('zh-CN')}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex justify-end gap-1">
                                                <Link href={`/admin/presentations/${presentation.presentation_id}`}>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                        <Edit2 className="w-4 h-4" />
                                                    </Button>
                                                </Link>
                                                <Button
                                                    onClick={() => setDeleteTarget(presentation)}
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Empty State */}
                {filteredPresentations.length === 0 && !isLoading && (
                    <div className="py-16 text-center">
                        <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
                            <Presentation className="w-8 h-8 text-slate-400" />
                        </div>
                        <h3 className="text-lg font-medium text-slate-900 mb-1">暂无PPT</h3>
                        <p className="text-slate-500 text-sm">点击“上传PPT”按钮添加第一个演示文稿</p>
                    </div>
                )}

                {/* Loading State */}
                {isLoading && (
                    <div className="py-16 text-center">
                        <div className="w-8 h-8 border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-slate-500 text-sm">加载中...</p>
                    </div>
                )}

                {/* Pagination */}
                <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-medium">
                        显示 {filteredPresentations.length > 0 ? `${(page - 1) * 10 + 1}-${(page - 1) * 10 + filteredPresentations.length}` : '0'} 个PPT
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
                            disabled={filteredPresentations.length < 10}
                        >
                            下一页
                        </Button>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}
