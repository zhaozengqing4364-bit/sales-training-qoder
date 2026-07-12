"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, ChevronDown, Lock } from "lucide-react";

import type { JourneyPhaseProgress } from "@/lib/api/types/newcomer-training";
import { activityStatusLabel, progressLabel } from "@/lib/newcomer-training/presentation";

export function JourneyOutline({ phases, currentPhaseId }: { phases: JourneyPhaseProgress[]; currentPhaseId?: string | null }) {
    const resolvedCurrentPhaseId = currentPhaseId ?? phases.find((phase) => !phase.completed && !phase.locked)?.phase_id ?? null;
    const [expanded, setExpanded] = useState<Record<string, boolean>>(() => Object.fromEntries(phases.map((phase) => [phase.phase_id, phase.phase_id === resolvedCurrentPhaseId])));
    return <section aria-label="训练路径进度" className="space-y-3">
        {phases.map((phase) => {
            const open = expanded[phase.phase_id] ?? false;
            const stateLabel = phase.completed ? "已完成" : phase.locked ? "未解锁" : phase.phase_id === resolvedCurrentPhaseId ? "当前" : "待开始";
            return <div key={phase.phase_id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <button type="button" aria-expanded={open} aria-label={`${phase.title} ${stateLabel}`} onClick={() => setExpanded((current) => ({ ...current, [phase.phase_id]: !open }))} className="flex w-full items-center gap-3 px-5 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500">
                    {phase.completed ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : phase.locked ? <Lock className="h-5 w-5 text-slate-400" /> : <span className="h-3 w-3 rounded-full bg-blue-600 ring-4 ring-blue-100" />}
                    <span className="min-w-0 flex-1"><span className="block font-semibold text-slate-900">{phase.outcome || phase.title}</span><span className="mt-0.5 block text-sm text-slate-500">{phase.outcome ? `${phase.title} · ` : ""}{phase.locked ? phase.lock_reason : progressLabel(phase.completed_count, phase.total_required)}</span></span>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{stateLabel}</span><ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
                </button>
                {open && <div className="border-t border-slate-100 px-4 py-3 sm:px-5"><ol className="space-y-2">{phase.modules.map((moduleConfig) => <li key={moduleConfig.module_id}><Link href={`/newcomer-training/modules/${encodeURIComponent(moduleConfig.module_id)}`} className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"><span className="min-w-0"><span className="block text-sm font-medium text-slate-800">{moduleConfig.outcome || moduleConfig.title}</span><span className="mt-0.5 block text-xs text-slate-500">{moduleConfig.outcome ? `${moduleConfig.title} · ` : ""}{moduleConfig.locked ? moduleConfig.lock_reason : `${moduleConfig.completed_count}/${moduleConfig.total_required} 个必修活动`}</span></span><span className="shrink-0 text-xs text-slate-500">{moduleConfig.activities.find((item) => !item.completed)?.locked ? "等待解锁" : activityStatusLabel(moduleConfig.activities.find((item) => !item.completed) ?? moduleConfig.activities.at(-1)!)}</span></Link></li>)}</ol></div>}
            </div>;
        })}
    </section>;
}
