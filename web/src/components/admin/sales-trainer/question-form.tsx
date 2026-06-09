"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import {
    canEditQuestionRevision,
    QuestionArchivedReadOnlyGuidance,
    QuestionPublishedRevisionGuidance,
} from "@/components/admin/sales-trainer/question-form-governance";
import type {
    QuestionDifficulty,
    SalesTrainerQuestion,
    SalesTrainerQuestionCategory,
    SalesTrainerQuestionCreateRequest,
    SalesTrainerQuestionOption,
    SalesTrainerQuestionType,
    SalesTrainerQuestionUpdateRequest,
} from "@/lib/api/types";

interface SalesTrainerQuestionFormProps {
    mode: "create" | "edit";
    initialQuestion?: SalesTrainerQuestion | null;
    categories: SalesTrainerQuestionCategory[];
    isSubmitting: boolean;
    onSubmit: (
        payload: SalesTrainerQuestionCreateRequest | SalesTrainerQuestionUpdateRequest,
    ) => Promise<void> | void;
}

const QUESTION_TYPES: Array<{ value: SalesTrainerQuestionType; label: string }> = [
    { value: "single_choice", label: "单选题" },
    { value: "multiple_choice", label: "多选题" },
    { value: "true_false", label: "判断题" },
    { value: "short_answer", label: "简答题" },
];

function defaultOptions(question?: SalesTrainerQuestion | null): SalesTrainerQuestionOption[] {
    if (question?.options?.length) {
        return question.options;
    }
    return [
        { value: "A", label: "" },
        { value: "B", label: "" },
        { value: "C", label: "" },
        { value: "D", label: "" },
    ];
}

function tagsToText(tags: string[]): string {
    return tags.join(", ");
}

function textToList(text: string): string[] {
    return text
        .split(/[\n,，]/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function getAiScoringConfig(question?: SalesTrainerQuestion | null): Record<string, unknown> {
    const config = question?.ai_scoring;
    return config && typeof config === "object" && !Array.isArray(config) ? config : {};
}

function configString(config: Record<string, unknown>, key: string): string {
    const value = config[key];
    return typeof value === "string" ? value : "";
}

function configNumberText(config: Record<string, unknown>, key: string, fallback = ""): string {
    const value = config[key];
    return typeof value === "number" && Number.isFinite(value) ? String(value) : fallback;
}

function parseOptionalNumber(
    value: string,
    label: string,
    options: { min?: number; max?: number; integer?: boolean } = {},
): number | undefined {
    const trimmed = value.trim();
    if (!trimmed) {
        return undefined;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
        throw new Error(`${label}必须是数字。`);
    }
    if (options.integer && !Number.isInteger(parsed)) {
        throw new Error(`${label}必须是整数。`);
    }
    if (options.min !== undefined && parsed < options.min) {
        throw new Error(`${label}不能小于 ${options.min}。`);
    }
    if (options.max !== undefined && parsed > options.max) {
        throw new Error(`${label}不能大于 ${options.max}。`);
    }
    return parsed;
}

export function SalesTrainerQuestionForm({
    mode,
    initialQuestion,
    categories,
    isSubmitting,
    onSubmit,
}: SalesTrainerQuestionFormProps) {
    const initialAiScoring = getAiScoringConfig(initialQuestion);
    const [title, setTitle] = useState(initialQuestion?.title ?? "");
    const [stem, setStem] = useState(initialQuestion?.stem ?? "");
    const [categoryId, setCategoryId] = useState(initialQuestion?.category_id ?? categories[0]?.category_id ?? "");
    const [questionType, setQuestionType] = useState<SalesTrainerQuestionType>(
        initialQuestion?.question_type ?? "single_choice",
    );
    const [difficulty, setDifficulty] = useState<QuestionDifficulty>(initialQuestion?.difficulty ?? "medium");
    const [tags, setTags] = useState(tagsToText(initialQuestion?.tags ?? []));
    const [department, setDepartment] = useState(initialQuestion?.department ?? "");
    const [safetyFlagged, setSafetyFlagged] = useState(Boolean(initialQuestion?.safety_flagged));
    const [options, setOptions] = useState<SalesTrainerQuestionOption[]>(defaultOptions(initialQuestion));
    const [correctAnswer, setCorrectAnswer] = useState(initialQuestion?.correct_answer ?? "");
    const [correctAnswersText, setCorrectAnswersText] = useState(
        (initialQuestion?.correct_answers ?? []).join(", "),
    );
    const [correctBool, setCorrectBool] = useState(
        initialQuestion?.correct_bool === false ? "false" : "true",
    );
    const [referenceAnswer, setReferenceAnswer] = useState(initialQuestion?.reference_answer ?? "");
    const [scoringDimensions, setScoringDimensions] = useState(
        (initialQuestion?.scoring_dimensions ?? []).join("\n"),
    );
    const [explanation, setExplanation] = useState(initialQuestion?.explanation ?? "");
    const [aiScoringEnabled, setAiScoringEnabled] = useState(
        initialAiScoring.enabled === false ? "false" : "true",
    );
    const [aiModelConfigId, setAiModelConfigId] = useState(configString(initialAiScoring, "model_config_id"));
    const [aiPassThreshold, setAiPassThreshold] = useState(configNumberText(initialAiScoring, "pass_threshold"));
    const [aiTemperature, setAiTemperature] = useState(configNumberText(initialAiScoring, "temperature"));
    const [aiTimeout, setAiTimeout] = useState(configNumberText(initialAiScoring, "timeout"));
    const [aiMaxRetries, setAiMaxRetries] = useState(configNumberText(initialAiScoring, "max_retries"));
    const [aiMaxTokens, setAiMaxTokens] = useState(configNumberText(initialAiScoring, "max_tokens"));
    const [aiSystemPrompt, setAiSystemPrompt] = useState(configString(initialAiScoring, "system_prompt"));
    const [aiPromptTemplate, setAiPromptTemplate] = useState(configString(initialAiScoring, "prompt_template"));
    const [error, setError] = useState<string | null>(null);
    const canEdit = canEditQuestionRevision(initialQuestion?.status);
    const isPublished = initialQuestion?.status === "published";
    const isArchived = initialQuestion?.status === "archived";

    function updateOption(index: number, patch: Partial<SalesTrainerQuestionOption>) {
        setOptions((current) =>
            current.map((option, optionIndex) =>
                optionIndex === index ? { ...option, ...patch } : option,
            ),
        );
    }

    function addOption() {
        const nextValue = String.fromCharCode(65 + options.length);
        setOptions((current) => [...current, { value: nextValue, label: "" }]);
    }

    function removeOption(index: number) {
        setOptions((current) => current.filter((_, optionIndex) => optionIndex !== index));
    }

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);
        if (isArchived) {
            setError("归档题目仅用于审计和历史追溯，不能继续编辑；请在历史版本中回滚后再用于后续组卷。");
            return;
        }
        if (!title.trim() || !stem.trim() || !categoryId) {
            setError("题目标题、题干和分类不能为空。");
            return;
        }
        const cleanOptions = options
            .map((option) => ({
                value: option.value.trim(),
                label: option.label.trim(),
            }))
            .filter((option) => option.value && option.label);
        const payload: SalesTrainerQuestionCreateRequest = {
            title: title.trim(),
            stem: stem.trim(),
            category_id: categoryId,
            question_type: questionType,
            difficulty,
            tags: textToList(tags),
            department: department.trim() || null,
            safety_flagged: safetyFlagged,
            scoring_dimensions: textToList(scoringDimensions),
            explanation: explanation.trim() || null,
        };
        if (questionType === "single_choice") {
            payload.options = cleanOptions;
            payload.correct_answer = correctAnswer.trim() || null;
        } else if (questionType === "multiple_choice") {
            payload.options = cleanOptions;
            payload.correct_answers = textToList(correctAnswersText);
        } else if (questionType === "true_false") {
            payload.correct_bool = correctBool === "true";
        } else {
            payload.reference_answer = referenceAnswer.trim();
            let aiConfig: Record<string, unknown>;
            try {
                aiConfig = {
                    enabled: aiScoringEnabled === "true",
                    ...(aiPassThreshold.trim() ? {
                        pass_threshold: parseOptionalNumber(aiPassThreshold, "简答通过线", {
                            min: 0,
                            max: 100,
                        }),
                    } : {}),
                    ...(aiModelConfigId.trim() ? { model_config_id: aiModelConfigId.trim() } : {}),
                    ...(aiTemperature.trim() ? {
                        temperature: parseOptionalNumber(aiTemperature, "温度", {
                            min: 0,
                            max: 2,
                        }),
                    } : {}),
                    ...(aiTimeout.trim() ? {
                        timeout: parseOptionalNumber(aiTimeout, "超时秒数", {
                            min: 1,
                            max: 120,
                        }),
                    } : {}),
                    ...(aiMaxRetries.trim() ? {
                        max_retries: parseOptionalNumber(aiMaxRetries, "重试次数", {
                            min: 0,
                            max: 5,
                            integer: true,
                        }),
                    } : {}),
                    ...(aiMaxTokens.trim() ? {
                        max_tokens: parseOptionalNumber(aiMaxTokens, "最大输出 tokens", {
                            min: 1,
                            max: 4000,
                            integer: true,
                        }),
                    } : {}),
                    ...(aiSystemPrompt.trim() ? { system_prompt: aiSystemPrompt.trim() } : {}),
                    ...(aiPromptTemplate.trim() ? { prompt_template: aiPromptTemplate.trim() } : {}),
                };
            } catch (parseError) {
                setError(parseError instanceof Error ? parseError.message : "AI 评分参数不合法。");
                return;
            }
            payload.ai_scoring = aiConfig;
        }
        await onSubmit(payload);
    }

    return (
        <form className="space-y-6" noValidate onSubmit={handleSubmit}>
            <GlassCard className="space-y-5 p-6">
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-title">题目标题</label>
                        <Input id="sales-trainer-question-title" value={title} onChange={(event) => setTitle(event.target.value)} disabled={isSubmitting || !canEdit} />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-category">题目分类</label>
                        <select
                            id="sales-trainer-question-category"
                            value={categoryId}
                            onChange={(event) => setCategoryId(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            <option value="">请选择分类</option>
                            {categories.map((category) => (
                                <option key={category.category_id} value={category.category_id}>{category.name}</option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-type">题型</label>
                        <select
                            id="sales-trainer-question-type"
                            value={questionType}
                            onChange={(event) => setQuestionType(event.target.value as SalesTrainerQuestionType)}
                            disabled={isSubmitting || !canEdit}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            {QUESTION_TYPES.map((type) => (
                                <option key={type.value} value={type.value}>{type.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-difficulty">难度</label>
                        <select
                            id="sales-trainer-question-difficulty"
                            value={difficulty}
                            onChange={(event) => setDifficulty(event.target.value as QuestionDifficulty)}
                            disabled={isSubmitting || !canEdit}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            <option value="easy">简单</option>
                            <option value="medium">中等</option>
                            <option value="hard">困难</option>
                        </select>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-stem">题干</label>
                    <textarea
                        id="sales-trainer-question-stem"
                        value={stem}
                        onChange={(event) => setStem(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        rows={5}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-tags">标签</label>
                        <Input id="sales-trainer-question-tags" value={tags} onChange={(event) => setTags(event.target.value)} disabled={isSubmitting || !canEdit} placeholder="逗号分隔" />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-department">适用部门</label>
                        <Input id="sales-trainer-question-department" value={department} onChange={(event) => setDepartment(event.target.value)} disabled={isSubmitting || !canEdit} />
                    </div>
                </div>

                <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={safetyFlagged} onChange={(event) => setSafetyFlagged(event.target.checked)} disabled={isSubmitting || !canEdit} />
                    标记为需要安全复核
                </label>
            </GlassCard>

            <GlassCard className="space-y-2 p-6">
                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-explanation">答案解析</label>
                <textarea
                    id="sales-trainer-question-explanation"
                    value={explanation}
                    onChange={(event) => setExplanation(event.target.value)}
                    disabled={isSubmitting || !canEdit}
                    rows={4}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                    placeholder="学员提交后展示，用于说明为什么这样作答。"
                />
            </GlassCard>

            {(questionType === "single_choice" || questionType === "multiple_choice") ? (
                <GlassCard className="space-y-4 p-6">
                    <div className="flex items-center justify-between gap-3">
                        <h2 className="text-lg font-bold text-slate-900">选项与答案</h2>
                        <Button type="button" variant="outline" size="sm" onClick={addOption} disabled={isSubmitting || !canEdit}>添加选项</Button>
                    </div>
                    <div className="space-y-3">
                        {options.map((option, index) => (
                            <div key={`${option.value}-${index}`} className="grid gap-3 md:grid-cols-[96px_1fr_auto]">
                                <Input value={option.value} onChange={(event) => updateOption(index, { value: event.target.value })} disabled={isSubmitting || !canEdit} aria-label={`选项 ${index + 1} 值`} />
                                <Input value={option.label} onChange={(event) => updateOption(index, { label: event.target.value })} disabled={isSubmitting || !canEdit} aria-label={`选项 ${index + 1} 内容`} />
                                <Button type="button" variant="ghost" size="sm" onClick={() => removeOption(index)} disabled={isSubmitting || !canEdit || options.length <= 2}>移除</Button>
                            </div>
                        ))}
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-answer">
                            {questionType === "single_choice" ? "正确答案" : "正确答案"}
                        </label>
                        <Input
                            id="sales-trainer-question-answer"
                            value={questionType === "single_choice" ? correctAnswer : correctAnswersText}
                            onChange={(event) => questionType === "single_choice" ? setCorrectAnswer(event.target.value) : setCorrectAnswersText(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            placeholder={questionType === "single_choice" ? "例如 A" : "例如 A, C"}
                        />
                    </div>
                </GlassCard>
            ) : null}

            {questionType === "true_false" ? (
                <GlassCard className="space-y-2 p-6">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-true-false">正确判断</label>
                    <select
                        id="sales-trainer-question-true-false"
                        value={correctBool}
                        onChange={(event) => setCorrectBool(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                    >
                        <option value="true">正确</option>
                        <option value="false">错误</option>
                    </select>
                </GlassCard>
            ) : null}

            {questionType === "short_answer" ? (
                <GlassCard className="space-y-5 p-6">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-reference">参考答案</label>
                        <textarea
                            id="sales-trainer-question-reference"
                            value={referenceAnswer}
                            onChange={(event) => setReferenceAnswer(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            rows={6}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-dimensions">评分维度</label>
                        <textarea
                            id="sales-trainer-question-dimensions"
                            value={scoringDimensions}
                            onChange={(event) => setScoringDimensions(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            rows={4}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            placeholder="每行一个维度"
                        />
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-enabled">AI 评分</label>
                            <select
                                id="sales-trainer-question-ai-enabled"
                                value={aiScoringEnabled}
                                onChange={(event) => setAiScoringEnabled(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                            >
                                <option value="true">启用</option>
                                <option value="false">停用</option>
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-threshold">简答通过线</label>
                            <Input
                                id="sales-trainer-question-ai-threshold"
                                type="number"
                                min={0}
                                max={100}
                                value={aiPassThreshold}
                                onChange={(event) => setAiPassThreshold(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-model-config">模型配置 ID</label>
                            <Input
                                id="sales-trainer-question-ai-model-config"
                                value={aiModelConfigId}
                                onChange={(event) => setAiModelConfigId(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                placeholder="留空使用默认 LLM 配置"
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-temperature">温度</label>
                                <Input id="sales-trainer-question-ai-temperature" type="number" step="0.1" min={0} max={2} value={aiTemperature} onChange={(event) => setAiTemperature(event.target.value)} disabled={isSubmitting || !canEdit} />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-timeout">超时秒数</label>
                                <Input id="sales-trainer-question-ai-timeout" type="number" min={1} max={120} value={aiTimeout} onChange={(event) => setAiTimeout(event.target.value)} disabled={isSubmitting || !canEdit} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 md:col-span-2">
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-retries">重试次数</label>
                                <Input id="sales-trainer-question-ai-retries" type="number" min={0} max={5} value={aiMaxRetries} onChange={(event) => setAiMaxRetries(event.target.value)} disabled={isSubmitting || !canEdit} />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-max-tokens">最大输出 tokens</label>
                                <Input id="sales-trainer-question-ai-max-tokens" type="number" min={1} max={4000} value={aiMaxTokens} onChange={(event) => setAiMaxTokens(event.target.value)} disabled={isSubmitting || !canEdit} />
                            </div>
                        </div>
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-system">系统提示词</label>
                        <textarea
                            id="sales-trainer-question-ai-system"
                            value={aiSystemPrompt}
                            onChange={(event) => setAiSystemPrompt(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            rows={3}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            placeholder="留空使用新人训练路径默认简答评分角色"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-question-ai-template">评分提示词模板</label>
                        <textarea
                            id="sales-trainer-question-ai-template"
                            value={aiPromptTemplate}
                            onChange={(event) => setAiPromptTemplate(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            rows={6}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            placeholder="可使用 {title}、{stem}、{reference_answer}、{dimensions}、{criteria}、{answer}"
                        />
                    </div>
                </GlassCard>
            ) : null}

            {error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
            ) : null}

            {isPublished ? <QuestionPublishedRevisionGuidance /> : null}
            {isArchived ? <QuestionArchivedReadOnlyGuidance /> : null}

            <div className="flex justify-end">
                <Button type="submit" disabled={isSubmitting || isArchived}>
                    {isSubmitting ? "保存中..." : mode === "create" ? "创建题目" : "保存题目"}
                </Button>
            </div>
        </form>
    );
}
