"use client";

/**
 * Create New Prompt Template Page (B10)
 */

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Save, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { api } from "@/lib/api/client";
import { PromptType } from "@/lib/api/types";

const PROMPT_TYPE_LABELS: Record<PromptType, string> = {
    summary: "总结",
    system: "系统",
    system_prompt: "系统提示词",
    extraction: "提取",
    scoring: "评分",
    realtime_scoring: "实时评分",
    stage: "阶段",
    realtime_scoring: "实时评分",
    fuzzy_detection: "模糊检测",
    realtime_scoring: "实时评分",
    interruption: "打断检测",
    tracking: "跟踪",
    welcome: "欢迎词",
    evaluation: "实时评价",
    report: "综合报告",
  realtime_scoring: "实时评分",
};
const SALES_ALLOWED_PROMPT_TYPES: PromptType[] = ["evaluation", "report", "stage", "scoring", "realtime_scoring"];

export default function NewPromptTemplatePage() {
    const router = useRouter();
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [name, setName] = useState("");
    const [promptType, setPromptType] = useState<PromptType>("summary");
    const [category, setCategory] = useState("common");
    const [template, setTemplate] = useState("");
    const [isDefault, setIsDefault] = useState(false);
    const normalizedCategory = category.trim().toLowerCase();

    const selectablePromptTypes = useMemo(() => {
        const entries = Object.entries(PROMPT_TYPE_LABELS) as [PromptType, string][];
        if (normalizedCategory !== "sales") {
            return entries;
        }
        return entries.filter(([type]) => SALES_ALLOWED_PROMPT_TYPES.includes(type));
    }, [normalizedCategory]);

    const effectivePromptType = (
        selectablePromptTypes.some(([type]) => type === promptType)
            ? promptType
            : (selectablePromptTypes[0]?.[0] ?? promptType)
    );

    // Extract variables from template
    const extractVariables = (tpl: string): string[] => {
        const matches = tpl.match(/\{\{\s*(\w+)\s*\}\}/g);
        if (!matches) return [];
        return [...new Set(matches.map((m) => m.replace(/\{\{\s*|\s*\}\}/g, "")))].filter(
            (v) => v && !v.includes(".") // Filter out attribute access
        );
    };

    const extractedVars = extractVariables(template);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);

        try {
            await api.admin.createPromptTemplate({
                name,
                prompt_type: effectivePromptType,
                category,
                template,
                variables: extractedVars,
                is_default: isDefault,
            });
            router.push("/admin/prompts");
        } catch (err) {
            setError(err instanceof Error ? err.message : "创建失败");
            setSaving(false);
        }
    };

    return (
        <div className="container mx-auto px-4 py-6 max-w-4xl">
            {/* Header */}
            <div className="flex items-center gap-4 mb-6">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push("/admin/prompts")}
                >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    返回
                </Button>
                <h1 className="text-2xl font-semibold text-zinc-900">新建提示词模板</h1>
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2 text-red-500 mb-4 p-3 bg-red-50 rounded-lg">
                    <AlertCircle className="w-5 h-5" />
                    {error}
                </div>
            )}

            {/* Form */}
            <GlassCard className="p-6">
                <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Name */}
                        <div>
                            <label className="block text-sm font-medium text-zinc-700 mb-2">
                                模板名称 <span className="text-red-500">*</span>
                            </label>
                            <Input
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="例如：销售对话总结"
                                required
                            />
                        </div>

                        {/* Type */}
                        <div>
                            <label className="block text-sm font-medium text-zinc-700 mb-2">
                                提示词类型 <span className="text-red-500">*</span>
                            </label>
                            <select
                                value={promptType}
                                onChange={(e) => setPromptType(e.target.value as PromptType)}
                                className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                                required
                            >
                                {selectablePromptTypes.map(([type, label]) => (
                                    <option key={type} value={type}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Category */}
                        <div>
                            <label className="block text-sm font-medium text-zinc-700 mb-2">
                                分类
                            </label>
                            <Input
                                value={category}
                                onChange={(e) => {
                                    const nextCategory = e.target.value;
                                    const nextNormalized = nextCategory.trim().toLowerCase();
                                    if (
                                        nextNormalized === "sales" &&
                                        !SALES_ALLOWED_PROMPT_TYPES.includes(promptType)
                                    ) {
                                        setPromptType(SALES_ALLOWED_PROMPT_TYPES[0]);
                                    }
                                    setCategory(nextCategory);
                                }}
                                placeholder="例如：sales, presentation, common"
                            />
                            {normalizedCategory === "sales" && (
                                <p className="mt-1 text-xs text-amber-600">
                                    销售场景仅允许评估/报告相关模板类型。
                                </p>
                            )}
                        </div>

                        {/* Is Default */}
                        <div className="flex items-center">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={isDefault}
                                    onChange={(e) => setIsDefault(e.target.checked)}
                                    className="rounded border-zinc-300"
                                />
                                <span className="text-sm text-zinc-700">设为默认模板</span>
                            </label>
                        </div>
                    </div>

                    {/* Template */}
                    <div>
                        <label className="block text-sm font-medium text-zinc-700 mb-2">
                            模板内容 <span className="text-red-500">*</span>
                        </label>
                        <textarea
                            value={template}
                            onChange={(e) => setTemplate(e.target.value)}
                            placeholder="输入 Jinja2 模板，使用 {{ variable }} 语法插入变量"
                            className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900 min-h-[300px]"
                            required
                        />
                        <p className="text-xs text-zinc-500 mt-1">
                            支持 Jinja2 模板语法，使用 {"{{"} variable {"}}"} 插入变量
                        </p>
                    </div>

                    {/* Variables Preview */}
                    {extractedVars.length > 0 && (
                        <div className="bg-blue-50 rounded-lg p-4">
                            <h4 className="text-sm font-medium text-blue-900 mb-2">
                                自动提取的变量
                            </h4>
                            <div className="flex flex-wrap gap-2">
                                {extractedVars.map((v) => (
                                    <span
                                        key={v}
                                        className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm"
                                    >
                                        {v}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex justify-end gap-3 pt-4 border-t">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => router.push("/admin/prompts")}
                            disabled={saving}
                        >
                            取消
                        </Button>
                        <Button
                            type="submit"
                            className="bg-zinc-900 hover:bg-zinc-800"
                            disabled={saving || !name || !template}
                        >
                            {saving ? (
                                <>
                                    <StatusIndicator status="loading"  className="mr-2" />
                                    保存中...
                                </>
                            ) : (
                                <>
                                    <Save className="w-4 h-4 mr-2" />
                                    保存
                                </>
                            )}
                        </Button>
                    </div>
                </form>
            </GlassCard>
        </div>
    );
}
