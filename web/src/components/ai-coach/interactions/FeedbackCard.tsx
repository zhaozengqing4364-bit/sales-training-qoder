"use client";

import type { ReactNode } from "react";

export interface FeedbackCardProps {
    readonly score: number;
    readonly max_score: number;
    readonly feedback: string;
    readonly missed_points?: readonly string[];
    readonly footer?: ReactNode;
}

function formatScore(score: number, maxScore: number): string {
    if (maxScore <= 0) {
        return `${score}`;
    }
    return `${score} / ${maxScore}`;
}

export function FeedbackCard({
    score,
    max_score,
    feedback,
    missed_points = [],
    footer = null,
}: FeedbackCardProps) {
    return (
        <section
            className="rounded-xl border border-slate-200 bg-slate-50 p-5 shadow-sm"
            data-component="ai-coach-feedback-card"
        >
            <header className="flex items-center justify-between">
                <h3 className="text-base font-semibold text-slate-900">
                    AI 教练反馈
                </h3>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                    {formatScore(score, max_score)}
                </span>
            </header>
            <p className="mt-3 text-sm leading-relaxed text-slate-700">
                {feedback}
            </p>
            {missed_points.length > 0 ? (
                <div className="mt-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        遗漏要点
                    </h4>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {missed_points.map((point, index) => (
                            <li key={`${index}-${point}`}>{point}</li>
                        ))}
                    </ul>
                </div>
            ) : null}
            {footer ? <div className="mt-4">{footer}</div> : null}
        </section>
    );
}
