"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ExternalLink, Loader2, Send, Sparkles, X } from "lucide-react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type {
    AdminModelConfigListItem,
    BusinessEtiquetteQuestionDraftType,
    PromptTemplate,
} from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
    formatBusinessPurpose,
    formatCategoryLabel,
    formatPromptType,
    formatTemplateName,
    PROMPT_BUSINESS_PURPOSE,
} from "@/components/admin/prompts/prompt-labels";
import { debug } from "@/lib/debug";

interface BusinessEtiquetteQuestionDraftPanelProps {
    chapterOrder: number;
}

const QUESTION_TYPES: readonly BusinessEtiquetteQuestionDraftType[] = [
    "single_choice",
    "multiple_choice",
    "short_answer",
];

const TYPE_LABELS: Record<BusinessEtiquetteQuestionDraftType, string> = {
    single_choice: "单选题",
    multiple_choice: "多选题",
    short_answer: "简答题",
};

const PROMPT_TEMPLATE_CATEGORIES = [
    "business_etiquette",
    "sales_trainer_ai_coach",
    "sales_trainer",
] as const;
const QUESTION_TEMPLATE_KEYWORDS = ["题目生成", "题目草稿", "试题生成", "question"] as const;
const QUESTION_TEMPLATE_EXCLUDE_KEYWORDS = ["对话教练", "互动卡片", "chatbot"] as const;
const DEFAULT_REASON = "从学习内容详情页生成商务礼仪题目草稿";
const QUESTION_PROMPT_TEMPLATE_NAME = "商务礼仪题目草稿生成 v1";
const AI_COACH_SYSTEM_PROMPT_TEMPLATE_NAME = "新人训练路径商务技巧 AI 对话教练生成 v1";
const questionPromptTemplateCreateHref = (
    `/admin/prompts/new?category=business_etiquette&prompt_type=scoring&name=${
        encodeURIComponent(QUESTION_PROMPT_TEMPLATE_NAME)
    }&business_purpose=${PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION}`
);
const aiCoachSystemPromptTemplateCreateHref = (
    `/admin/prompts/new?category=sales_trainer_ai_coach&prompt_type=stage&name=${
        encodeURIComponent(AI_COACH_SYSTEM_PROMPT_TEMPLATE_NAME)
    }&business_purpose=${PROMPT_BUSINESS_PURPOSE.AI_COACH_CONVERSATION}`
);

function parseCsv(value: string): string[] {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function parseJsonObject(value: string, message: string): Record<string, unknown> {
    if (!value.trim()) return {};
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error(message);
    }
    return parsed as Record<string, unknown>;
}

function mergeTemplates(...groups: PromptTemplate[][]): PromptTemplate[] {
    const byId = new Map<string, PromptTemplate>();
    groups.flat().forEach((template) => {
        if (template.is_active && !byId.has(template.id)) {
            byId.set(template.id, template);
        }
    });
    return Array.from(byId.values());
}

function templateLabel(template: PromptTemplate): string {
    const tags = [
        formatCategoryLabel(template.category),
        formatPromptType(template.prompt_type, template.display_type),
        formatBusinessPurpose(template.business_purpose, template.display_business_purpose),
        template.is_default ? "默认" : null,
    ].filter(Boolean);
    return `${formatTemplateName(template.name, template.display_name)}（${tags.join(" · ")}）`;
}

function isBusinessEtiquetteQuestionTemplate(template: PromptTemplate): boolean {
    if (template.business_purpose) {
        return template.business_purpose === PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION;
    }
    const text = [
        template.name,
        template.display_name,
        template.business_purpose,
        template.display_business_purpose,
        template.category,
        template.prompt_type,
        template.display_type,
        template.display_category,
        template.template,
    ].filter(Boolean).join(" ").toLowerCase();
    const hasQuestionIntent = QUESTION_TEMPLATE_KEYWORDS.some((keyword) => (
        text.includes(keyword.toLowerCase())
    ));
    const isCoachConversationTemplate = QUESTION_TEMPLATE_EXCLUDE_KEYWORDS.some((keyword) => (
        text.includes(keyword.toLowerCase())
    ));
    return template.is_active && hasQuestionIntent && !isCoachConversationTemplate;
}

export function BusinessEtiquetteQuestionDraftPanel({
    chapterOrder,
}: BusinessEtiquetteQuestionDraftPanelProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isLoadingReferences, setIsLoadingReferences] = useState(false);
    const [referencesLoaded, setReferencesLoaded] = useState(false);
    const [referenceError, setReferenceError] = useState<string | null>(null);
    const [referenceWarning, setReferenceWarning] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [generatedCount, setGeneratedCount] = useState<number | null>(null);
    const [generatedBatchId, setGeneratedBatchId] = useState<string | null>(null);
    const [promptTemplateId, setPromptTemplateId] = useState("");
    const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
    const [llmConfigs, setLlmConfigs] = useState<AdminModelConfigListItem[]>([]);
    const [selectedModelConfigId, setSelectedModelConfigId] = useState("");
    const [draftCount, setDraftCount] = useState("3");
    const [questionTypes, setQuestionTypes] = useState<BusinessEtiquetteQuestionDraftType[]>([
        "single_choice",
        "multiple_choice",
        "short_answer",
    ]);
    const [capabilityKeysText, setCapabilityKeysText] = useState("");
    const [advancedModelConfigJson, setAdvancedModelConfigJson] = useState("");
    const [reason, setReason] = useState(DEFAULT_REASON);

    useEffect(() => {
        if (!isOpen || referencesLoaded) return;
        let cancelled = false;
        async function loadReferences() {
            setIsLoadingReferences(true);
            setReferenceError(null);
            setReferenceWarning(null);
            try {
                const [purposeTemplates, modelConfigs] = await Promise.all([
                    api.admin.getPromptTemplates({
                        business_purpose: PROMPT_BUSINESS_PURPOSE.BUSINESS_ETIQUETTE_QUESTION,
                        is_active: true,
                    }),
                    api.admin.getModelConfigs(),
                ]);
                if (cancelled) return;
                let templateGroups: PromptTemplate[][] = [purposeTemplates];
                if (!purposeTemplates.length) {
                    templateGroups = await Promise.all(PROMPT_TEMPLATE_CATEGORIES.map((category) => (
                        api.admin.getPromptTemplates({ category, is_active: true })
                    )));
                    if (cancelled) return;
                }
                const availableTemplates = mergeTemplates(...templateGroups)
                    .filter(isBusinessEtiquetteQuestionTemplate)
                    .filter((template) => (
                        !template.template.includes("ai_coach_interaction_v1")
                        && !template.template.includes("allowed_interaction_types")
                    ));
                const availableLlmConfigs = (modelConfigs.llm || []).filter((item) => item.is_active);
                setPromptTemplates(availableTemplates);
                setLlmConfigs(availableLlmConfigs);
                setReferencesLoaded(true);
                setPromptTemplateId((current) => (
                    current
                    || availableTemplates.find((item) => item.is_default)?.id
                    || availableTemplates[0]?.id
                    || ""
                ));
                setSelectedModelConfigId((current) => (
                    current || availableLlmConfigs.find((item) => item.is_default)?.id || ""
                ));
                if (!availableTemplates.length) {
                    setReferenceWarning(
                        "未找到商务礼仪题目生成专用模板。请到提示词管理新建模板：分类选择「新人训练 AI 教练」或「商务礼仪」，业务用途选择「商务礼仪题目生成」，保存后回到这里生成。",
                    );
                }
            } catch (err) {
                if (cancelled) return;
                debug.error("Failed to load business etiquette generation references:", err);
                setReferenceError(getApiErrorMessage(err));
            } finally {
                if (!cancelled) setIsLoadingReferences(false);
            }
        }
        void loadReferences();
        return () => {
            cancelled = true;
        };
    }, [isOpen, referencesLoaded]);

    function toggleQuestionType(type: BusinessEtiquetteQuestionDraftType) {
        setQuestionTypes((current) => (
            current.includes(type)
                ? current.filter((item) => item !== type)
                : [...current, type]
        ));
    }

    function requestGeneration() {
        setError(null);
        if (!promptTemplateId.trim()) {
            setError("请先选择商务礼仪题目生成 Prompt 模板。");
            return;
        }
        if (!questionTypes.length) {
            setError("至少选择一种题型。");
            return;
        }
        const count = Number(draftCount);
        if (!Number.isInteger(count) || count < 1 || count > 10) {
            setError("生成数量必须是 1 到 10 的整数。");
            return;
        }
        try {
            parseJsonObject(advancedModelConfigJson, "高级模型参数必须是 JSON 对象。");
        } catch (err) {
            setError(err instanceof Error ? err.message : "高级模型参数 JSON 无效。");
            return;
        }
        setConfirmOpen(true);
    }

    function buildModelConfigPayload(): Record<string, unknown> {
        const advancedConfig = parseJsonObject(
            advancedModelConfigJson,
            "高级模型参数必须是 JSON 对象。",
        );
        const safeAdvancedConfig = { ...advancedConfig };
        delete safeAdvancedConfig.model_config_id;
        if (!selectedModelConfigId) return safeAdvancedConfig;
        return {
            ...safeAdvancedConfig,
            model_config_id: selectedModelConfigId,
        };
    }

    async function generateDrafts() {
        setConfirmOpen(false);
        setIsGenerating(true);
        setError(null);
        setGeneratedCount(null);
        setGeneratedBatchId(null);
        try {
            const result = await api.admin.salesTrainer.generateBusinessEtiquetteQuestionDrafts({
                chapter_order: chapterOrder,
                prompt_template_id: promptTemplateId.trim(),
                question_types: questionTypes,
                draft_count: Number(draftCount),
                capability_keys: parseCsv(capabilityKeysText),
                model_config: buildModelConfigPayload(),
                reason: reason.trim() || DEFAULT_REASON,
            });
            setGeneratedCount(result.total);
            setGeneratedBatchId(result.batch_id);
        } catch (err) {
            debug.error("Business etiquette draft generation failed:", err);
            setError(getApiErrorMessage(err));
        } finally {
            setIsGenerating(false);
        }
    }

    if (!isOpen) {
        return (
            <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => setIsOpen(true)}
            >
                <Sparkles className="mr-1 h-3.5 w-3.5" />
                生成商务礼仪题目草稿
            </Button>
        );
    }

    return (
        <div className="space-y-4">
            <ConfirmDialog
                open={confirmOpen}
                onOpenChange={setConfirmOpen}
                title="确认生成题目草稿"
                description={`将基于第 ${chapterOrder} 章生成 ${draftCount} 道商务礼仪题目草稿，只写入草稿箱，不会直接发布或绑定给学员。该操作会调用 AI 模型并产生耗时/成本。`}
                confirmText="确认生成"
                cancelText="再检查一下"
                variant="warning"
                onConfirm={() => void generateDrafts()}
                isLoading={isGenerating}
            />

            <div className="flex items-start justify-between gap-3">
                <div>
                    <h3 className="text-sm font-bold text-slate-900">商务礼仪题目草稿</h3>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                        当前章节只生成待审核草稿；审核通过后才会转正式题库草稿。
                    </p>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs">
                        <Link
                            href="/admin/prompts"
                            className="inline-flex items-center gap-1 font-semibold text-blue-700 underline underline-offset-2"
                        >
                            管理 Prompt 模板
                            <ExternalLink className="h-3 w-3" />
                        </Link>
                        <Link
                            href={questionPromptTemplateCreateHref}
                            className="inline-flex items-center gap-1 font-semibold text-blue-700 underline underline-offset-2"
                        >
                            新建题目生成模板
                            <ExternalLink className="h-3 w-3" />
                        </Link>
                        <Link
                            href={aiCoachSystemPromptTemplateCreateHref}
                            className="inline-flex items-center gap-1 font-semibold text-blue-700 underline underline-offset-2"
                        >
                            新建 AI 教练系统提示词
                            <ExternalLink className="h-3 w-3" />
                        </Link>
                        <Link
                            href="/admin/settings"
                            className="inline-flex items-center gap-1 font-semibold text-blue-700 underline underline-offset-2"
                        >
                            管理模型配置
                            <ExternalLink className="h-3 w-3" />
                        </Link>
                    </div>
                </div>
                <button
                    type="button"
                    onClick={() => setIsOpen(false)}
                    className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                    aria-label="关闭商务礼仪题目草稿面板"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>

            {isLoadingReferences ? (
                <div className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在加载模板和模型配置
                </div>
            ) : null}

            {referenceWarning ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-800">
                    {referenceWarning}
                </div>
            ) : null}

            {referenceError ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    模板或模型配置加载失败：{referenceError}
                </div>
            ) : null}

            {error ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            ) : null}

            {generatedCount !== null ? (
                <div className="space-y-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    <p className="font-semibold">
                        已生成 {generatedCount} 道待审核草稿{generatedBatchId ? `，批次 ${generatedBatchId.slice(0, 8)}` : ""}。
                    </p>
                    <p>
                        {"下一步：去草稿箱审核 -> 转正式题库草稿 -> 发布题目/组卷 -> 发布路径配置。"}
                    </p>
                    <Link
                        href={generatedBatchId ? `/admin/sales-trainer/questions/drafts?batch_id=${generatedBatchId}` : "/admin/sales-trainer/questions/drafts"}
                        className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-900 underline underline-offset-2"
                    >
                        去题目草稿箱
                        <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    当前章节
                    <input
                        className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500"
                        value={`第 ${chapterOrder} 章`}
                        readOnly
                    />
                </label>
                <label className="space-y-1 text-sm font-medium text-slate-700">
                    生成数量
                    <input
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        min={1}
                        max={10}
                        type="number"
                        value={draftCount}
                        onChange={(event) => setDraftCount(event.target.value)}
                    />
                </label>
            </div>

            <label className="space-y-1 text-sm font-medium text-slate-700">
                Prompt 模板
                <select
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                    value={promptTemplateId}
                    onChange={(event) => setPromptTemplateId(event.target.value)}
                    disabled={isLoadingReferences}
                >
                    <option value="">请选择商务礼仪题目生成模板</option>
                    {promptTemplates.map((template) => (
                        <option key={template.id} value={template.id}>
                            {templateLabel(template)}
                        </option>
                    ))}
                </select>
                <span className="block text-xs font-normal leading-5 text-slate-500">
                    模板在「提示词管理」维护；这里只显示商务礼仪题目生成专用模板，不会回退展示通用系统模板。
                </span>
            </label>

            <label className="space-y-1 text-sm font-medium text-slate-700">
                LLM 模型配置
                <select
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
                    value={selectedModelConfigId}
                    onChange={(event) => setSelectedModelConfigId(event.target.value)}
                    disabled={isLoadingReferences}
                >
                    <option value="">系统默认 LLM 配置</option>
                    {llmConfigs.map((config) => (
                        <option key={config.id} value={config.id}>
                            {config.name} · {config.provider}/{config.model_name}
                            {config.is_default ? " · 默认" : ""}
                        </option>
                    ))}
                </select>
                <span className="block text-xs font-normal leading-5 text-slate-500">
                    模型在「系统设置 → 模型配置」维护；这里只选择用于本批 AI 生成的 LLM 配置。
                </span>
            </label>

            <div className="flex flex-wrap gap-2">
                {QUESTION_TYPES.map((type) => (
                    <label
                        key={type}
                        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
                    >
                        <input
                            checked={questionTypes.includes(type)}
                            type="checkbox"
                            onChange={() => toggleQuestionType(type)}
                        />
                        {TYPE_LABELS[type]}
                    </label>
                ))}
            </div>

            <label className="space-y-1 text-sm font-medium text-slate-700">
                能力点 key
                <input
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={capabilityKeysText}
                    onChange={(event) => setCapabilityKeysText(event.target.value)}
                    placeholder="可选，多个用英文逗号分隔；为空时按章节能力点生成"
                />
            </label>

            <label className="space-y-1 text-sm font-medium text-slate-700">
                高级模型参数 JSON（可选）
                <textarea
                    className="min-h-20 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs"
                    value={advancedModelConfigJson}
                    onChange={(event) => setAdvancedModelConfigJson(event.target.value)}
                    placeholder='例如 {"extra_config":{"temperature":0.2}}；通常无需填写'
                />
            </label>

            <label className="space-y-1 text-sm font-medium text-slate-700">
                操作原因
                <input
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                />
            </label>

            <Button onClick={requestGeneration} disabled={isGenerating || isLoadingReferences}>
                <Send className="mr-2 h-4 w-4" />
                {isGenerating ? "生成中..." : "生成待审核草稿"}
            </Button>
        </div>
    );
}
