import Link from "next/link";

import type { JourneyResponse } from "@/lib/api/types/newcomer-training";
import { missionFromJourney } from "@/lib/newcomer-training/learner-mission";
import { JourneyOutline } from "./journey-outline";
import { LearnerMissionCard } from "./learner-mission-card";

export function JourneyHome({ journey }: { journey: JourneyResponse }) {
    const current = journey.phases.find((phase) => !phase.completed && !phase.locked) ?? journey.phases.at(-1) ?? null;
    const mission = missionFromJourney(journey);
    return <main className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
        <div className="mx-auto max-w-5xl">
            <header className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div><p className="text-sm font-medium text-blue-700">你的学习任务</p><p className="mt-1 text-lg font-semibold text-slate-950">{journey.path_title}</p></div>
                <Link href="/history?source=newcomer-training" className="text-sm font-medium text-slate-600 underline-offset-4 hover:text-slate-950 hover:underline">查看训练记录</Link>
            </header>
            {mission
                ? <LearnerMissionCard mission={mission} actionHref={`/newcomer-training/activities/${encodeURIComponent(mission.activityId)}`} />
                : <section aria-live="polite" data-motion-kind="spatial" className="motion-completion-reveal rounded-3xl border border-emerald-200 bg-white p-7 shadow-sm"><p className="text-xl font-semibold text-emerald-950">当前训练已全部完成</p><p className="mt-2 text-sm text-slate-600">你可以在训练记录中查看成绩和反馈。</p></section>}
            <section className="mt-8">
                <div className="mb-4"><h2 className="text-lg font-semibold text-slate-950">完整训练安排</h2><p className="mt-1 text-sm text-slate-500">一次只需完成当前任务，后续内容会按顺序解锁。</p></div>
                <JourneyOutline phases={journey.phases} currentPhaseId={current?.phase_id ?? null} />
            </section>
        </div>
    </main>;
}
