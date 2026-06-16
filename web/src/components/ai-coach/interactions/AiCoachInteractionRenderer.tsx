"use client";

import type { ReactNode } from "react";

import type {
    AiCoachAnswerPayloadV1,
    AiCoachInteractionPublicV1,
} from "@/lib/api/types";

import { MultipleChoiceInteractionCard } from "./MultipleChoiceInteractionCard";
import type { MultipleChoiceOption } from "./MultipleChoiceInteractionCard";
import { ShortAnswerInteractionCard } from "./ShortAnswerInteractionCard";
import { SingleChoiceInteractionCard } from "./SingleChoiceInteractionCard";
import type { SingleChoiceOption } from "./SingleChoiceInteractionCard";

/**
 * Whitelist renderer entry point.
 *
 * Dispatches on `interaction_type` to one of the static, well-typed
 * interaction cards. It does NOT accept arbitrary React components, raw
 * HTML, Markdown, or any LLM-supplied executable structure. The only
 * way to render a turn is through the small set of components in
 * `interactions/`.
 */

export interface AiCoachInteractionRendererProps {
    readonly interaction: AiCoachInteractionPublicV1;
    readonly value: AiCoachAnswerPayloadV1 | null;
    readonly onChange: (payload: AiCoachAnswerPayloadV1) => void;
    readonly disabled?: boolean;
    readonly helperText?: string | null;
    readonly footer?: ReactNode;
}

function readMinMax(
    constraints: Record<string, number> | undefined,
    key: "min_selected" | "max_selected" | "min_length" | "max_length",
): number | null {
    if (!constraints) {
        return null;
    }
    const raw = constraints[key];
    return typeof raw === "number" ? raw : null;
}

function toSingleOptions(
    options: AiCoachInteractionPublicV1["options"],
): SingleChoiceOption[] {
    if (!options) {
        return [];
    }
    return options.map((option) => ({
        option_id: option.option_id,
        label: option.text,
        // Public option contract intentionally omits ``is_distractor``
        // — exposing the distractor flag would let the learner defeat
        // the question by always picking the option whose flag is false.
        description: null,
    }));
}

function toMultipleOptions(
    options: AiCoachInteractionPublicV1["options"],
): MultipleChoiceOption[] {
    return toSingleOptions(options);
}

function getSingleValue(payload: AiCoachAnswerPayloadV1 | null): string | null {
    if (!payload || payload.variant !== "choice") {
        return null;
    }
    const first = payload.option_ids?.[0];
    return first ?? null;
}

function getMultiValue(payload: AiCoachAnswerPayloadV1 | null): string[] {
    if (!payload || payload.variant !== "choice") {
        return [];
    }
    return [...(payload.option_ids ?? [])];
}

function getTextValue(payload: AiCoachAnswerPayloadV1 | null): string {
    if (!payload || payload.variant !== "text") {
        return "";
    }
    return payload.text ?? "";
}

function trainingCardHelper(interaction: AiCoachInteractionPublicV1): string {
    switch (interaction.training_card_type ?? "scenario_judgment") {
        case "expression_rewrite":
            return "改写卡：把不专业表达改成更合适的商务表达。";
        case "role_response":
            return "角色回应卡：根据对方话术写出你的回应。";
        case "scenario_judgment":
        default:
            return "场景判断卡：判断当前做法是否符合商务礼仪。";
    }
}

export function AiCoachInteractionRenderer({
    interaction,
    value,
    onChange,
    disabled = false,
    helperText = null,
    footer = null,
}: AiCoachInteractionRendererProps) {
    const resolvedHelperText = helperText ?? trainingCardHelper(interaction);
    switch (interaction.interaction_type) {
        case "single_choice": {
            const options = toSingleOptions(interaction.options);
            const current = getSingleValue(value);
            return (
                <SingleChoiceInteractionCard
                    stem={interaction.stem}
                    options={options}
                    value={current}
                    disabled={disabled}
                    helperText={resolvedHelperText}
                    footer={footer}
                    onChange={(optionId) =>
                        onChange({
                            variant: "choice",
                            option_ids: [optionId],
                        })
                    }
                />
            );
        }
        case "multiple_choice": {
            const options = toMultipleOptions(interaction.options);
            const current = getMultiValue(value);
            return (
                <MultipleChoiceInteractionCard
                    stem={interaction.stem}
                    options={options}
                    value={current}
                    min_selected={readMinMax(
                        interaction.answer_constraints,
                        "min_selected",
                    )}
                    max_selected={readMinMax(
                        interaction.answer_constraints,
                        "max_selected",
                    )}
                    disabled={disabled}
                    helperText={resolvedHelperText}
                    footer={footer}
                    onChange={(optionIds) =>
                        onChange({
                            variant: "choice",
                            option_ids: optionIds,
                        })
                    }
                />
            );
        }
        case "short_answer": {
            const current = getTextValue(value);
            return (
                <ShortAnswerInteractionCard
                    stem={interaction.stem}
                    value={current}
                    min_length={readMinMax(
                        interaction.answer_constraints,
                        "min_length",
                    )}
                    max_length={readMinMax(
                        interaction.answer_constraints,
                        "max_length",
                    )}
                    disabled={disabled}
                    helperText={resolvedHelperText}
                    footer={footer}
                    onChange={(text) =>
                        onChange({
                            variant: "text",
                            text,
                        })
                    }
                />
            );
        }
        default: {
            // Exhaustiveness guard: this branch is unreachable when the
            // union of `interaction_type` literal types is updated, but we
            // still surface a safe placeholder so the UI never breaks.
            const exhaustive: never = interaction.interaction_type;
            return (
                <section
                    className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
                    data-component="ai-coach-unsupported-interaction"
                >
                    不支持的交互类型：
                    <code className="ml-1 rounded bg-rose-100 px-1 py-0.5">
                        {String(exhaustive)}
                    </code>
                </section>
            );
        }
    }
}
