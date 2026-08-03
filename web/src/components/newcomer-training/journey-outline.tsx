"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, ChevronDown, Lock } from "lucide-react";

import type {
    JourneyActivityViewModel,
    JourneyStageViewModel,
} from "@/lib/newcomer-training/view-models";

export function JourneyOutline({
    stages,
    currentStageId,
}: {
    stages: JourneyStageViewModel[];
    currentStageId?: string | null;
}) {
    const resolvedCurrentStageId = currentStageId
        ?? stages.find((stage) => stage.status === "current")?.id
        ?? null;
    const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
        Object.fromEntries(stages.map((stage) => [stage.id, stage.id === resolvedCurrentStageId])),
    );
    const reduceMotion = useReducedMotion();
    const hiddenTransform = reduceMotion ? "translate3d(0,0,0)" : "translate3d(0,-8px,0)";

    return (
        <section aria-label="训练路径进度" className="space-y-3">
            {stages.map((stage) => {
                const open = expanded[stage.id] ?? false;
                return (
                    <div key={stage.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                        <button
                            type="button"
                            aria-expanded={open}
                            aria-label={`${stage.title} ${stage.statusLabel}`}
                            onClick={() => setExpanded((current) => ({ ...current, [stage.id]: !open }))}
                            className="flex w-full items-center gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500"
                        >
                            {stage.status === "completed" ? <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-emerald-600" /> : stage.status === "locked" ? <Lock aria-hidden="true" className="h-5 w-5 text-slate-400" /> : <span aria-hidden="true" className="h-3 w-3 rounded-full bg-blue-600 ring-4 ring-blue-100" />}
                            <span className="min-w-0 flex-1">
                                <span className="block break-words font-semibold text-slate-900">{stage.objective || stage.title}</span>
                                <span className="mt-0.5 block break-words text-sm text-slate-500">{stage.objective ? `${stage.title} · ` : ""}{stage.completedCount}/{stage.totalCount} 个活动已完成</span>
                            </span>
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{stage.statusLabel}</span>
                            <span data-chevron-motion aria-hidden="true" className={`text-slate-400 transition-transform duration-[var(--duration-popover)] ease-[var(--ease-out)] motion-reduce:transform-none ${open ? "rotate-180" : ""}`}><ChevronDown className="h-4 w-4" /></span>
                        </button>
                        <AnimatePresence initial={false}>
                            {open ? (
                                <motion.div
                                    key={`${stage.id}-content`}
                                    initial={{ opacity: 0, transform: hiddenTransform }}
                                    animate={{ opacity: 1, transform: "translate3d(0,0,0)" }}
                                    exit={{ opacity: 0, transform: hiddenTransform }}
                                    transition={{ duration: reduceMotion ? 0.16 : 0.2, ease: [0.23, 1, 0.32, 1] }}
                                    data-motion-kind="spatial"
                                    className="border-t border-slate-100 px-4 py-3 sm:px-5"
                                >
                                    <ol className="space-y-2">
                                        {stage.activities.map((activity) => (
                                            <li key={activity.id}>
                                                {activity.href === null ? (
                                                    <div aria-label={`${activity.title} ${activity.statusLabel}`} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-slate-500"><ActivitySummary activity={activity} /><Lock aria-hidden="true" className="h-4 w-4 shrink-0" /></div>
                                                ) : (
                                                    <Link href={activity.href} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"><ActivitySummary activity={activity} /><span className="shrink-0 text-xs text-slate-500">{activity.statusLabel}</span></Link>
                                                )}
                                            </li>
                                        ))}
                                    </ol>
                                </motion.div>
                            ) : null}
                        </AnimatePresence>
                    </div>
                );
            })}
        </section>
    );
}

function ActivitySummary({ activity }: { activity: JourneyActivityViewModel }) {
    return (
        <span className="min-w-0">
            <span className="block break-words text-sm font-medium text-slate-800">{activity.title}</span>
            <span className="mt-0.5 block break-words text-xs text-slate-500">{activity.objective}{activity.estimatedMinutes > 0 ? ` · 约 ${activity.estimatedMinutes} 分钟` : ""}</span>
        </span>
    );
}
