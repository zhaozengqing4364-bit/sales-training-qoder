"use client";

import { Check, Loader2, Send, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
    AiCoachAnswerPayloadV1,
    AiCoachUiEventPublicV1,
} from "@/lib/api/types";

import {
    draftForChoice,
    draftForText,
    eventScoreState,
    isAnswerPayloadSubmittable,
    selectedOptionIds,
    textAnswer,
} from "./coach-session";

export function GenerativeCard({
    event,
    draft,
    isActive,
    isSubmitting,
    onFollowupPrompt,
    onDraftChange,
    onSubmit,
}: {
    readonly event: AiCoachUiEventPublicV1;
    readonly draft: AiCoachAnswerPayloadV1 | null;
    readonly isActive: boolean;
    readonly isSubmitting: boolean;
    readonly onFollowupPrompt: (prompt: string) => void;
    readonly onDraftChange: (payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmit: () => void;
}) {
    switch (event.type) {
        case "quiz_card":
            return (
                <QuizCard
                    event={event}
                    draft={draft}
                    isActive={isActive}
                    isSubmitting={isSubmitting}
                    onDraftChange={onDraftChange}
                    onSubmit={onSubmit}
                />
            );
        case "explanation_card":
            return (
                <section className="rounded-2xl border border-violet-100 bg-white p-5 shadow-sm">
                    <CardBadge>解析</CardBadge>
                    {event.payload.title ? (
                        <h2 className="mt-3 text-base font-semibold text-slate-950">
                            {event.payload.title}
                        </h2>
                    ) : null}
                    <p className="mt-2 text-sm leading-relaxed text-slate-700">
                        {event.payload.body}
                    </p>
                </section>
            );
        case "summary_card":
            return (
                <section className="rounded-2xl border border-violet-100 bg-white p-5 shadow-sm">
                    <CardBadge>复盘</CardBadge>
                    {event.payload.title ? (
                        <h2 className="mt-3 text-base font-semibold text-slate-950">
                            {event.payload.title}
                        </h2>
                    ) : null}
                    <ul className="mt-3 space-y-2 text-sm text-slate-700">
                        {event.payload.items.map((item) => (
                            <li key={item} className="rounded-xl bg-slate-50 px-3 py-2">
                                {item}
                            </li>
                        ))}
                    </ul>
                    <SummaryDetails payload={event.payload} />
                </section>
            );
        case "followup_prompt":
            return (
                <section className="rounded-2xl border border-violet-100 bg-white p-5 shadow-sm">
                    <CardBadge>追问</CardBadge>
                    <div className="mt-3 flex flex-wrap gap-2">
                        {event.payload.prompts.map((prompt) => (
                            <button
                                key={prompt}
                                type="button"
                                onClick={() => onFollowupPrompt(prompt)}
                                className="rounded-full border border-violet-100 bg-violet-50 px-3 py-1.5 text-sm text-violet-700"
                            >
                                {prompt}
                            </button>
                        ))}
                    </div>
                </section>
            );
        case "assistant_text":
        case "quiz_result":
            return null;
        default: {
            const exhaustive: never = event;
            return exhaustive;
        }
    }
}

function QuizCard({
    event,
    draft,
    isActive,
    isSubmitting,
    onDraftChange,
    onSubmit,
}: {
    readonly event: Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }>;
    readonly draft: AiCoachAnswerPayloadV1 | null;
    readonly isActive: boolean;
    readonly isSubmitting: boolean;
    readonly onDraftChange: (payload: AiCoachAnswerPayloadV1) => void;
    readonly onSubmit: () => void;
}) {
    const interaction = event.payload.interaction;
    const submitted = event.answer_payload;
    const value = submitted ?? draft;
    const selected = selectedOptionIds(value);
    const multiple = interaction.interaction_type === "multiple_choice";
    const shortAnswer = interaction.interaction_type === "short_answer";
    const scored = event.status === "scored" && event.score_result !== null;
    const canSubmit = isActive && isAnswerPayloadSubmittable(interaction, draft);
    const state = eventScoreState(event);
    return (
        <section className="rounded-2xl border border-violet-100 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
                <CardBadge>{shortAnswer ? "简答" : multiple ? "多选" : "单选"}</CardBadge>
                {scored ? (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                        已提交
                    </span>
                ) : null}
            </div>
            <h2 className="mt-4 text-base font-semibold leading-relaxed text-slate-950">
                {interaction.stem}
            </h2>
            {shortAnswer ? (
                <textarea
                    value={textAnswer(value)}
                    disabled={!isActive || scored || isSubmitting}
                    onChange={(changeEvent) => onDraftChange(draftForText(changeEvent.target.value))}
                    rows={4}
                    className="mt-4 w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-relaxed text-slate-900 outline-none focus:border-violet-300"
                />
            ) : (
                <div className="mt-4 space-y-2">
                    {(interaction.options ?? []).map((option) => {
                        const isSelected = selected.includes(option.option_id);
                        return (
                            <button
                                key={option.option_id}
                                type="button"
                                disabled={!isActive || scored || isSubmitting}
                                onClick={() =>
                                    onDraftChange(draftForChoice(value, option.option_id, multiple))
                                }
                                className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm transition ${optionStateClass(
                                    isSelected,
                                    scored,
                                    state,
                                )}`}
                            >
                                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-white text-xs font-bold">
                                    {option.option_id}
                                </span>
                                <span className="flex-1 text-slate-800">{option.text}</span>
                                {scored && isSelected ? (
                                    state === "correct" ? (
                                        <Check className="h-4 w-4 text-emerald-600" />
                                    ) : (
                                        <X className="h-4 w-4 text-red-600" />
                                    )
                                ) : null}
                            </button>
                        );
                    })}
                </div>
            )}
            {event.payload.explanation && scored ? (
                <p className="mt-4 rounded-xl bg-violet-50 px-4 py-3 text-sm leading-relaxed text-violet-800">
                    {event.payload.explanation}
                </p>
            ) : null}
            {event.score_result ? <ScoreFeedback event={event} /> : null}
            {!scored ? (
                <div className="mt-4 flex justify-end">
                    <Button
                        className="rounded-full bg-violet-600 hover:bg-violet-700"
                        disabled={!canSubmit || isSubmitting}
                        onClick={onSubmit}
                    >
                        {isSubmitting ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                            <Send className="mr-2 h-4 w-4" />
                        )}
                        提交
                    </Button>
                </div>
            ) : null}
        </section>
    );
}

function ScoreFeedback({
    event,
}: {
    readonly event: Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }>;
}) {
    const result = event.score_result;
    if (!result) {
        return null;
    }
    const interaction = event.payload.interaction;
    const isChoice =
        interaction.interaction_type === "single_choice"
        || interaction.interaction_type === "multiple_choice";
    const mastered = result.mastered ?? result.score >= result.max_score;
    const percent = result.max_score > 0
        ? Math.round((result.score / result.max_score) * 100)
        : null;
    const thresholdLabel = formatThreshold(result.mastery_threshold);
    const title = isChoice
        ? mastered ? "答对" : "未掌握"
        : mastered ? "已达到掌握标准" : "未达到掌握标准";
    const standardText = thresholdLabel
        ? mastered
            ? `已达到本轮掌握标准：${thresholdLabel}`
            : `未达到本轮掌握标准：${thresholdLabel}`
        : mastered
            ? "已达到本轮掌握标准"
            : "未达到本轮掌握标准";
    return (
        <div className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${mastered
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}>
                    {title}
                </span>
                <span className="text-xs font-medium text-slate-500">
                    {standardText}
                </span>
                {!isChoice && percent !== null ? (
                    <span className="text-xs font-medium text-slate-500">
                        本题掌握度：{percent}%
                    </span>
                ) : null}
            </div>
            <p className="mt-2 leading-relaxed">{result.feedback}</p>
            {result.missed_points.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5">
                    {result.missed_points.map((point) => (
                        <li key={point}>{point}</li>
                    ))}
                </ul>
            ) : null}
        </div>
    );
}

function formatThreshold(threshold: number | null | undefined): string | null {
    if (typeof threshold !== "number") {
        return null;
    }
    return `${Math.round(threshold)}%`;
}

function SummaryDetails({
    payload,
}: {
    readonly payload: Extract<AiCoachUiEventPublicV1, { type: "summary_card" }>["payload"];
}) {
    const groups = [
        ["优势", payload.strengths ?? []],
        ["短板", payload.weaknesses ?? []],
        ["下一步", payload.next_steps ?? []],
    ] as const;
    return (
        <div className="mt-4 space-y-3">
            {typeof payload.score_percent === "number" || typeof payload.mastered === "boolean" ? (
                <div className="flex flex-wrap gap-2 text-xs">
                    {typeof payload.score_percent === "number" ? (
                        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">
                            {Math.round(payload.score_percent)}%
                        </span>
                    ) : null}
                    {typeof payload.mastered === "boolean" ? (
                        <span className="rounded-full bg-violet-100 px-3 py-1 text-violet-700">
                            {payload.mastered ? "已掌握" : "继续练习"}
                        </span>
                    ) : null}
                </div>
            ) : null}
            {groups.map(([label, items]) =>
                items.length > 0 ? (
                    <div key={label}>
                        <p className="text-xs font-semibold text-slate-500">{label}</p>
                        <ul className="mt-2 space-y-1 text-sm text-slate-700">
                            {items.map((item) => (
                                <li key={item} className="rounded-xl bg-slate-50 px-3 py-2">
                                    {item}
                                </li>
                            ))}
                        </ul>
                    </div>
                ) : null,
            )}
        </div>
    );
}

function optionStateClass(
    isSelected: boolean,
    scored: boolean,
    state: "correct" | "wrong" | "pending",
): string {
    if (scored && isSelected && state === "correct") {
        return "border-emerald-200 bg-emerald-50";
    }
    if (scored && isSelected && state === "wrong") {
        return "border-red-200 bg-red-50";
    }
    if (isSelected) {
        return "border-violet-300 bg-violet-50";
    }
    return "border-slate-200 bg-white hover:border-violet-200 hover:bg-violet-50/60";
}

function CardBadge({ children }: { readonly children: string }) {
    return (
        <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-700">
            {children}
        </span>
    );
}
