"use client";

/**
 * Edit Prompt Template Page (B10)
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save, AlertCircle, Play } from "lucide-react";
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
    realtime_scoring: "实时评分",
    stage: "阶段",
    fuzzy_detection: "模糊检测",
    realtime_scoring: "实时评分",
    interruption: "打断检测",
    tracking: "跟踪",
    welcome: "欢迎词",
    evaluation: "实时评价",
    report: "综合报告",
};
const SALES_ALLOWED_PROMPT_TYPES: PromptType[] = ["evaluation", "report", "stage", "scoring", "realtime_scoring"];

export default function EditPromptTemplatePage() {
    const params = useParams();
    const router = useRouter();
    const rawTemplateId = params?.id;
    const templateId = Array.isArray(rawTemplateId) ? rawTemplateId[0] : rawTemplateId;
    const isValidTemplateId =
        typeof templateId === "string"
        && templateId.trim().length > 0
        && templateId !== "undefined";
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [originalTemplate, setOriginalTemplate] = useState<PromptTemplate | null>(null);

    // Form state
    const [name, setName] = useState("");
    const [promptType, setPromptType] = useState<PromptType>("summary");
    const [category, setCategory] = useState("common");
    const [template, setTemplate] = useState("");
    const [isActive, setIsActive] = useState(true);
    const [isDefault, setIsDefault] = useState(false);

    // Test render state
    const [testVariables, setTestVariables] = useState<string>("{}");
    const [testResult, setTestResult] = useState<string | null>(null);
    const [testing, setTesting] = useState(false);
    const [showTestModal, setShowTestModal] = useState(false);
    const normalizedCategory = category.trim().toLowerCase();

    const selectablePromptTypes = useMemo(() => {
        const entries = Object.entries(PROMPT_TYPE_LABELS) as [PromptType, string][];
        if (normalizedCategory !== "sales") {
            return entries;
        }
        return entries.filter(([type]) => SALES_ALLOWED_PROMPT_TYPES.includes(type));
    }, [normalizedCategory]);

    // Load template
    const loadTemplate = useCallback(async () => {
        if (!isValidTemplateId || !templateId) {
            setError("模板ID无效，请返回列表后重试。");
            setLoading(false);
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const data = await api.admin.getPromptTemplate(templateId);
            setOriginalTemplate(data);
            setName(data.name);
            setPromptType(data.prompt_type);
            setCategory(data.category);
            setTemplate(data.template);
            setIsActive(data.is_active);
            setIsDefault(data.is_default);

            // Generate sample variables
            const sampleVars: Record<string, string> = {};
            data.variables.forEach((v) => {
                sampleVars[v] = `示例${v}`;
            });
            setTestVariables(JSON.stringify(sampleVars, null, 2));
        } catch (err) {
            setError(err instanceof Error ? err.message : "加载失败");
        } finally {
            setLoading(false);
        }
    }, [isValidTemplateId, templateId]);

    useEffect(() => {
        loadTemplate();
    }, [loadTemplate]);

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
            (v) => v && !v.includes(".")
        );
    };

    const extractedVars = extractVariables(template);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);

        try {
            if (!isValidTemplateId || !templateId) {
                throw new Error("模板ID无效，无法保存");
            }
            await api.admin.updatePromptTemplate(templateId, {
                name,
                prompt_type: effectivePromptType,
                category,
                template,
                variables: extractedVars,
                is_active: isActive,
                is_default: isDefault,
            });
            router.push("/admin/prompts");
        } catch (err) {
            setError(err instanceof Error ? err.message : "保存失败");
            setSaving(false);
        }
    };

    const handleTestRender = async () => {
        setTesting(true);
        setTestResult(null);
        try {
            if (!isValidTemplateId || !templateId) {
                throw new Error("模板ID无效，无法测试渲染");
            }
            const variables = JSON.parse(testVariables);
            const result = await api.admin.renderPromptTemplate(templateId, variables);
            setTestResult(result.rendered);
        } catch (err) {
            setTestResult(`错误: ${err instanceof Error ? err.message : "渲染失败"}`);
        } finally {
            setTesting(false);
        }
    };

    if (loading) {
        return (
            <div className="container mx-auto px-4 py-12 max-w-4xl text-center">
                <StatusIndicator status="loading"  />
                <p className="mt-4 text-zinc-500">加载中...</p>
            </div>
        );
    }

    if (error && !originalTemplate) {
        return (
            <div className="container mx-auto px-4 py-12 max-w-4xl">
                <div className="flex items-center gap-2 text-red-500 justify-center">
                    <AlertCircle className="w-6 h-6" />
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div className="container mx-auto px-4 py-6 max-w-4xl">
            {/* Header */}
            <div className="flex items-center gap-4 mb-6">
                <Button variant="ghost" size="sm" onClick={() => router.push("/admin/prompts")}>
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    返回
                </Button>
                <h1 className="text-2xl font-semibold text-zinc-900">编辑提示词模板</h1>
                {originalTemplate?.is_system && (
                    <Badge className="bg-slate-100 text-slate-800">系统模板</Badge>
                )}
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
                            <Input value={name} onChange={(e) => setName(e.target.value)} required />
                        </div>

                        {/* Type */}
                        <div>
                            <label className="block text-sm font-medium text-zinc-700 mb-2">
                                提示词类型 <span className="text-red-500">*</span>
                            </label>
                            <select
                                value={effectivePromptType}
                                onChange={(e) => setPromptType(e.target.value as PromptType)}
                                className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-zinc-900"
                                required
                                disabled={originalTemplate?.is_system}
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
                            <label className="block text-sm font-medium text-zinc-700 mb-2">分类</label>
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
                            />
                            {normalizedCategory === "sales" && (
                                <p className="mt-1 text-xs text-amber-600">
                                    销售场景仅允许评估/报告相关模板类型。
                                </p>
                            )}
                        </div>

                        {/* Status */}
                        <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={isActive}
                                    onChange={(e) => setIsActive(e.target.checked)}
                                    className="rounded border-zinc-300"
                                    disabled={originalTemplate?.is_system}
                                />
                                <span className="text-sm text-zinc-700">启用</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={isDefault}
                                    onChange={(e) => setIsDefault(e.target.checked)}
                                    className="rounded border-zinc-300"
                                />
                                <span className="text-sm text-zinc-700">设为默认</span>
                            </label>
                        </div>
                    </div>

                    {/* Template */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="block text-sm font-medium text-zinc-700">
                                模板内容 <span className="text-red-500">*</span>
                            </label>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => setShowTestModal(true)}
                            >
                                <Play className="w-4 h-4 mr-2" />
                                测试渲染
                            </Button>
                        </div>
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
                            <h4 className="text-sm font-medium text-blue-900 mb-2">自动提取的变量</h4>
                            <div className="flex flex-wrap gap-2">
                                {extractedVars.map((v) => (
                                    <span
                                        key={v}
                                        className={cn(
                                            "px-2 py-1 rounded text-sm",
                                            originalTemplate?.variables.includes(v)
                                                ? "bg-blue-100 text-blue-800"
                                                : "bg-green-100 text-green-800"
                                        )}
                                    >
                                        {v}
                                        {!originalTemplate?.variables.includes(v) && " (新)"}
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

            {/* Test Render Modal */}
            <GlassModal isOpen={showTestModal} onClose={() => setShowTestModal(false)} title="测试模板渲染" size="lg">
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-zinc-700 mb-2">变量 (JSON)</label>
                        <textarea
                            value={testVariables}
                            onChange={(e) => setTestVariables(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-zinc-900 min-h-[150px]"
                            placeholder='{"variable": "value"}'
                        />
                    </div>
                    <Button onClick={handleTestRender} disabled={testing} className="w-full">
                        {testing ? (
                            <>
                                <StatusIndicator status="loading"  className="mr-2" />
                                渲染中...
                            </>
                        ) : (
                            <>
                                <Play className="w-4 h-4 mr-2" />
                                渲染
                            </>
                        )}
                    </Button>
                    {testResult !== null && (
                        <div className="bg-zinc-900 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-auto max-h-96">
                            <pre>{testResult}</pre>
                        </div>
                    )}
                </div>
            </GlassModal>
        </div>
    );
}
