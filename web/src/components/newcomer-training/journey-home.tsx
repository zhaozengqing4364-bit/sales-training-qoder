import Link from "next/link";
import { ArrowRight, Clock3 } from "lucide-react";

import type { JourneyResponse } from "@/lib/api/types/newcomer-training";
import { JourneyOutline } from "./journey-outline";

export function JourneyHome({ journey }: { journey: JourneyResponse }) {
    const current = journey.phases.find((phase) => !phase.completed && !phase.locked) ?? journey.phases.at(-1) ?? null;
    const next = journey.primary_next_action;
    const nextActivity = journey.phases.flatMap((phase) => phase.modules).flatMap((moduleConfig) => moduleConfig.activities).find((activity) => activity.activity_id === next?.activity_id);
    return <main className="mx-auto min-h-screen max-w-5xl bg-slate-50 px-4 py-8 md:px-6">
        <header className="rounded-3xl bg-slate-900 p-6 text-white shadow-xl md:p-8"><p className="text-sm font-medium text-blue-200">{current ? `当前阶段：${current.title}` : "训练路径"}</p><h1 className="mt-2 text-3xl font-semibold">{journey.path_title}</h1><div className="mt-6 grid gap-4 md:grid-cols-[1fr_auto]"><div><div className="flex items-center justify-between text-sm text-slate-300"><span>整体进度</span><span>{Math.round(journey.progress.percent)}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-700"><div className="h-full rounded-full bg-blue-400" style={{ width: `${Math.min(100, Math.max(0, journey.progress.percent))}%` }} /></div></div><div className="flex items-center gap-2 text-sm text-slate-300"><Clock3 className="h-4 w-4" />{nextActivity ? "完成当前任务后自动解锁下一步" : "训练任务已完成"}</div></div>
        {next ? <div className="mt-6 rounded-2xl bg-white p-5 text-slate-900"><p className="text-xs font-semibold uppercase tracking-wide text-slate-400">当前任务</p><p className="mt-1 text-lg font-semibold">{nextActivity?.title ?? next.label}</p><Link data-primary-action="true" href={`/newcomer-training/activities/${encodeURIComponent(next.activity_id)}`} className="mt-4 inline-flex h-11 items-center rounded-full bg-blue-600 px-6 text-sm font-semibold text-white shadow hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">继续学习<ArrowRight className="ml-2 h-4 w-4" /></Link></div> : <div className="mt-6 rounded-2xl bg-emerald-50 p-5 text-emerald-900"><p className="font-semibold">当前训练已全部完成</p><p className="mt-1 text-sm">你可以在训练记录中查看成绩和反馈。</p></div>}</header>
        <div className="mt-8"><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold text-slate-900">训练路径</h2><Link href="/history?source=newcomer-training" className="text-sm font-medium text-slate-600 hover:text-slate-900">查看训练记录</Link></div><JourneyOutline phases={journey.phases} /></div>
    </main>;
}
