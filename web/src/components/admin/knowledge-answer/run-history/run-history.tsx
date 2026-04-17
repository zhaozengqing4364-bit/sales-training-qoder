"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp, Search, Loader2, X, History } from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { useToast } from "@/components/ui/toast";
import { RunDetail } from "./run-detail";
import type {
    AdminKnowledgeAnswerRunListItem,
    AdminKnowledgeAnswerRunDetail,
    AdminKnowledgeAnswerRunStep,
} from "@/lib/api/types";

const PAGE_SIZE = 10;

const ANSWERABILITY_OPTIONS = [
    { value: "", label: "全部回答约束" },
    { value: "sufficient", label: "证据充分" },
    { value: "partial", label: "部分充分" },
    { value: "insufficient", label: "证据不足" },
    { value: "blocked", label: "已阻止" },
];

const STATUS_OPTIONS = [
    { value: "", label: "全部运行状态" },
    { value: "completed", label: "已完成" },
    { value: "failed", label: "失败" },
    { value: "blocked", label: "已阻止" },
    { value: "running", label: "运行中" },
];

const ANSWERABILITY_LABEL_MAP: Record<string, string> = Object.fromEntries(
    ANSWERABILITY_OPTIONS.filter((option) => option.value).map((option) => [option.value, option.label]),
);

const STATUS_LABEL_MAP: Record<string, string> = Object.fromEntries(
    STATUS_OPTIONS.filter((option) => option.value).map((option) => [option.value, option.label]),
);

const ANSWERABILITY_BADGE_MAP: Record<string, string> = {
    sufficient: "bg-green-100 text-green-800",
    partial: "bg-amber-100 text-amber-800",
    insufficient: "bg-slate-200 text-slate-600",
    blocked: "bg-red-100 text-red-700",
};

const STATUS_BADGE_MAP: Record<string, string> = {
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-700",
    blocked: "bg-amber-100 text-amber-800",
    running: "bg-blue-100 text-blue-700",
    pending: "bg-slate-200 text-slate-600",
};

function formatTimestamp(ts: string): string {
    return new Date(ts).toLocaleString("zh-CN", { hour12: false });
}

interface ExpandedRunData {
    detail: AdminKnowledgeAnswerRunDetail;
    steps: AdminKnowledgeAnswerRunStep[];
}

export function RunHistory() {
    const toast = useToast();

    // Section collapsed state
    const [expanded, setExpanded] = useState(true);

    // Filter state
    const [searchText, setSearchText] = useState("");
    const [answerabilityFilter, setAnswerabilityFilter] = useState("");
    const [statusFilter, setStatusFilter] = useState("");

    // Active filters (applied)
    const [activeSearch, setActiveSearch] = useState("");
    const [activeAnswerability, setActiveAnswerability] = useState("");
    const [activeStatus, setActiveStatus] = useState("");

    // Data state
    const [runs, setRuns] = useState<AdminKnowledgeAnswerRunListItem[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);

    // Expanded run detail
    const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
    const [expandedData, setExpandedData] = useState<ExpandedRunData | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    const loadRuns = useCallback(async (p: number, search: string, answerability: string, status: string) => {
        setLoading(true);
        try {
            const params: {
                limit: number;
                page: number;
                query?: string;
                answerability?: string;
                final_status?: string;
            } = {
                limit: PAGE_SIZE,
                page: p,
                query: search || undefined,
                answerability: answerability || undefined,
                final_status: status || undefined,
            };
            const result = await api.admin.listKnowledgeAnswerRuns(params);
            setRuns(result.items);
            setTotal(result.total);
        } catch (err) {
            toast.error("加载运行记录失败: " + getApiErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }, [toast]);

    // Initial load when section is expanded
    useEffect(() => {
        if (expanded) {
            loadRuns(1, activeSearch, activeAnswerability, activeStatus);
            setPage(1);
        }
    }, [expanded, loadRuns, activeSearch, activeAnswerability, activeStatus]);

    function applyFilters() {
        setActiveSearch(searchText.trim());
        setActiveAnswerability(answerabilityFilter);
        setActiveStatus(statusFilter);
        setPage(1);
        setExpandedRunId(null);
        setExpandedData(null);
    }

    function clearFilters() {
        setSearchText("");
        setAnswerabilityFilter("");
        setStatusFilter("");
        setActiveSearch("");
        setActiveAnswerability("");
        setActiveStatus("");
        setPage(1);
        setExpandedRunId(null);
        setExpandedData(null);
    }

    const hasActiveFilters = activeSearch || activeAnswerability || activeStatus;
    const hasVisibleFilters = hasActiveFilters || searchText || answerabilityFilter || statusFilter;

    async function toggleRunDetail(runId: string) {
        if (expandedRunId === runId) {
            setExpandedRunId(null);
            setExpandedData(null);
            return;
        }

        setExpandedRunId(runId);
        setDetailLoading(true);
        try {
            const [detail, stepsRes] = await Promise.all([
                api.admin.getKnowledgeAnswerRunDetail(runId),
                api.admin.getKnowledgeAnswerRunSteps(runId),
            ]);
            setExpandedData({ detail, steps: stepsRes.items });
        } catch (err) {
            toast.error("加载运行详情失败: " + getApiErrorMessage(err));
            setExpandedRunId(null);
        } finally {
            setDetailLoading(false);
        }
    }

    return (
        <div className="space-y-3">
            {/* Section header */}
            <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left transition-colors hover:bg-slate-50"
            >
                <div className="flex items-center gap-2">
                    <History className="h-4 w-4 text-indigo-600" />
                    <span className="font-medium text-slate-900">最近知识问答运行（全局）</span>
                </div>
                {expanded ? (
                    <ChevronUp className="h-4 w-4 text-slate-500" />
                ) : (
                    <ChevronDown className="h-4 w-4 text-slate-500" />
                )}
            </button>

            {expanded && (
                <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
                    <p className="text-sm text-slate-500">当前展示的是全局最近运行记录，不保证只来自本知识库；请结合本页搜索诊断一起排查。</p>
                    {/* Filter bar */}
                    <div className="flex flex-wrap items-end gap-2">
                        <div className="min-w-[200px] flex-1">
                            <label className="mb-1 block text-xs text-slate-500">搜索</label>
                            <div className="relative">
                                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                <Input
                                    value={searchText}
                                    onChange={(e) => setSearchText(e.target.value)}
                                    placeholder="按 query 搜索 recent runs"
                                    className="h-9 pl-9 text-sm"
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") applyFilters();
                                    }}
                                />
                        </div>
                    </div>
                        <div>
                            <label className="mb-1 block text-xs text-slate-500">可回答性</label>
                            <select
                                value={answerabilityFilter}
                                onChange={(e) => setAnswerabilityFilter(e.target.value)}
                                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                            >
                                {ANSWERABILITY_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="mb-1 block text-xs text-slate-500">状态</label>
                            <select
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                            >
                                {STATUS_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                        {opt.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <Button onClick={applyFilters} size="sm" className="rounded-full">
                            应用筛选
                        </Button>
                    </div>

                    {/* Active filter badges */}
                    {hasVisibleFilters && (
                        <div className="flex flex-wrap items-center gap-1.5">
                            <span className="text-xs text-slate-400">当前筛选:</span>
                            {activeSearch && (
                                <Badge variant="secondary" className="flex items-center gap-1 pr-1 text-xs">
                                    搜索: {activeSearch}
                                    <button
                                        type="button"
                                        onClick={() => { setSearchText(""); setActiveSearch(""); }}
                                        className="rounded-full p-0.5 hover:bg-slate-300/50"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </Badge>
                            )}
                            {activeAnswerability && (
                                <Badge variant="secondary" className="flex items-center gap-1 pr-1 text-xs">
                                    可回答性: {activeAnswerability}
                                    <button
                                        type="button"
                                        onClick={() => { setAnswerabilityFilter(""); setActiveAnswerability(""); }}
                                        className="rounded-full p-0.5 hover:bg-slate-300/50"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </Badge>
                            )}
                            {activeStatus && (
                                <Badge variant="secondary" className="flex items-center gap-1 pr-1 text-xs">
                                    状态: {activeStatus}
                                    <button
                                        type="button"
                                        onClick={() => { setStatusFilter(""); setActiveStatus(""); }}
                                        className="rounded-full p-0.5 hover:bg-slate-300/50"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </Badge>
                            )}
                            <button
                                type="button"
                                aria-label="清空筛选条件"
                                onClick={clearFilters}
                                className="text-xs text-slate-500 underline decoration-slate-300 hover:text-slate-700"
                            >
                                清空筛选
                            </button>
                        </div>
                    )}

                    {/* Total count */}
                    <div className="text-xs text-slate-400">
                        当前第 {page} / {totalPages} 页 · 共 {total} 条 recent runs
                    </div>

                    {/* Run list */}
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                            <span className="ml-2 text-sm text-slate-500">加载中...</span>
                        </div>
                    ) : runs.length === 0 ? (
                        <div className="py-8 text-center text-sm text-slate-400">
                            当前筛选条件下暂无运行记录，可调整筛选或清空后重试。
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {runs.map((run) => {
                                const isExpanded = expandedRunId === run.id;
                                return (
                                    <div
                                        key={run.id}
                                        className="rounded-lg border border-slate-200 bg-white"
                                    >
                                        {/* Run header row */}
                                        <button
                                            type="button"
                                            aria-label="查看运行详情"
                                            onClick={() => toggleRunDetail(run.id)}
                                            className="flex w-full items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-slate-50"
                                        >
                                            <div className="min-w-0 flex-1 space-y-1">
                                                <p className="truncate text-sm font-medium text-slate-900">
                                                    {run.query_text}
                                                </p>
                                                <div className="flex flex-wrap items-center gap-1.5">
                                                    <Badge
                                                        className={
                                                            ANSWERABILITY_BADGE_MAP[run.answerability] ||
                                                            "bg-slate-100 text-slate-600"
                                                        }
                                                    >
                                                        {ANSWERABILITY_LABEL_MAP[run.answerability] || run.answerability}
                                                    </Badge>
                                                    <Badge
                                                        className={
                                                            STATUS_BADGE_MAP[run.final_status] ||
                                                            "bg-slate-100 text-slate-600"
                                                        }
                                                    >
                                                        {STATUS_LABEL_MAP[run.final_status] || run.final_status}
                                                    </Badge>
                                                    <span className="text-xs text-slate-400">
                                                        {run.step_count} 步
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="flex shrink-0 items-center gap-2">
                                                <span className="hidden text-xs text-slate-400 sm:inline-block">
                                                    {formatTimestamp(run.created_at)}
                                                </span>
                                                {isExpanded ? (
                                                    <ChevronUp className="h-4 w-4 text-slate-500" />
                                                ) : (
                                                    <ChevronDown className="h-4 w-4 text-slate-500" />
                                                )}
                                            </div>
                                        </button>

                                        {/* Expanded detail */}
                                        {isExpanded && (
                                            <div className="border-t border-slate-100 px-3 py-3">
                                                {detailLoading ? (
                                                    <div className="flex items-center justify-center py-4">
                                                        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                                                        <span className="ml-2 text-xs text-slate-500">加载详情...</span>
                                                    </div>
                                                ) : expandedData ? (
                                                    <RunDetail
                                                        detail={expandedData.detail}
                                                        steps={expandedData.steps}
                                                    />
                                                ) : null}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Pagination */}
                    <div className="flex items-center justify-between pt-2">
                        <span className="text-xs text-slate-400">
                                第 {page} / {totalPages} 页
                        </span>
                        <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="rounded-full"
                                    disabled={page <= 1}
                                    onClick={() => {
                                        const nextPage = page - 1;
                                        setPage(nextPage);
                                        loadRuns(nextPage, activeSearch, activeAnswerability, activeStatus);
                                    }}
                                >
                                    上一页
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="rounded-full"
                                    disabled={page >= totalPages}
                                    onClick={() => {
                                        const nextPage = page + 1;
                                        setPage(nextPage);
                                        loadRuns(nextPage, activeSearch, activeAnswerability, activeStatus);
                                    }}
                                >
                                    下一页
                                </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
