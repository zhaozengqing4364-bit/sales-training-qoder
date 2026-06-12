"use client";

import type { ReactNode } from "react";

export interface MasteryResultCardProps {
    readonly overall_mastered: boolean;
    readonly total_score: number;
    readonly max_score: number;
    readonly onRetry?: (() => void) | null;
    readonly onBack?: (() => void) | null;
    readonly summary?: string | null;
    readonly footer?: ReactNode;
}

function formatScore(score: number, maxScore: number): string {
    if (maxScore <= 0) {
        return `${score}`;
    }
    const ratio = score / maxScore;
    return `${score} / ${maxScore}（${Math.round(ratio * 100)}%）`;
}

/**
 * Whitelist renderer for the final mastery verdict at the end of a session.
 *
 * Renders a summary card with overall mastery flag, totals, and a small
 * button group composed only of typed callbacks (onRetry, onBack).
 */
export function MasteryResultCard({
    overall_mastered,
    total_score,
    max_score,
    onRetry = null,
    onBack = null,
    summary = null,
    footer = null,
}: MasteryResultCardProps) {
    return (
        <section
            className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
            data-component="ai-coach-mastery-result-card"
        >
            <header className="flex items-start justify-between gap-4">
                <div>
                    <h3 className="text-lg font-semibold text-slate-900">
                        {overall_mastered ? "本节已掌握" : "本节未达标"}
                    </h3>
                    {summary ? (
                        <p className="mt-1 text-sm text-slate-600">{summary}</p>
                    ) : (
                        <p className="mt-1 text-sm text-slate-600">
                            {overall_mastered
                                ? "你已通过本节训练，可以进入下一关卡。"
                                : "建议再次练习本节内容，巩固薄弱要点。"}
                        </p>
                    )}
                </div>
                <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                        overall_mastered
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-rose-100 text-rose-700"
                    }`}
                >
                    {overall_mastered ? "Mastered" : "Not Mastered"}
                </span>
            </header>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                    <dt className="text-xs text-slate-500">本节总分</dt>
                    <dd className="mt-1 text-base font-semibold text-slate-900">
                        {formatScore(total_score, max_score)}
                    </dd>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                    <dt className="text-xs text-slate-500">结果</dt>
                    <dd className="mt-1 text-base font-semibold text-slate-900">
                        {overall_mastered ? "已通过" : "待复盘"}
                    </dd>
                </div>
            </dl>
            {(onRetry || onBack) ? (
                <div className="mt-5 flex flex-wrap gap-2">
                    {onRetry ? (
                        <button
                            type="button"
                            onClick={onRetry}
                            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-sky-700"
                        >
                            再次练习
                        </button>
                    ) : null}
                    {onBack ? (
                        <button
                            type="button"
                            onClick={onBack}
                            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                        >
                            返回路径
                        </button>
                    ) : null}
                </div>
            ) : null}
            {footer ? <div className="mt-4">{footer}</div> : null}
        </section>
    );
}
