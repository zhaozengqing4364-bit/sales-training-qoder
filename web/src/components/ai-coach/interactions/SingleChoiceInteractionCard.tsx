"use client";

import type { ReactNode } from "react";

export interface SingleChoiceOption {
    readonly option_id: string;
    readonly label: string;
    readonly description?: string | null;
}

export interface SingleChoiceInteractionCardProps {
    readonly stem: string;
    readonly options: readonly SingleChoiceOption[];
    readonly value: string | null;
    readonly onChange: (optionId: string) => void;
    readonly disabled?: boolean;
    readonly helperText?: string | null;
    readonly footer?: ReactNode;
}

/**
 * Whitelist renderer for a single-choice interaction.
 *
 * Props are explicit and typed — there is no `component` or `render` slot,
 * no LLM-supplied tree, and no Markdown/HTML passthrough. The user picks
 * one option_id and we call onChange(optionId).
 */
export function SingleChoiceInteractionCard({
    stem,
    options,
    value,
    onChange,
    disabled = false,
    helperText = null,
    footer = null,
}: SingleChoiceInteractionCardProps) {
    return (
        <section
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            data-interaction-type="single_choice"
        >
            <h3 className="text-base font-semibold text-slate-900">{stem}</h3>
            {helperText ? (
                <p className="mt-1 text-sm text-slate-500">{helperText}</p>
            ) : null}
            <ul className="mt-4 space-y-2" role="radiogroup" aria-label={stem}>
                {options.map((option) => {
                    const checked = value === option.option_id;
                    const inputId = `single-choice-${option.option_id}`;
                    return (
                        <li key={option.option_id}>
                            <label
                                htmlFor={inputId}
                                className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 transition-colors ${
                                    checked
                                        ? "border-sky-500 bg-sky-50"
                                        : "border-slate-200 bg-white hover:border-slate-300"
                                } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
                            >
                                <input
                                    id={inputId}
                                    type="radio"
                                    name="ai-coach-single-choice"
                                    value={option.option_id}
                                    checked={checked}
                                    disabled={disabled}
                                    onChange={() => onChange(option.option_id)}
                                    className="mt-1 h-4 w-4 text-sky-600 focus:ring-sky-500"
                                />
                                <span className="flex flex-col">
                                    <span className="text-sm font-medium text-slate-900">
                                        {option.label}
                                    </span>
                                    {option.description ? (
                                        <span className="text-xs text-slate-500">
                                            {option.description}
                                        </span>
                                    ) : null}
                                </span>
                            </label>
                        </li>
                    );
                })}
            </ul>
            {footer ? <div className="mt-4">{footer}</div> : null}
        </section>
    );
}
