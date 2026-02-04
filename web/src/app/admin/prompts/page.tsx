"use client";

/**
 * Admin Prompt Templates Management Page (B10)
 *
 * Features:
 * - List all prompt templates
 * - Create, edit, delete templates
 * - Preview rendered templates
 * - Manage scenario assignments
 */

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
    Plus,
    Search,
    Edit2,
    Trash2,
    Eye,
    Copy,
    CheckCircle,
    XCircle,
    AlertCircle,
    Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { GlassModal } from "@/components/ui/glass-modal";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api/client";
import { PromptTemplate, PromptType } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const PROMPT_TYPE_LABELS: Record<PromptType, string> = {
    summary: "总结",
    system: "系统",
    system_prompt: "系统提示词",
    extraction: "提取",
    scoring: "评分",
    stage: "阶段",
    fuzzy_detection: "模糊检测",
    interruption: "打断检测",
    tracking: "跟踪",
    welcome: "欢迎词",
    evaluation: "实时评价",
    report: "综合报告",
};

const PROMPT_TYPE_COLORS: Record<PromptType, string> = {
    summary: "bg-blue-100 text-blue-800",
    system: "bg-purple-100 text-purple-800",
    system_prompt: "bg-purple-100 text-purple-800",
    extraction: "bg-green-100 text-green-800",
    scoring: "bg-yellow-100 text-yellow-800",
    stage: "bg-orange-100 text-orange-800",
    fuzzy_detection: "bg-red-100 text-red-800",
    interruption: "bg-pink-100 text-pink-800",
    tracking: "bg-cyan-100 text-cyan-800",
    welcome: "bg-indigo-100 text-indigo-800",
    evaluation: "bg-teal-100 text-teal-800",
    report: "bg-gray-100 text-gray-800",
};

export default function AdminPromptsPage() {
    const router = useRouter();
    const [templates, setTemplates] = useState<PromptTemplate[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [typeFilter, setTypeFilter] = useState<PromptType | "all">("all");
    const [showInactive, setShowInactive] = useState(false);

    // Modal states
    const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null);
    const [showPreviewModal, setShowPreviewModal] = useState(false);
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [deleting, setDeleting] = useState(false);

    // Load templates
    const loadTemplates = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.admin.getPromptTemplates({
                is_active: showInactive ? undefined : true,
            });
            setTemplates(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "加载失败");
        } finally {
            setLoading(false);
        }
    }, [showInactive]);

    useEffect(() => {
        loadTemplates();
    }, [loadTemplates]);

    // Filter templates
    const filteredTemplates = templates.filter((template) => {
        const matchesSearch =
            template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            template.template.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesType = typeFilter === "all" || template.prompt_type === typeFilter;
        return matchesSearch && matchesType;
    });

    // Delete template
    const handleDelete = async () => {
        if (!selectedTemplate) return;

        setDeleting(true);
        try {
            await api.admin.deletePromptTemplate(selectedTemplate.id);
            await loadTemplates();
            setShowDeleteModal(false);
            setSelectedTemplate(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "删除失败");
        } finally {
            setDeleting(false);
        }
    };

    // Copy template content
    const handleCopy = async (content: string) => {
        try {
            await navigator.clipboard.writeText(content);
        } catch {
            // Ignore copy errors
        }
    };

    return (
        <div className="container mx-auto px-4 py-6 max-w-7xl">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-semibold text-zinc-900">提示词模板管理</h1>
                    <p className="text-zinc-500 mt-1">管理 AI 系统的提示词模板和场景分配</p>
                </div>
                <Button
                    onClick={() => router.push("/admin/prompts/new")}
                    className="bg-zinc-900 hover:bg-zinc-800"
                >
                    <Plus className="w-4 h-4 mr-2" />
                    新建模板
                </Button>
            </div>

            {/* Filters */}
            <GlassCard className="p-4 mb-6">
                <div className="flex flex-col md:flex-row gap-4">
                    <div className="flex-1 relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
                        <Input
                            placeholder="搜索模板名称或内容..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10"
                        />
                    </div>
                    <select
                        value={typeFilter}
                        onChange={(e) => setTypeFilter(e.target.value as PromptType | "all")}
                        className="px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                    >
                        <option value="all">所有类型</option>
                        {Object.entries(PROMPT_TYPE_LABELS).map(([type, label]) => (
                            <option key={type} value={type}>
                                {label}
                            </option>
                        ))}
                    </select>
                    <label className="flex items-center gap-2 text-sm text-zinc-600">
                        <input
                            type="checkbox"
                            checked={showInactive}
                            onChange={(e) => setShowInactive(e.target.checked)}
                            className="rounded border-zinc-300"
                        />
                        显示已禁用
                    </label>
                </div>
            </GlassCard>

            {/* Loading State */}
            {loading && (
                <div className="flex items-center justify-center py-12">
                    <StatusIndicator status="processing" size={20} />
                    <span className="ml-2 text-zinc-500">加载中...</span>
                </div>
            )}

            {/* Error State */}
            {error && !loading && (
                <div className="flex items-center justify-center py-12 text-red-500">
                    <AlertCircle className="w-5 h-5 mr-2" />
                    {error}
                </div>
            )}

            {/* Templates Grid */}
            {!loading && !error && (
                <div className="grid gap-4">
                    {filteredTemplates.map((template) => (
                        <GlassCard
                            key={template.id}
                            className={cn(
                                "p-4 transition-all hover:shadow-lg",
                                !template.is_active && "opacity-60"
                            )}
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-2">
                                        <h3 className="font-medium text-zinc-900 truncate">
                                            {template.name}
                                        </h3>
                                        <Badge
                                            className={cn(
                                                "text-xs",
                                                PROMPT_TYPE_COLORS[template.prompt_type]
                                            )}
                                        >
                                            {PROMPT_TYPE_LABELS[template.prompt_type]}
                                        </Badge>
                                        {template.is_default && (
                                            <Badge className="bg-amber-100 text-amber-800 text-xs">
                                                默认
                                            </Badge>
                                        )}
                                        {template.is_system && (
                                            <Badge className="bg-slate-100 text-slate-800 text-xs">
                                                系统
                                            </Badge>
                                        )}
                                        {!template.is_active && (
                                            <Badge className="bg-gray-100 text-gray-600 text-xs">
                                                已禁用
                                            </Badge>
                                        )}
                                    </div>

                                    <p className="text-sm text-zinc-500 mb-2">
                                        分类: {template.category}
                                    </p>

                                    <div className="bg-zinc-50 rounded-lg p-3 text-sm text-zinc-600 font-mono line-clamp-3">
                                        {template.template}
                                    </div>

                                    <div className="flex items-center gap-2 mt-3">
                                        <span className="text-xs text-zinc-400">变量:</span>
                                        {template.variables.length > 0 ? (
                                            template.variables.map((v) => (
                                                <Badge
                                                    key={v}
                                                    variant="secondary"
                                                    className="text-xs"
                                                >
                                                    {v}
                                                </Badge>
                                            ))
                                        ) : (
                                            <span className="text-xs text-zinc-400">无</span>
                                        )}
                                    </div>
                                </div>

                                <div className="flex items-center gap-1">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => {
                                            setSelectedTemplate(template);
                                            setShowPreviewModal(true);
                                        }}
                                        title="预览"
                                    >
                                        <Eye className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleCopy(template.template)}
                                        title="复制"
                                    >
                                        <Copy className="w-4 h-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() =>
                                            router.push(`/admin/prompts/${template.id}/edit`)
                                        }
                                        title="编辑"
                                    >
                                        <Edit2 className="w-4 h-4" />
                                    </Button>
                                    {!template.is_system && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-red-500 hover:text-red-700"
                                            onClick={() => {
                                                setSelectedTemplate(template);
                                                setShowDeleteModal(true);
                                            }}
                                            title="删除"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </GlassCard>
                    ))}

                    {filteredTemplates.length === 0 && (
                        <div className="text-center py-12">
                            <Sparkles className="w-12 h-12 text-zinc-300 mx-auto mb-4" />
                            <p className="text-zinc-500">没有找到匹配的提示词模板</p>
                        </div>
                    )}
                </div>
            )}

            {/* Preview Modal */}
            <GlassModal
                isOpen={showPreviewModal}
                onClose={() => setShowPreviewModal(false)}
                title="模板预览"
                size="lg"
            >
                {selectedTemplate && (
                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Badge className={PROMPT_TYPE_COLORS[selectedTemplate.prompt_type]}>
                                {PROMPT_TYPE_LABELS[selectedTemplate.prompt_type]}
                            </Badge>
                            <span className="font-medium">{selectedTemplate.name}</span>
                        </div>
                        <div className="bg-zinc-900 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-auto max-h-96">
                            <pre>{selectedTemplate.template}</pre>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-zinc-500">可用变量:</span>
                            {selectedTemplate.variables.map((v) => (
                                <Badge key={v} variant="secondary">
                                    {v}
                                </Badge>
                            ))}
                        </div>
                    </div>
                )}
            </GlassModal>

            {/* Delete Confirmation Modal */}
            <GlassModal
                isOpen={showDeleteModal}
                onClose={() => setShowDeleteModal(false)}
                title="确认删除"
                size="sm"
            >
                <div className="text-center">
                    <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
                    <p className="text-zinc-600 mb-6">
                        确定要删除提示词模板 "{selectedTemplate?.name}" 吗？
                        <br />
                        此操作不可恢复。
                    </p>
                    <div className="flex justify-center gap-3">
                        <Button
                            variant="outline"
                            onClick={() => setShowDeleteModal(false)}
                            disabled={deleting}
                        >
                            取消
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleDelete}
                            disabled={deleting}
                        >
                            {deleting ? "删除中..." : "确认删除"}
                        </Button>
                    </div>
                </div>
            </GlassModal>
        </div>
    );
}
