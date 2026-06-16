"use client";

import type { ReactNode } from "react";
import { BookOpen, Filter, RefreshCw, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type { SalesTrainerQuestionCategory } from "@/lib/api/types";

import { QUESTION_STATUS_LABELS } from "./question-display";

interface QuestionGovernanceSidebarProps {
    readonly aiScoredCount: number;
    readonly categories: readonly SalesTrainerQuestionCategory[];
    readonly categoryId: string;
    readonly difficulty: string;
    readonly onCategoryChange: (value: string) => void;
    readonly onDifficultyChange: (value: string) => void;
    readonly onRefresh: () => void;
    readonly onStatusChange: (value: string) => void;
    readonly onTagChange: (value: string) => void;
    readonly publishedCount: number;
    readonly questionCount: number;
    readonly status: string;
    readonly tag: string;
}

export function QuestionGovernanceSidebar({
    aiScoredCount,
    categories,
    categoryId,
    difficulty,
    onCategoryChange,
    onDifficultyChange,
    onRefresh,
    onStatusChange,
    onTagChange,
    publishedCount,
    questionCount,
    status,
    tag,
}: QuestionGovernanceSidebarProps) {
    return (
        <aside className="space-y-4">
            <GlassCard className="space-y-5 p-5">
                <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white">
                        <BookOpen className="h-5 w-5" aria-hidden />
                    </div>
                    <div>
                        <h2 className="text-base font-bold text-slate-900">正式题目概览</h2>
                        <p className="text-xs text-slate-500">发布后才会进入学员小测候选池</p>
                    </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                    <MetricTile label="正式题目" value={questionCount} tone="slate" />
                    <MetricTile label="已发布" value={publishedCount} tone="emerald" />
                    <MetricTile label="AI评分" value={aiScoredCount} tone="blue" />
                </div>
            </GlassCard>

            <GlassCard className="space-y-4 p-5">
                <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-slate-500" aria-hidden />
                    <h2 className="text-base font-bold text-slate-900">筛选题目</h2>
                </div>
                <FilterSelect label="分类" value={categoryId} onChange={onCategoryChange}>
                    <option value="">全部分类</option>
                    {categories.map((category) => (
                        <option key={category.category_id} value={category.category_id}>
                            {category.name}
                        </option>
                    ))}
                </FilterSelect>
                <FilterSelect label="状态" value={status} onChange={onStatusChange}>
                    <option value="">全部状态</option>
                    <option value="draft">{QUESTION_STATUS_LABELS.draft}</option>
                    <option value="published">{QUESTION_STATUS_LABELS.published}</option>
                    <option value="archived">{QUESTION_STATUS_LABELS.archived}</option>
                </FilterSelect>
                <FilterSelect label="难度" value={difficulty} onChange={onDifficultyChange}>
                    <option value="">全部难度</option>
                    <option value="easy">简单</option>
                    <option value="medium">中等</option>
                    <option value="hard">困难</option>
                </FilterSelect>
                <label className="space-y-2 text-sm font-medium text-slate-700">
                    <span>标签</span>
                    <div className="relative">
                        <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" aria-hidden />
                        <Input
                            className="pl-9"
                            value={tag}
                            onChange={(event) => onTagChange(event.target.value)}
                            placeholder="输入标签关键词"
                        />
                    </div>
                </label>
                <Button variant="outline" className="w-full" onClick={onRefresh}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    刷新
                </Button>
            </GlassCard>
        </aside>
    );
}

interface MetricTileProps {
    readonly label: string;
    readonly tone: "blue" | "emerald" | "slate";
    readonly value: number;
}

function MetricTile({ label, tone, value }: MetricTileProps) {
    const toneClass = {
        blue: "border-blue-100 bg-blue-50 text-blue-700",
        emerald: "border-emerald-100 bg-emerald-50 text-emerald-700",
        slate: "border-slate-100 bg-slate-50 text-slate-500",
    } as const;
    const valueClass = {
        blue: "text-blue-800",
        emerald: "text-emerald-800",
        slate: "text-slate-900",
    } as const;

    return (
        <div className={`rounded-2xl border p-3 ${toneClass[tone]}`}>
            <p className="text-xs">{label}</p>
            <p className={`mt-1 text-xl font-black ${valueClass[tone]}`}>{value}</p>
        </div>
    );
}

interface FilterSelectProps {
    readonly children: ReactNode;
    readonly label: string;
    readonly onChange: (value: string) => void;
    readonly value: string;
}

function FilterSelect({ children, label, onChange, value }: FilterSelectProps) {
    return (
        <label className="space-y-2 text-sm font-medium text-slate-700">
            <span>{label}</span>
            <select
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
            >
                {children}
            </select>
        </label>
    );
}
