import Link from "next/link";
import { ArrowRight, CheckCircle2, Clock3, Lightbulb, Route } from "lucide-react";

import type { LearnerMissionViewModel } from "@/lib/newcomer-training/learner-mission";

export function LearnerMissionCard({
    mission,
    actionHref,
    preview = false,
}: {
    mission: LearnerMissionViewModel;
    actionHref?: string;
    preview?: boolean;
}) {
    const actionClass = "inline-flex h-12 w-full items-center justify-center rounded-xl bg-blue-600 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 sm:w-auto";
    return <article className="flex flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="order-1 border-b border-slate-100 px-5 py-5 sm:px-7">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
                <span className="rounded-full bg-blue-50 px-3 py-1 font-medium text-blue-700">{preview ? "新学员预览" : "当前任务"}</span>
                <span>{mission.phaseLabel}</span><span aria-hidden="true">·</span><span>{mission.moduleLabel}</span>
            </div>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{mission.title}</h1>
            <p className="mt-2 max-w-3xl text-base leading-7 text-slate-600">{mission.objective}</p>
            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500">
                {mission.estimatedMinutes ? <span className="inline-flex items-center gap-1.5"><Clock3 className="h-4 w-4" />预计 {mission.estimatedMinutes} 分钟</span> : null}
                <span className="inline-flex items-center gap-1.5"><Route className="h-4 w-4" />整体进度 {Math.round(mission.progressPercent)}%</span>
            </div>
        </div>

        <div className="order-3 grid gap-6 px-5 py-6 sm:px-7 lg:order-2 lg:grid-cols-[minmax(0,1.25fr)_minmax(260px,0.75fr)]">
            <div>
                <div className="flex items-start gap-3 rounded-2xl bg-amber-50 px-4 py-3.5 text-amber-950">
                    <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                    <div><h2 className="text-sm font-semibold">为什么要做</h2><p className="mt-1 text-sm leading-6 text-amber-900/80">{mission.whyItMatters}</p></div>
                </div>
                <h2 className="mt-6 text-sm font-semibold text-slate-900">完成步骤</h2>
                <ol className="mt-3 grid gap-3 sm:grid-cols-3">
                    {mission.steps.map((step, index) => <li key={`${index}-${step}`} className="flex gap-3 rounded-2xl border border-slate-200 p-3.5 text-sm leading-6 text-slate-700">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">{index + 1}</span>
                        <span>{step}</span>
                    </li>)}
                </ol>
            </div>

            <aside className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-4">
                <h2 className="text-sm font-semibold text-emerald-950">怎样算完成</h2>
                <ul className="mt-3 space-y-3">
                    {mission.successCriteria.map((criterion) => <li key={criterion} className="flex gap-2 text-sm leading-6 text-emerald-900">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /><span>{criterion}</span>
                    </li>)}
                </ul>
            </aside>
        </div>

        <div className="order-2 flex flex-col gap-3 border-b border-slate-100 bg-slate-50/70 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-7 lg:order-3 lg:border-b-0 lg:border-t">
            <p className="hidden text-sm text-slate-500 sm:block">完成后，系统会自动带你进入下一项任务。</p>
            {actionHref
                ? <Link data-primary-action="true" href={actionHref} className={actionClass}>{mission.actionLabel}<ArrowRight className="ml-2 h-4 w-4" /></Link>
                : <span aria-disabled="true" className={`${actionClass} cursor-default opacity-80`}>{mission.actionLabel}<ArrowRight className="ml-2 h-4 w-4" /></span>}
        </div>
    </article>;
}
