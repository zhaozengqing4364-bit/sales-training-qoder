import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { FileText, Database } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AdminKnowledgeBase } from "@/lib/api/types";

interface KnowledgeBaseCardProps {
    knowledgeBase: AdminKnowledgeBase;
    isSelected: boolean;
    onToggle: () => void;
    disabled?: boolean;
}

// 状态配置
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
    active: { label: "可用", className: "text-emerald-600 border-emerald-200 bg-emerald-50" },
    processing: { label: "处理中", className: "text-amber-600 border-amber-200 bg-amber-50" },
    inactive: { label: "停用", className: "text-slate-500 border-slate-200 bg-slate-50" },
};

// 分类配置
const CATEGORY_CONFIG: Record<string, { label: string; icon: React.ReactNode }> = {
    product: { label: "产品知识", icon: <Database className="w-4 h-4" /> },
    sales: { label: "销售话术", icon: <FileText className="w-4 h-4" /> },
    faq: { label: "常见问题", icon: <FileText className="w-4 h-4" /> },
    default: { label: "通用知识", icon: <FileText className="w-4 h-4" /> },
};

export function KnowledgeBaseCard({
    knowledgeBase,
    isSelected,
    onToggle,
    disabled = false,
}: KnowledgeBaseCardProps) {
    const statusConfig = STATUS_CONFIG[knowledgeBase.status] || STATUS_CONFIG.inactive;
    const categoryConfig = CATEGORY_CONFIG[knowledgeBase.category] || CATEGORY_CONFIG.default;

    return (
        <div
            onClick={!disabled ? onToggle : undefined}
            className={cn(
                "relative",
                disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
            )}
        >
            <GlassCard
                className={cn(
                    "p-4 transition-all border-2",
                    isSelected
                        ? "border-indigo-500 bg-indigo-50/30"
                        : "border-transparent hover:border-slate-200"
                )}
            >
                <div className="flex items-start gap-3">
                    {/* 复选框 */}
                    <div className="pt-0.5">
                        <Checkbox
                            checked={isSelected}
                            onCheckedChange={onToggle}
                            disabled={disabled}
                            onClick={(e) => e.stopPropagation()}
                        />
                    </div>

                    {/* 内容区域 */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-2">
                            <h3 className="font-semibold text-slate-900 truncate">
                                {knowledgeBase.name}
                            </h3>
                            <Badge
                                variant="secondary"
                                className={cn("text-xs border shrink-0", statusConfig.className)}
                            >
                                {statusConfig.label}
                            </Badge>
                        </div>

                        <p className="text-sm text-slate-500 line-clamp-2 mb-3">
                            {knowledgeBase.description}
                        </p>

                        {/* 元信息 */}
                        <div className="flex items-center gap-3 text-xs text-slate-400">
                            <span className="flex items-center gap-1">
                                {categoryConfig.icon}
                                {categoryConfig.label}
                            </span>
                            <span className="flex items-center gap-1">
                                <FileText className="w-3.5 h-3.5" />
                                {knowledgeBase.document_count} 文档
                            </span>
                            <span className="flex items-center gap-1">
                                <Database className="w-3.5 h-3.5" />
                                {knowledgeBase.total_chunks} 片段
                            </span>
                        </div>
                    </div>
                </div>
            </GlassCard>
        </div>
    );
}
