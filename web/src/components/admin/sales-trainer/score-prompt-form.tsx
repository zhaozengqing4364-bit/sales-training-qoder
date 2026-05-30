"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import type {
    SalesTrainerAudioScorePrompt,
    SalesTrainerAudioScorePromptCreateRequest,
    SalesTrainerAudioScorePromptUpdateRequest,
} from "@/lib/api/types";

interface SalesTrainerScorePromptFormProps {
    mode: "create" | "edit";
    initialPrompt?: SalesTrainerAudioScorePrompt | null;
    isSubmitting: boolean;
    onSubmit: (
        payload: SalesTrainerAudioScorePromptCreateRequest | SalesTrainerAudioScorePromptUpdateRequest,
    ) => Promise<void> | void;
}

function getDefaultSchema(prompt?: SalesTrainerAudioScorePrompt | null): string {
    return JSON.stringify(prompt?.output_schema ?? {}, null, 2);
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

export function SalesTrainerScorePromptForm({
    mode,
    initialPrompt,
    isSubmitting,
    onSubmit,
}: SalesTrainerScorePromptFormProps) {
    const [name, setName] = useState(initialPrompt?.name ?? "");
    const [purpose, setPurpose] = useState(initialPrompt?.purpose ?? "general_audio_scoring");
    const [systemPrompt, setSystemPrompt] = useState(getDefaultSystemPrompt(initialPrompt));
    const [scoringTemplate, setScoringTemplate] = useState(getDefaultScoringTemplate(initialPrompt));
    const [outputSchemaText, setOutputSchemaText] = useState(getDefaultSchema(initialPrompt));
    const [error, setError] = useState<string | null>(null);
    const canEdit = !initialPrompt || initialPrompt.status === "draft";

    async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);

        if (!canEdit) {
            setError("只有 draft 状态的录音评分标准可以修改。");
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

        let outputSchema: Record<string, unknown> = {};
        try {
            outputSchema = JSON.parse(outputSchemaText || "{}") as Record<string, unknown>;
        } catch {
            setError("输出 schema 必须是合法 JSON。");
            return;
        }

        await onSubmit({
            name: name.trim(),
            purpose: purpose.trim(),
            system_prompt: systemPrompt,
            scoring_template: scoringTemplate,
            output_schema: outputSchema,
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
                        <Input
                            id="sales-trainer-score-prompt-purpose"
                            value={purpose}
                            onChange={(event) => setPurpose(event.target.value)}
                            disabled={isSubmitting || !canEdit}
                        />
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

            {!canEdit ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    当前状态为 {initialPrompt?.status}，需要返回列表创建新的 draft 或执行发布流转。
                </div>
            ) : null}

            <div className="flex justify-end">
                <Button
                    type="submit"
                    disabled={isSubmitting || !canEdit}
                    className="rounded-full bg-slate-900 text-white"
                >
                    {isSubmitting ? "保存中..." : mode === "create" ? "创建评分标准" : "保存评分标准"}
                </Button>
            </div>
        </form>
    );
}
