"use client";
import { debug } from "@/lib/debug";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { SessionItem } from "@/lib/api/types";
import { GlassCard } from "@/components/ui/glass-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Filter, Download, FileText, Eye, Activity, Calendar, Trash2 } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
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
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/glass-tooltip";
import {
    MobileTableCard
} from "@/components/ui/mobile-table-card";

// Helper Functions
const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}分 ${s}秒`;
};

const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleString();
};

const PAGE_SIZE = 10;

export default function RecordsPage() {
    const { success: showSuccessToast, error: showErrorToast, showToast } = useToast();
    const [records, setRecords] = useState<SessionItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<SessionItem | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Filter & Search States
    const [searchQuery, setSearchQuery] = useState("");
    const [categoryFilter, setCategoryFilter] = useState("all");
    const [page, setPage] = useState(1);
    const [isFilterOpen, setIsFilterOpen] = useState(false);

    const loadData = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.admin.getTrainingRecords({
                search: searchQuery,
                category: categoryFilter,
                page: page,
                page_size: PAGE_SIZE
            });
            setRecords(data);
        } catch (err) {
            debug.error("Failed to load records:", err);
            const message = err instanceof Error ? err.message : "训练记录加载失败";
            setError(message);
            showErrorToast(message);
            setRecords([]);
        } finally {
            setIsLoading(false);
        }
    }, [categoryFilter, page, searchQuery, showErrorToast]);

    const handleDelete = async () => {
        if (!deleteTarget) return;

        setIsDeleting(true);
        try {
            await api.admin.deleteTrainingRecord(deleteTarget.id);
            setRecords(prev => prev.filter((record) => record.id !== deleteTarget.id));
            showSuccessToast("删除成功");
            setDeleteTarget(null);
        } catch (err) {
            debug.error("Failed to delete record:", err);
            showErrorToast("删除失败");
        } finally {
            setIsDeleting(false);
        }
    };

    const handleApplyFilter = () => {
        setIsFilterOpen(false);
        setPage(1);
    };

    useEffect(() => {
        loadData();
    }, [loadData]);

    if (isLoading) {
        return <div className="p-8 text-center text-slate-500">加载中...</div>;
    }

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => {
                    if (!open) {
                        setDeleteTarget(null);
                    }
                }}
                title="删除训练记录"
                description={deleteTarget ? `确定要删除「${deleteTarget.title}」吗？` : "确定要删除这条训练记录吗？"}
                confirmText="删除"
                variant="danger"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight">训练记录</h1>
                    <p className="text-slate-500 mt-1">查看所有用户的训练历史</p>
                </div>
                <div className="flex gap-3">
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="outline" className="rounded-full border-slate-200 text-slate-600 hover:bg-slate-50">
                                <Download className="w-4 h-4 mr-2" /> 导出记录
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>导出记录</DialogTitle>
                                <DialogDescription>选择日期范围和格式。</DialogDescription>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-slate-400 uppercase">开始日期</label>
                                        <div className="relative">
                                            <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                            <input type="date" className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm" />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-xs font-bold text-slate-400 uppercase">结束日期</label>
                                        <div className="relative">
                                            <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                            <input type="date" className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm" />
                                        </div>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <label className="text-xs font-bold text-slate-400 uppercase">格式</label>
                                    <div className="flex gap-4">
                                        <div className="flex-1 p-3 border-2 border-blue-500 bg-blue-50 rounded-xl text-center cursor-pointer">
                                            <span className="font-bold text-blue-700">Excel / CSV</span>
                                        </div>
                                        <div className="flex-1 p-3 border border-slate-200 bg-slate-50 rounded-xl text-center cursor-pointer hover:border-slate-300">
                                            <span className="font-bold text-slate-600">PDF 报告</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button className="w-full rounded-full bg-slate-900 text-white" onClick={() => showToast("导出任务已提交，完成后会生成下载文件。", "info")}>下载</Button>
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
                        placeholder="搜索记录标题..."
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
                                <DialogTitle>筛选记录</DialogTitle>
                            </DialogHeader>
                            <div className="py-6 space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">评分范围</label>
                                    <input type="range" className="w-full accent-blue-600" />
                                    <div className="flex justify-between text-xs text-slate-500 mt-1">
                                        <span>0</span>
                                        <span>100</span>
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 block">场景类型</label>
                                    <div className="flex flex-wrap gap-2">
                                        {[
                                            { id: 'all', label: '全部' },
                                            { id: 'sales', label: '销售对练' },
                                            { id: 'presentation', label: 'PPT 演示' },
                                        ].map(c => (
                                            <Badge 
                                                key={c.id}
                                                variant={categoryFilter === c.id ? 'blue' : 'secondary'}
                                                className="cursor-pointer"
                                                onClick={() => setCategoryFilter(c.id)}
                                            >
                                                {c.label}
                                            </Badge>
                                        ))}
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

            {/* Records Table */}
            <GlassCard className="overflow-hidden">
                {error ? (
                    <div className="m-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                        <p className="font-semibold">训练记录加载失败</p>
                        <p className="mt-1">{error}</p>
                        <Button variant="outline" className="mt-3 rounded-full" onClick={() => void loadData()}>重试</Button>
                    </div>
                ) : null}
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4 p-4">
                    {records.map((record) => (
                        <MobileTableCard
                            key={record.id}
                            title={
                                <div>
                                    <div className="font-bold text-slate-900">{record.title}</div>
                                    <div className="text-slate-400 text-xs">{record.id}</div>
                                </div>
                            }
                            icon={
                                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold
                                    ${record.scenario_type === 'sales' ? 'bg-blue-50 text-blue-600' :
                                        record.scenario_type === 'presentation' ? 'bg-purple-50 text-purple-600' :
                                            'bg-slate-100 text-slate-500'}`}>
                                    <FileText className="w-5 h-5" />
                                </div>
                            }
                            columns={[
                                {
                                    label: "评分",
                                    value: <span className={`font-bold ${record.overall_score >= 80 ? 'text-emerald-600' : record.overall_score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>{record.overall_score}</span>
                                }
                            ]}
                            actions={
                                <div className="absolute top-4 right-4">
                                    <Button
                                        onClick={() => setDeleteTarget(record)}
                                        aria-label={`删除记录 ${record.title}`}
                                        variant="ghost"
                                        size="icon"
                                        className="text-slate-400 hover:text-red-600 rounded-full"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </Button>
                                </div>
                            }
                            className="relative"
                        >
                            <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-50 mt-2">
                                <span>{formatDuration(record.duration_seconds)}</span>
                                <span>{new Date(record.start_time).toLocaleDateString()}</span>
                            </div>
                        </MobileTableCard>
                    ))}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase font-bold text-slate-400 tracking-wider">
                            <tr>
                                <th className="px-6 py-4">记录ID</th>
                                <th className="px-6 py-4">场景名称</th>
                                <th className="px-6 py-4">类型</th>
                                <th className="px-6 py-4">评分</th>
                                <th className="px-6 py-4">时长</th>
                                <th className="px-6 py-4">日期</th>
                                <th className="px-6 py-4 text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {records.map((record) => (
                                <tr key={record.id} className="hover:bg-slate-50/50 transition-colors group">
                                    <td className="px-6 py-4 font-mono text-xs text-slate-500">
                                        {record.id}
                                    </td>
                                    <td className="px-6 py-4 font-medium text-slate-900">
                                        {record.title}
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="secondary" className="bg-slate-50 text-slate-600 font-normal border-slate-200">
                                            {record.scenario_type === 'sales' ? '销售教练' : 'PPT演讲'}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${record.overall_score >= 80 ? 'bg-emerald-500' : record.overall_score >= 60 ? 'bg-amber-500' : record.overall_score >= 60 ? 'bg-amber-500' : 'bg-red-500'}`} />
                                            <span className={`font-bold ${record.overall_score >= 80 ? 'text-emerald-600' : record.overall_score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
                                                {record.overall_score}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-slate-500">
                                        {formatDuration(record.duration_seconds)}
                                    </td>
                                    <td className="px-6 py-4 text-slate-500">
                                        {formatTime(record.start_time)}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex justify-end gap-2">
                                            <TooltipProvider>
                                                <Dialog>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <DialogTrigger asChild>
                                                                <Button variant="ghost" size="icon" className="text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-full">
                                                                    <Eye className="w-4 h-4" />
                                                                </Button>
                                                            </DialogTrigger>
                                                        </TooltipTrigger>
                                                        <TooltipContent>查看详情</TooltipContent>
                                                    </Tooltip>
                                                    <DialogContent className="max-w-3xl">
                                                        <DialogHeader>
                                                            <DialogTitle className="flex items-center gap-2">
                                                                <FileText className="w-5 h-5 text-slate-400" />
                                                                会话详情: {record.id}
                                                            </DialogTitle>
                                                            <DialogDescription>{formatTime(record.start_time)}</DialogDescription>
                                                        </DialogHeader>
                                                        <div className="py-6 grid grid-cols-3 gap-6">
                                                            <div className="col-span-2 space-y-6">
                                                                <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100">
                                                                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">分析总结</h4>
                                                                    <p className="text-sm text-slate-700 leading-relaxed">
                                                                        {record.feedback_summary || "暂无反馈摘要。该会话未返回可展示的总结内容。"}
                                                                    </p>
                                                                </div>
                                                                <div>
                                                                    <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">关键指标</h4>
                                                                    <div className="grid grid-cols-2 gap-3">
                                                                        <div className="p-3 bg-white border border-slate-100 rounded-xl shadow-sm">
                                                                            <div className="text-slate-500 text-xs">清晰度</div>
                                                                            <div className="text-xl font-bold text-slate-900">高</div>
                                                                        </div>
                                                                        <div className="p-3 bg-white border border-slate-100 rounded-xl shadow-sm">
                                                                            <div className="text-slate-500 text-xs">语速</div>
                                                                            <div className="text-xl font-bold text-slate-900">标准</div>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <div className="col-span-1 space-y-4">
                                                                <div className="w-full bg-slate-900 rounded-2xl p-4 text-white text-center">
                                                                    <div className="text-4xl font-black">{record.overall_score}</div>
                                                                    <div className="text-xs text-slate-400 uppercase tracking-widest mt-1">总评分</div>
                                                                </div>
                                                                <div className="space-y-2">
                                                                    <Button variant="outline" className="w-full justify-start rounded-xl border-slate-200">
                                                                        <Download className="w-4 h-4 mr-2" /> 下载报告
                                                                    </Button>
                                                                    <Button variant="outline" className="w-full justify-start rounded-xl border-slate-200">
                                                                        <Activity className="w-4 h-4 mr-2" /> 查看文字记录
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </DialogContent>
                                                </Dialog>
                                            </TooltipProvider>
                                            <Button
                                                onClick={() => setDeleteTarget(record)}
                                                aria-label={`删除记录 ${record.title}`}
                                                variant="ghost"
                                                size="icon"
                                                className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-full"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                 {/* Pagination */}
                 <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-400 font-medium">第 {page} 页</span>
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
                            disabled={records.length < PAGE_SIZE || isLoading}
                            onClick={() => setPage(p => p + 1)}
                        >
                            下一页
                        </Button>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}
