"use client";

import type { ReactNode } from "react";
import { useId } from "react";

export interface ShortAnswerInteractionCardProps {
    readonly stem: string;
    readonly value: string;
    readonly onChange: (text: string) => void;
    readonly min_length?: number | null;
    readonly max_length?: number | null;
    readonly disabled?: boolean;
    readonly helperText?: string | null;
    readonly footer?: ReactNode;
}

/**
 * Whitelist renderer for a short-answer interaction.
 *
 * The textarea value is controlled by the parent; the only mutation surface
 * is onChange(text). Length bounds are exposed as read-only metadata and
 * also used to clamp and surface counters.
 */
export function ShortAnswerInteractionCard({
    stem,
    value,
    onChange,
    min_length = null,
    max_length = null,
    disabled = false,
    helperText = null,
    footer = null,
}: ShortAnswerInteractionCardProps) {
    const inputId = useId();
    const length = value.length;
    const minOk = min_length === null || length >= min_length;
    const maxOk = max_length === null || length <= max_length;

    const handleChange = (next: string) => {
        if (disabled) {
            return;
        }
        if (max_length !== null && next.length > max_length) {
            // Truncate to the maximum allowed length so we never let the
            // controlled value exceed the contract.
            onChange(next.slice(0, max_length));
            return;
        }
        onChange(next);
    };

    return (
        <section
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            data-interaction-type="short_answer"
        >
            <h3 className="text-base font-semibold text-slate-900">{stem}</h3>
            {helperText ? (
                <p className="mt-1 text-sm text-slate-500">{helperText}</p>
            ) : null}
            <label htmlFor={inputId} className="sr-only">
                {stem}
            </label>
            <textarea
                id={inputId}
                value={value}
                onChange={(event) => handleChange(event.target.value)}
                disabled={disabled}
                rows={4}
                className="mt-3 block w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 disabled:cursor-not-allowed disabled:bg-slate-50"
                placeholder="请输入你的回答"
            />
            <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                <span>
                    {min_length !== null ? `至少 ${min_length} 字` : ""}
                    {min_length !== null && max_length !== null ? " · " : ""}
                    {max_length !== null ? `最多 ${max_length} 字` : ""}
                </span>
                <span
                    className={
                        !minOk || !maxOk ? "text-rose-500" : "text-slate-400"
                    }
                >
                    {length}
                    {max_length !== null ? ` / ${max_length}` : ""}
                </span>
            </div>
            {footer ? <div className="mt-4">{footer}</div> : null}
        </section>
    );
}
