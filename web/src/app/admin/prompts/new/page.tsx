"use client";

/**
 * Create New Prompt Template Page (B10)
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Save, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { GlassCard } from "@/components/ui/glass-card";
import { StatusIndicator } from "@/components/ui/status-indicator";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { PromptBusinessPurpose, PromptTemplateOptions, PromptType } from "@/lib/api/types";
import {
    formatBusinessPurpose,
    formatCategoryLabel,
    formatPromptType,
    isPromptBusinessPurpose,
    PROMPT_BUSINESS_PURPOSE,
    PROMPT_BUSINESS_PURPOSE_OPTIONS,
    PROMPT_TYPE_LABELS,
} from "@/components/admin/prompts/prompt-labels";

const PROMPT_CATEGORY_OPTIONS = [
    { value: "common", label: "通用" },
    { value: "sales", label: "销售训练" },
    { value: "sales_bot", label: "销售实时对练" },
    { value: "business_etiquette", label: "商务礼仪" },
    { value: "sales_trainer_ai_coach", label: "新人训练 AI 教练" },
    { value: "presentation", label: "PPT 演练" },
    { value: "system", label: "系统报告" },
] as const;

const BUSINESS_ETIQUETTE_QUESTION_TEMPLATE_PRESET = `你是商务礼仪新人训练题目草稿生成器。请严格基于章节原文生成题目，不要编造教材外知识。

训练包：{{ training_pack_key }}
训练包版本：{{ training_pack_revision_no }}
文章标题：{{ book_title }}
当前章节：第 {{ chapter_order }} 章 {{ chapter_title }}
章节 ID：{{ chapter_id }}

【章节原文】
{{ chapter_content }}

【能力点】
{{ capabilities_json }}

【能力点 key】
{{ capability_keys_json }}

【本次要求】
- 生成数量：{{ draft_count }}
- 允许题型：{{ question_types_json }}
- 语言：{{ language }}
- 审核规则：{{ review_policy }}
- 操作原因：{{ reason }}

【输出要求】
只输出合法 JSON，不要输出 Markdown，不要输出解释性正文。JSON 必须满足以下 schema：
{{ output_schema }}

每道题必须：
1. 明确引用章节原文或 source_excerpt。
2. 单选题必须有 options 和 correct_answer。
3. 多选题必须有 options 和 correct_answers。
4. 简答题必须有 reference_answer。
5. capability_keys 只能使用上方能力点 key。`;

function presetTemplateForBusinessPurpose(
    purpose: string | null,
): string {
    if (purpose === PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION) {
        return BUSINESS_ETIQUETTE_QUESTION_TEMPLATE_PRESET;
    }
    return "";
}

export default function NewPromptTemplatePage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const requestedPromptType = searchParams.get("prompt_type");
    const requestedBusinessPurpose = searchParams.get("business_purpose");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [name, setName] = useState(() => searchParams.get("name") || "");
    const [promptType, setPromptType] = useState<PromptType>(() => (
        requestedPromptType && requestedPromptType in PROMPT_TYPE_LABELS
            ? requestedPromptType as PromptType
            : "summary"
    ));
    const [businessPurpose, setBusinessPurpose] = useState<PromptBusinessPurpose | "">(() => (
        isPromptBusinessPurpose(requestedBusinessPurpose) ? requestedBusinessPurpose : ""
    ));
    const [category, setCategory] = useState(() => searchParams.get("category") || "common");
    const [template, setTemplate] = useState(() => (
        presetTemplateForBusinessPurpose(requestedBusinessPurpose)
    ));
    const [isDefault, setIsDefault] = useState(false);
    const [promptOptions, setPromptOptions] = useState<PromptTemplateOptions | null>(null);
    const normalizedCategory = category.trim().toLowerCase();
    const salesAllowedPromptTypes = useMemo(
        () => new Set((promptOptions?.sales_allowed_prompt_types || []) as PromptType[]),
        [promptOptions],
    );
    const businessPurposeOptions = useMemo(
        () => (
            promptOptions?.allowed_business_purposes?.length
                ? promptOptions.allowed_business_purposes
                : PROMPT_BUSINESS_PURPOSE_OPTIONS
        ),
        [promptOptions],
    );

    useEffect(() => {
        void api.admin.getPromptTemplateOptions()
            .then(setPromptOptions)
            .catch(() => setPromptOptions(null));
    }, []);

    const selectablePromptTypes = useMemo(() => {
        const entries = Object.entries(PROMPT_TYPE_LABELS) as [PromptType, string][];
        if (normalizedCategory !== "sales" || salesAllowedPromptTypes.size === 0) {
            return entries;
        }
        return entries.filter(([type]) => salesAllowedPromptTypes.has(type));
    }, [normalizedCategory, salesAllowedPromptTypes]);

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
                business_purpose: businessPurpose || null,
                category,
                template,
                variables: extractedVars,
                is_default: isDefault,
            });
            router.push("/admin/prompts");
        } catch (err) {
            setError(getApiErrorMessage(err));
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
                                        {formatPromptType(type, label)}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Category */}
                        <div>
                            <label className="block text-sm font-medium text-zinc-700 mb-2">
                                分类
                            </label>
                            <input
                                list="prompt-category-options"
                                value={category}
                                onChange={(e) => {
                                    const nextCategory = e.target.value;
                                    const nextNormalized = nextCategory.trim().toLowerCase();
                                    if (
                                        nextNormalized === "sales" &&
                                        salesAllowedPromptTypes.size > 0 &&
                                        !salesAllowedPromptTypes.has(promptType)
                                    ) {
                                        setPromptType([...salesAllowedPromptTypes][0]);
                                    }
                                    setCategory(nextCategory);
                                }}
                                className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                                placeholder="选择或输入分类"
                            />
                            <datalist id="prompt-category-options">
                                {PROMPT_CATEGORY_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </datalist>
                            <p className="mt-1 text-xs text-zinc-500">{formatCategoryLabel(category)}</p>
                            {normalizedCategory === "sales" && (
                                <p className="mt-1 text-xs text-amber-600">
                                    销售场景仅允许评估/报告相关模板类型。
                                </p>
                            )}
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-zinc-700 mb-2">
                                业务用途
                            </label>
                            <select
                                value={businessPurpose}
                                onChange={(e) => setBusinessPurpose(e.target.value as PromptBusinessPurpose | "")}
                                className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                            >
                                <option value="">不指定业务用途</option>
                                {businessPurposeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                            <p className="mt-1 text-xs text-zinc-500">
                                {formatBusinessPurpose(businessPurpose || null)}
                            </p>
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
