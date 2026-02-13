"use client";

import { useState } from "react";
import { KnowledgeBaseCard } from "./KnowledgeBaseCard";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { BookOpen, X, Library, AlertCircle } from "lucide-react";
import type { AdminKnowledgeBase } from "@/lib/api/types";

interface KnowledgeBaseSelectorProps {
    availableKBs: AdminKnowledgeBase[];
    selectedIds: string[];
    onChange: (ids: string[]) => void;
    isLoading?: boolean;
    error?: string | null;
    maxSelections?: number;
}

export function KnowledgeBaseSelector({
    availableKBs,
    selectedIds,
    onChange,
    isLoading = false,
    error = null,
    maxSelections = 5,
}: KnowledgeBaseSelectorProps) {
    const [showAll, setShowAll] = useState(false);

    const selectedKBs = availableKBs.filter((kb) => selectedIds.includes(kb.id));
    const unselectedKBs = availableKBs.filter((kb) => !selectedIds.includes(kb.id));

    const toggleKnowledgeBase = (kbId: string) => {
        if (selectedIds.includes(kbId)) {
            onChange(selectedIds.filter((id) => id !== kbId));
        } else {
            if (selectedIds.length >= maxSelections) {
                return;
            }
            onChange([...selectedIds, kbId]);
        }
    };

    const removeSelected = (kbId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        onChange(selectedIds.filter((id) => id !== kbId));
    };

    const displayLimit = 6;
    const hasMore = unselectedKBs.length > displayLimit;
    const displayedUnselected = showAll
        ? unselectedKBs
        : unselectedKBs.slice(0, displayLimit);

    if (isLoading) {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4">
                    <Skeleton className="h-5 w-5" />
                    <Skeleton className="h-6 w-32" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {[1, 2, 3, 4].map((i) => (
                        <Skeleton key={i} className="h-24" />
                    ))}
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <GlassCard className="p-6">
                <div className="flex items-center gap-3 text-amber-600">
                    <AlertCircle className="w-5 h-5" />
                    <span>{error}</span>
                </div>
            </GlassCard>
        );
    }

    if (availableKBs.length === 0) {
        return (
            <EmptyState
                title="暂无可用知识库"
                description="该智能体暂无可用的知识库，请联系管理员添加。"
                icon={<Library className="w-10 h-10 text-slate-300" />}
            />
        );
    }

    const isMaxReached = selectedIds.length >= maxSelections;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-slate-600" />
                    <h3 className="text-lg font-bold text-slate-800">选择挂载的知识库</h3>
                </div>
                <Badge variant="secondary" className="text-xs">
                    已选择 {selectedIds.length}/{maxSelections}
                </Badge>
            </div>

            <p className="text-sm text-slate-500">
                选择要挂载到当前智能体的知识库，AI将基于这些知识进行回答
            </p>

            {selectedKBs.length > 0 && (
                <div className="space-y-3">
                    <h4 className="text-sm font-medium text-slate-700">已选择</h4>
                    <div className="flex flex-wrap gap-2">
                        {selectedKBs.map((kb) => (
                            <Badge
                                key={kb.id}
                                variant="secondary"
                                className="pl-3 pr-2 py-1.5 bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100 cursor-pointer"
                                onClick={(e) => removeSelected(kb.id, e)}
                            >
                                <span className="mr-1">{kb.name}</span>
                                <X className="w-3 h-3" />
                            </Badge>
                        ))}
                    </div>
                </div>
            )}

            {isMaxReached && (
                <GlassCard className="p-3 bg-amber-50/50 border-amber-200">
                    <p className="text-sm text-amber-700">
                        已达到最大选择数量 ({maxSelections}个)，如需更换请先取消已选择的库
                    </p>
                </GlassCard>
            )}

            <div className="space-y-3">
                <h4 className="text-sm font-medium text-slate-700">可用知识库</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {displayedUnselected.map((kb) => (
                        <KnowledgeBaseCard
                            key={kb.id}
                            knowledgeBase={kb}
                            isSelected={false}
                            onToggle={() => toggleKnowledgeBase(kb.id)}
                            disabled={isMaxReached}
                        />
                    ))}
                </div>

                {hasMore && !showAll && (
                    <Button
                        variant="ghost"
                        onClick={() => setShowAll(true)}
                        className="w-full text-slate-500 hover:text-slate-700"
                    >
                        显示全部 {unselectedKBs.length} 个知识库
                    </Button>
                )}
            </div>
        </div>
    );
}
