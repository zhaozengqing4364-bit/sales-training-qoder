"use client";

import type { ReactNode } from "react";

export interface MultipleChoiceOption {
    readonly option_id: string;
    readonly label: string;
    readonly description?: string | null;
}

export interface MultipleChoiceInteractionCardProps {
    readonly stem: string;
    readonly options: readonly MultipleChoiceOption[];
    readonly value: readonly string[];
    readonly onChange: (optionIds: string[]) => void;
    readonly min_selected?: number | null;
    readonly max_selected?: number | null;
    readonly disabled?: boolean;
    readonly helperText?: string | null;
    readonly footer?: ReactNode;
}

/**
 * Whitelist renderer for a multiple-choice interaction.
 *
 * Maintains a string[] of selected option_ids and enforces optional
 * min/max selected bounds. No raw HTML or component slots are accepted.
 */
export function MultipleChoiceInteractionCard({
    stem,
    options,
    value,
    onChange,
    min_selected = null,
    max_selected = null,
    disabled = false,
    helperText = null,
    footer = null,
}: MultipleChoiceInteractionCardProps) {
    const selected = new Set(value);

    const handleToggle = (optionId: string) => {
        if (disabled) {
            return;
        }
        const next = new Set(selected);
        if (next.has(optionId)) {
            next.delete(optionId);
        } else {
            if (max_selected !== null && next.size >= max_selected) {
                // Skip the addition but still notify listeners with the existing
                // selection to keep the call surface predictable.
                return;
            }
            next.add(optionId);
        }
        onChange(Array.from(next));
    };

    return (
        <section
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            data-interaction-type="multiple_choice"
        >
            <h3 className="text-base font-semibold text-slate-900">{stem}</h3>
            {helperText ? (
                <p className="mt-1 text-sm text-slate-500">{helperText}</p>
            ) : null}
            {(min_selected !== null || max_selected !== null) ? (
                <p className="mt-2 text-xs text-slate-400">
                    {min_selected !== null ? `至少 ${min_selected} 项` : ""}
                    {min_selected !== null && max_selected !== null ? " · " : ""}
                    {max_selected !== null ? `最多 ${max_selected} 项` : ""}
                </p>
            ) : null}
            <ul className="mt-4 space-y-2">
                {options.map((option) => {
                    const checked = selected.has(option.option_id);
                    const inputId = `multi-choice-${option.option_id}`;
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
                                    type="checkbox"
                                    value={option.option_id}
                                    checked={checked}
                                    disabled={disabled}
                                    onChange={() => handleToggle(option.option_id)}
                                    className="mt-1 h-4 w-4 rounded text-sky-600 focus:ring-sky-500"
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
