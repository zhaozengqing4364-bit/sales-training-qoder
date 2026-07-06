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

function PublishedRevisionGuidance() {
    return (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            <p className="font-semibold">编辑将生成新修订</p>
            <p className="mt-1 text-emerald-800">
                保存修改会进入待发布修订；发布后只影响后续学员和后续评分，已提交录音、转写和评分结果继续保留当时快照。
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
    const [learnerRubricText, setLearnerRubricText] = useState(getDefaultRubric(initialPrompt));
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
            learnerRubric = normalizeLearnerRubric(
                parseJsonObject(learnerRubricText, "学员可见评分标准"),
            );
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
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-score-template">
                        评分说明
                    </label>
                    <textarea
                        id="sales-trainer-score-template"
                        value={scoringTemplate}
                        onChange={(event) => setScoringTemplate(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        rows={10}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm"
                    />
                </div>
                <div className="space-y-2">
                    <label className="text-sm font-medium text-slate-700" htmlFor="sales-trainer-learner-rubric">
                        学员可见评分标准（JSON）
                    </label>
                    <textarea
                        id="sales-trainer-learner-rubric"
                        value={learnerRubricText}
                        onChange={(event) => setLearnerRubricText(event.target.value)}
                        disabled={isSubmitting || !canEdit}
                        rows={10}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 font-mono text-sm"
                    />
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
                    {isSubmitting ? "保存中..." : mode === "create" ? "创建评分标准" : "保存评分标准"}
                </Button>
            </div>
        </form>
    );
}
