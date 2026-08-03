"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import {
    formatTrainingPurpose,
    TRAINING_PURPOSE_OPTIONS,
} from "@/lib/sales-trainer/admin-display";
import type {
    SalesTrainerAudioScoreOutputSchema,
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerAudioScorePromptUpdateRequest,
    SalesTrainerLearnerRubric,
} from "@/lib/api/types";

interface SalesTrainerScorePromptFormProps {
    mode: "create" | "edit";
    initialPrompt?: SalesTrainerAudioScorePrompt | null;
    initialPurpose?: string | null;
    isSubmitting: boolean;
    onSubmit: (
        payload: SalesTrainerAudioScorePromptCreateRequest | SalesTrainerAudioScorePromptUpdateRequest,
    ) => Promise<void> | void;
    onCopyDraft?: () => void;
}

function getDefaultSchema(prompt?: SalesTrainerAudioScorePrompt | null): string {
    return JSON.stringify(prompt?.output_schema ?? {}, null, 2);
}

function getDefaultRubric(prompt?: SalesTrainerAudioScorePrompt | null): string {
    return JSON.stringify(
        prompt?.learner_rubric ?? {
            visible_to_learner: true,
            criteria: [],
            common_mistakes: [],
        },
        null,
        2,
    );
}

function getDefaultPassThreshold(prompt?: SalesTrainerAudioScorePrompt | null): string {
    const threshold = prompt?.learner_rubric?.pass_threshold;
    if (typeof threshold === "number" && Number.isFinite(threshold)) {
        return String(threshold);
    }
    return prompt ? "" : "70";
}

function getDefaultRubricCriteria(prompt?: SalesTrainerAudioScorePrompt | null): string {
    const criteria = prompt?.learner_rubric?.criteria;
    if (!Array.isArray(criteria) || criteria.length === 0) {
        if (prompt) {
            return "";
        }
        return [
            "内容准确性 | 30 | 关键信息完整、事实准确",
            "表达结构 | 30 | 讲解有开场、主体和结论",
            "客户价值 | 25 | 能把材料内容转化为客户收益",
            "行动建议 | 15 | 能给出明确下一步",
        ].join("\n");
    }
    return criteria.map((criterion) => [
        criterion.label,
        typeof criterion.weight === "number" ? criterion.weight : "",
        criterion.description ?? "",
    ].filter((item) => String(item).trim()).join(" | ")).join("\n");
}

function getDefaultCommonMistakes(prompt?: SalesTrainerAudioScorePrompt | null): string {
    return (prompt?.learner_rubric?.common_mistakes ?? []).join("\n");
}

function getDefaultSystemPrompt(prompt?: SalesTrainerAudioScorePrompt | null): string {
    return prompt?.system_prompt ?? "你是销售训练录音评分专家，请依据评分说明对学员录音转写文本给出客观评分。";
}

function getDefaultScoringTemplate(prompt?: SalesTrainerAudioScorePrompt | null): string {
    return prompt?.scoring_template ?? [
        "评分维度：内容准确性、沟通结构、客户洞察、行动建议。",
        "通过线：70 分。",
        "输出要求：返回总分、是否通过、总结、优点、改进建议和各维度分数。",
        "",
        "录音转写：",
        "{transcript}",
    ].join("\n");
}

function parseJsonObject(text: string, fieldLabel: string): Record<string, unknown> {
    const parsed = JSON.parse(text || "{}") as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error(`${fieldLabel} 必须是 JSON 对象。`);
    }
    return parsed as Record<string, unknown>;
}

function normalizeOutputSchema(value: Record<string, unknown>): SalesTrainerAudioScoreOutputSchema {
    const type = value.type ?? "object";
    if (type !== "object") {
        throw new Error("output_schema.type 必须是 object。");
    }
    const properties = value.properties;
    if (
        properties !== undefined
        && (!properties || typeof properties !== "object" || Array.isArray(properties))
    ) {
        throw new Error("output_schema.properties 必须是对象。");
    }
    const required = value.required;
    if (
        required !== undefined
        && (!Array.isArray(required) || required.some((item) => typeof item !== "string" || !item.trim()))
    ) {
        throw new Error("output_schema.required 必须是字符串数组。");
    }
    const propertyMap = properties as Record<string, unknown> | undefined;
    if (Array.isArray(required) && propertyMap) {
        const missing = required.filter((item) => !(item in propertyMap));
        if (missing.length > 0) {
            throw new Error("output_schema.required 字段必须先在 properties 中声明。");
        }
    }
    return value as SalesTrainerAudioScoreOutputSchema;
}

function normalizeLearnerRubric(value: Record<string, unknown>): SalesTrainerLearnerRubric {
    const criteria = value.criteria;
    if (criteria !== undefined && !Array.isArray(criteria)) {
        throw new Error("learner_rubric.criteria 必须是数组。");
    }
    if (Array.isArray(criteria)) {
        for (const item of criteria) {
            if (!item || typeof item !== "object" || Array.isArray(item)) {
                throw new Error("learner_rubric.criteria 每一项都必须是对象。");
            }
            const criterion = item as Record<string, unknown>;
            if (typeof criterion.key !== "string" || !criterion.key.trim()) {
                throw new Error("learner_rubric.criteria 每一项必须包含 key。");
            }
            if (typeof criterion.label !== "string" || !criterion.label.trim()) {
                throw new Error("learner_rubric.criteria 每一项必须包含 label。");
            }
        }
    }
    const commonMistakes = value.common_mistakes;
    if (
        commonMistakes !== undefined
        && (!Array.isArray(commonMistakes) || commonMistakes.some((item) => typeof item !== "string" || !item.trim()))
    ) {
        throw new Error("learner_rubric.common_mistakes 必须是非空字符串数组。");
    }
    return value as SalesTrainerLearnerRubric;
}

function textToList(text: string): string[] {
    return text
        .split(/\n/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function slugKey(text: string, index: number): string {
    const normalized = text
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "_")
        .replace(/^_+|_+$/g, "");
    return normalized || `criterion_${index + 1}`;
}

function parseOptionalNumber(value: string, label: string): number | null {
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
        throw new Error(`${label}必须是数字。`);
    }
    if (parsed < 0 || parsed > 100) {
        throw new Error(`${label}必须在 0 到 100 之间。`);
    }
    return parsed;
}

function buildLearnerRubric({
    commonMistakesText,
    criteriaText,
    learnerRubricJsonText,
    passThreshold,
    initialRubric,
    visibleToLearner,
}: {
    readonly commonMistakesText: string;
    readonly criteriaText: string;
    readonly initialRubric?: SalesTrainerLearnerRubric | null;
    readonly learnerRubricJsonText: string;
    readonly passThreshold: string;
    readonly visibleToLearner: boolean;
}): SalesTrainerLearnerRubric {
    if (learnerRubricJsonText.trim()) {
        return normalizeLearnerRubric(
            parseJsonObject(learnerRubricJsonText, "学员可见评分标准 JSON"),
        );
    }
    if (!criteriaText.trim() && !commonMistakesText.trim() && !passThreshold.trim()) {
        return initialRubric ?? {};
    }
    return {
        visible_to_learner: visibleToLearner,
        pass_threshold: parseOptionalNumber(passThreshold, "通过分"),
        criteria: textToList(criteriaText).map((line, index) => {
            const [rawLabel, rawWeight, ...descriptionParts] = line.split("|").map((part) => part.trim());
            const label = rawLabel || `评分维度 ${index + 1}`;
            return {
                key: slugKey(label, index),
                label,
                weight: rawWeight ? parseOptionalNumber(rawWeight, "维度权重") : null,
                description: descriptionParts.join(" | ") || null,
            };
        }),
        common_mistakes: textToList(commonMistakesText),
    };
}

function PublishedRevisionGuidance() {
    return (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <p className="font-semibold">保存并发布后只影响后续评分</p>
            <p className="mt-1 text-emerald-800">
                系统会先保存一份可审计修订，再发布为当前有效版本。已提交录音、转写和评分结果继续保留当时快照。
                需要重新评分历史记录时，请走单独的高风险重评流程。
            </p>
        </div>
    );
}

function ArchivedReadOnlyGuidance() {
    return (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            归档版本仅用于审计和历史追溯，不能继续编辑；需要恢复使用时请在历史版本中执行回滚。
        </div>
    );
}

export function SalesTrainerScorePromptForm({
    mode,
    initialPrompt,
    initialPurpose,
    isSubmitting,
    onSubmit,
}: SalesTrainerScorePromptFormProps) {
    const [name, setName] = useState(initialPrompt?.name ?? "");
    const [purpose, setPurpose] = useState(initialPrompt?.purpose ?? initialPurpose ?? "general_audio_scoring");
    const [systemPrompt, setSystemPrompt] = useState(getDefaultSystemPrompt(initialPrompt));
    const [scoringTemplate, setScoringTemplate] = useState(getDefaultScoringTemplate(initialPrompt));
    const [outputSchemaText, setOutputSchemaText] = useState(getDefaultSchema(initialPrompt));
    const [passThreshold, setPassThreshold] = useState(getDefaultPassThreshold(initialPrompt));
    const [criteriaText, setCriteriaText] = useState(getDefaultRubricCriteria(initialPrompt));
    const [commonMistakesText, setCommonMistakesText] = useState(getDefaultCommonMistakes(initialPrompt));
    const [visibleToLearner, setVisibleToLearner] = useState(initialPrompt?.learner_rubric?.visible_to_learner !== false);
    const [learnerRubricJsonText, setLearnerRubricJsonText] = useState("");
    const [error, setError] = useState<string | null>(null);
    const canEdit = !initialPrompt || initialPrompt.status !== "archived";
    const isPublished = initialPrompt?.status === "published";
    const isArchived = initialPrompt?.status === "archived";
    const hasKnownPurpose = TRAINING_PURPOSE_OPTIONS.some((option) => option.value === purpose);

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);

        if (isArchived) {
            setError("归档版本仅用于审计和历史追溯，不能继续编辑；请在历史版本中回滚后再用于后续学员。");
            return;
        }

        if (!name.trim() || !systemPrompt.trim() || !scoringTemplate.trim()) {
            setError("名称、系统提示词和评分说明不能为空。");
            return;
        }

        if (!scoringTemplate.includes("{transcript}")) {
            setError("评分说明必须包含 {transcript} 占位符。");
            return;
        }

        let outputSchema: SalesTrainerAudioScoreOutputSchema = {};
        let learnerRubric: SalesTrainerLearnerRubric = {};
        try {
            outputSchema = normalizeOutputSchema(
                parseJsonObject(outputSchemaText, "输出 schema"),
            );
        } catch (parseError) {
            setError(parseError instanceof Error ? parseError.message : "输出 schema 必须是合法 JSON 对象。");
            return;
        }
        try {
            learnerRubric = buildLearnerRubric({
                commonMistakesText,
                criteriaText,
                initialRubric: initialPrompt?.learner_rubric,
                learnerRubricJsonText,
                passThreshold,
                visibleToLearner,
            });
        } catch (parseError) {
            setError(parseError instanceof Error ? parseError.message : "学员可见评分标准必须是合法 JSON 对象。");
            return;
        }

        await onSubmit({
            name: name.trim(),
            purpose: purpose.trim(),
            system_prompt: systemPrompt,
            scoring_template: scoringTemplate,
            output_schema: outputSchema,
            learner_rubric: learnerRubric,
        });
    }

    return (
        <form className="space-y-6" onSubmit={handleSubmit}>
            <GlassCard className="space-y-4 p-6">
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-prompt-name">
                            评分标准名称
                        </label>
                        <Input
                            id="sales-trainer-score-prompt-name"
                            value={name}
                            onChange={(event) => setName(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-prompt-purpose">
                            适用用途
                        </label>
                        <select
                            id="sales-trainer-score-prompt-purpose"
                            value={purpose}
                            onChange={(event) => setPurpose(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm"
                        >
                            {TRAINING_PURPOSE_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                            {!hasKnownPurpose && purpose ? (
                                <option value={purpose}>{formatTrainingPurpose(purpose)}</option>
                            ) : null}
                        </select>
                    </div>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-pass-threshold">
                        通过分
                    </label>
                    <Input
                        id="sales-trainer-score-pass-threshold"
                        type="number"
                        min={0}
                        max={100}
                        value={passThreshold}
                        onChange={(event) => setPassThreshold(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                    />
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-template">
                        评分说明
                    </label>
                    <textarea
                        id="sales-trainer-score-template"
                        value={scoringTemplate}
                        onChange={(event) => setScoringTemplate(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        rows={16}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm"
                    />
                    <p className="text-xs leading-5 text-slate-500">
                        当前 {scoringTemplate.length.toLocaleString("zh-CN")} 字；系统会完整保存，并在评分时将 {"{transcript}"} 替换为录音转写。内容越长，评分耗时可能越高。
                    </p>
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-learner-rubric-criteria">
                        评分维度
                    </label>
                    <textarea
                        id="sales-trainer-learner-rubric-criteria"
                        value={criteriaText}
                        onChange={(event) => setCriteriaText(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        rows={6}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                        placeholder="每行一个维度，可写成：维度名称 | 权重 | 学员可见说明"
                    />
                </div>
                <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-learner-common-mistakes">
                            常见问题
                        </label>
                        <textarea
                            id="sales-trainer-learner-common-mistakes"
                            value={commonMistakesText}
                            onChange={(event) => setCommonMistakesText(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                            rows={4}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            placeholder="每行一个常见问题"
                        />
                    </div>
                    <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                        <input
                            type="checkbox"
                            checked={visibleToLearner}
                            onChange={(event) => setVisibleToLearner(event.target.checked)}
                            disabled={isSubmitting || !canEdit}
                        />
                        学员可见
                    </label>
                </div>
                <details className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700">高级模式</summary>
                    <div className="mt-4 space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-system-prompt">
                                system_prompt
                            </label>
                            <textarea
                                id="sales-trainer-score-system-prompt"
                                value={systemPrompt}
                                onChange={(event) => setSystemPrompt(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                rows={6}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-output-schema">
                                output_schema（JSON）
                            </label>
                            <textarea
                                id="sales-trainer-score-output-schema"
                                value={outputSchemaText}
                                onChange={(event) => setOutputSchemaText(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                rows={8}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-learner-rubric-json">
                                学员评分标准 JSON（可选覆盖）
                            </label>
                            <textarea
                                id="sales-trainer-learner-rubric-json"
                                value={learnerRubricJsonText}
                                onChange={(event) => setLearnerRubricJsonText(event.target.value)}
                                disabled={isSubmitting || !canEdit}
                                rows={6}
                                placeholder={getDefaultRubric(initialPrompt)}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm"
                            />
                        </div>
                    </div>
                </details>
            </GlassCard>

            {error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            ) : null}

            {isPublished ? <PublishedRevisionGuidance /> : null}
            {isArchived ? <ArchivedReadOnlyGuidance /> : null}

            <div className="flex justify-end">
                <Button
                    type="submit"
                    disabled={isSubmitting || isArchived}
                    className="rounded-full bg-slate-900 text-white"
                >
                    {isSubmitting
                        ? mode === "create" ? "创建中..." : "保存并发布中..."
                        : mode === "create" ? "创建评分标准" : "保存并发布"}
                </Button>
            </div>
        </form>
    );
}
