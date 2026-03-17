"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { AdminAgent } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Search, Filter, Plus, Bot, Edit2, Trash2, ChevronDown } from "lucide-react";
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

type AgentStatus = "published" | "draft" | "archived";

const STATUS_OPTIONS: { value: AgentStatus; label: string; color: string; dotColor: string }[] = [
    { value: "published", label: "已发布", color: "text-emerald-600", dotColor: "bg-emerald-500" },
    { value: "draft", label: "草稿", color: "text-slate-500", dotColor: "bg-slate-400" },
    { value: "archived", label: "已归档", color: "text-amber-600", dotColor: "bg-amber-500" },
];

function getStatusStyle(status: string) {
    const option = STATUS_OPTIONS.find(o => o.value === status);
    return option || STATUS_OPTIONS[1];
}

export default function AgentsPage() {
    const toast = useToast();
    const [agents, setAgents] = useState<AdminAgent[]>([]);

    // Filter & Search States
    const [searchQuery, setSearchQuery] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");
    const [page, setPage] = useState(1);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    // Create Dialog States
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [newAgentName, setNewAgentName] = useState("");
    const [newAgentDescription, setNewAgentDescription] = useState("");
    const [newAgentCategory, setNewAgentCategory] = useState("sales");
    const [isCreating, setIsCreating] = useState(false);

    // Delete Confirm Dialog
    const [deleteTarget, setDeleteTarget] = useState<AdminAgent | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Status dropdown
    const [statusDropdownId, setStatusDropdownId] = useState<string | null>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = () => setStatusDropdownId(null);
        if (statusDropdownId) {
            document.addEventListener('click', handleClickOutside);
            return () => document.removeEventListener('click', handleClickOutside);
        }
    }, [statusDropdownId]);

    const loadData = async () => {
        try {
            const data = await api.admin.getAgents({
                search: searchQuery || undefined,
                status: statusFilter !== "all" ? statusFilter : undefined,
                page: page,
                page_size: 10
            });
            setAgents(data.items || []);
        } catch (err) {
            console.error("Failed to load agents:", err);
            setAgents([]);
        }
    };

    useEffect(() => {
        loadData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, statusFilter, searchQuery]);

    const handleCreate = async () => {
        if (!newAgentName.trim()) {
            toast.error("请输入智能体名称");
            return;
        }

        setIsCreating(true);

        try {
            await api.admin.createAgent({
                name: newAgentName,
                description: newAgentDescription || undefined,
                category: newAgentCategory
            });

            setIsCreateOpen(false);
            setNewAgentName("");
            setNewAgentDescription("");
            setNewAgentCategory("sales");
            toast.success("智能体创建成功");
            loadData();
        } catch (err) {
            console.error("Failed to create agent:", err);
            toast.error(`创建失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsCreating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await api.admin.deleteAgent(deleteTarget.id);
            setAgents(prev => prev.filter(a => a.id !== deleteTarget.id));
            toast.success("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            console.error("Failed to delete agent:", err);
            toast.error(`删除失败: ${err instanceof Error ? err.message : "未知错误"}`);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleStatusChange = async (agent: AdminAgent, newStatus: AgentStatus) => {
        if (agent.status === newStatus) {
            setStatusDropdownId(null);
            return;
        }

        try {
            if (newStatus === "published") {
                await api.admin.publishAgent(agent.id);
                toast.success("发布成功");
            } else if (newStatus === "archived") {
                await api.admin.archiveAgent(agent.id);
                toast.success("已归档");
            } else if (newStatus === "draft") {
                await api.admin.unpublishAgent(agent.id);
                toast.success("已改为草稿");
            }
            setStatusDropdownId(null);
            loadData();
        } catch (err) {
            console.error("Failed to change status:", err);
            toast.error(`状态更新失败: ${err instanceof Error ? err.message : "未知错误"}`);
        }
    };

    const handleApplyFilter = () => {
        setIsFilterOpen(false);
        setPage(1);
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Delete Confirm Dialog */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="删除智能体"
                description={`确定要删除「${deleteTarget?.name}」吗？此操作不可撤销。`}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">智能体管理</h1>
                    <p className="text-slate-500 mt-1">管理 AI 智能体配置</p>
                </div>
                <div className="flex gap-3">
                    <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                        <DialogTrigger asChild>
                            <Button
                                type="button"
                                className="rounded-full bg-slate-900 hover:bg-slate-800 text-white shadow-lg shadow-slate-900/20"
                            >
                                <Plus className="w-4 h-4 mr-2" /> 新建智能体
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>新建智能体</DialogTitle>
                                <DialogDescription>创建一个新的 AI 训练场景。</DialogDescription>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">智能体名称</label>
                                    <input
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                        placeholder="例如：销售教练"
                                        value={newAgentName}
                                        onChange={(e) => setNewAgentName(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">类别</label>
                                    <select
                                        className="w-full h-10 rounded-lg border border-slate-200 px-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
                                        value={newAgentCategory}
                                        onChange={(e) => setNewAgentCategory(e.target.value)}
                                    >
                                        <option value="sales">销售</option>
                                        <option value="presentation">演讲</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">描述</label>
                                    <textarea
                                        className="w-full h-24 rounded-lg border border-slate-200 p-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                                        placeholder="描述该智能体的功能..."
                                        value={newAgentDescription}
                                        onChange={(e) => setNewAgentDescription(e.target.value)}
                                    />
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
                        placeholder="搜索智能体..."
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
                                <DialogTitle>筛选智能体</DialogTitle>
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
                                            variant={statusFilter === 'published' ? 'blue' : 'secondary'}
                                            className="cursor-pointer"
                                            onClick={() => setStatusFilter('published')}
                                        >
                                            已发布
                                        </Badge>
                                        <Badge
                                            variant={statusFilter === 'draft' ? 'blue' : 'secondary'}
                                            className="cursor-pointer"
                                            onClick={() => setStatusFilter('draft')}
                                        >
                                            草稿
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

            {/* Agents Table */}
            <GlassCard className="overflow-hidden">
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4 p-4">
                    {agents.map((agent) => {
                        const statusStyle = getStatusStyle(agent.status);
                        return (
                            <MobileTableCard
                                key={agent.id}
                                title={
                                    <div>
                                        <div className="font-bold text-slate-900">{agent.name}</div>
                                    </div>
                                }
                                icon={
                                    <div className="w-10 h-10 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600">
                                        <Bot className="w-5 h-5" />
                                    </div>
                                }
                                columns={[
                                    {
                                        label: "状态",
                                        value: (
                                            <div className="relative">
                                                <button
                                                    onClick={() => setStatusDropdownId(statusDropdownId === agent.id ? null : agent.id)}
                                                    className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-colors hover:bg-slate-100 ${statusStyle.color}`}
                                                >
                                                    <div className={`w-1.5 h-1.5 rounded-full ${statusStyle.dotColor}`} />
                                                    {statusStyle.label}
                                                    <ChevronDown className="w-3 h-3" />
                                                </button>
                                                {statusDropdownId === agent.id && (
                                                    <div className="absolute top-full left-0 mt-1 bg-white rounded-xl shadow-lg border border-slate-100 py-1 z-50 min-w-[100px]">
                                                        {STATUS_OPTIONS.map(option => (
                                                            <button
                                                                key={option.value}
                                                                onClick={() => handleStatusChange(agent, option.value)}
                                                                className={`w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-slate-50 ${option.color} ${agent.status === option.value ? 'bg-slate-50' : ''}`}
                                                            >
                                                                <div className={`w-1.5 h-1.5 rounded-full ${option.dotColor}`} />
                                                                {option.label}
                                                            </button>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    },
                                    {
                                        label: "角色数",
                                        value: agent.persona_count || 0
                                    }
                                ]}
                                actions={
                                    <div className="absolute top-4 right-4 flex gap-1">
                                        <Link href={`/admin/agents/${agent.id}`}>
                                            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                <Edit2 className="w-4 h-4" />
                                            </Button>
                                        </Link>
                                        <Button
                                            onClick={() => setDeleteTarget(agent)}
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                }
                                className="relative"
                            >
                                <div className="text-xs text-slate-500 pt-2">{agent.description}</div>
                            </MobileTableCard>
                        );
                    })}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                            <tr>
                                <th className="px-6 py-4">智能体名称</th>
                                <th className="px-6 py-4">描述</th>
                                <th className="px-6 py-4">状态</th>
                                <th className="px-6 py-4">角色数量</th>
                                <th className="px-6 py-4">练习次数</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {agents.map((agent) => {
                                const statusStyle = getStatusStyle(agent.status);
                                return (
                                    <tr key={agent.id} className="hover:bg-slate-50/50 transition-colors group">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-100 transition-colors">
                                                    <Bot className="w-5 h-5" />
                                                </div>
                                                <div className="font-bold text-slate-900">{agent.name}</div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-slate-500 max-w-xs truncate">
                                            {agent.description}
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="relative">
                                                <button
                                                    onClick={() => setStatusDropdownId(statusDropdownId === agent.id ? null : agent.id)}
                                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors hover:bg-slate-100 ${statusStyle.color}`}
                                                >
                                                    <div className={`w-1.5 h-1.5 rounded-full ${statusStyle.dotColor}`} />
                                                    {statusStyle.label}
                                                    <ChevronDown className="w-3.5 h-3.5" />
                                                </button>
                                                {statusDropdownId === agent.id && (
                                                    <div className="absolute top-full left-0 mt-1 bg-white rounded-xl shadow-lg border border-slate-100 py-1 z-50 min-w-[120px]">
                                                        {STATUS_OPTIONS.map(option => (
                                                            <button
                                                                key={option.value}
                                                                onClick={() => handleStatusChange(agent, option.value)}
                                                                className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-50 ${option.color} ${agent.status === option.value ? 'bg-slate-50' : ''}`}
                                                            >
                                                                <div className={`w-1.5 h-1.5 rounded-full ${option.dotColor}`} />
                                                                {option.label}
                                                            </button>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 font-medium text-slate-700">
                                            {agent.persona_count || 0}
                                        </td>
                                        <td className="px-6 py-4 font-medium text-slate-700">
                                            {agent.usage_count}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex justify-end gap-1">
                                                <Link href={`/admin/agents/${agent.id}`}>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                        <Edit2 className="w-4 h-4" />
                                                    </Button>
                                                </Link>
                                                <Button
                                                    onClick={() => setDeleteTarget(agent)}
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
                {/* Pagination */}
                <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-medium">显示 {agents.length > 0 ? `${(page - 1) * 10 + 1}-${(page - 1) * 10 + agents.length}` : '0'} 个智能体</span>
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
                            disabled={agents.length < 10}
                        >
                            下一页
                        </Button>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}
