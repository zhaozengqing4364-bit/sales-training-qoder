"use client";

import type { ComponentType } from "react";
import Link from "next/link";
import { CheckCircle2, Clock3, Lightbulb } from "lucide-react";

import type { FoundationActivityViewModel } from "@/lib/newcomer-training/view-models";
import { ActivityResultPanel } from "./activity-result-panel";
import { AssignmentRunner } from "./activity-runners/assignment-runner";
import { AudioAssessmentRunner } from "./activity-runners/audio-assessment-runner";
import { CoachRunner } from "./activity-runners/coach-runner";
import { LessonRunner } from "./activity-runners/lesson-runner";
import { QuizRunner } from "./activity-runners/quiz-runner";
import type { ActivityRunnerProps } from "./activity-runners/types";

export const ACTIVITY_RUNNERS: Record<
    FoundationActivityViewModel["activity"]["type"],
    ComponentType<ActivityRunnerProps>
> = {
    lesson: LessonRunner,
    quiz: QuizRunner,
    audio_assessment: AudioAssessmentRunner,
    ai_coach: CoachRunner,
    assignment: AssignmentRunner,
};

export function ActivityShell({ detail, onRefresh }: ActivityRunnerProps) {
    const Runner = ACTIVITY_RUNNERS[detail.activity.type];
    return <main className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
        <div className="mx-auto max-w-4xl">
            <Link href="/newcomer-training" className="text-sm font-medium text-slate-600 underline-offset-4 hover:text-slate-950 hover:underline">← 返回训练路径</Link>
            <article className="mt-4 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
                <header className="border-b border-slate-100 px-5 py-6 md:px-8">
                    <div className="flex flex-wrap items-center gap-3">
                        <p className="text-sm font-medium text-blue-700">当前任务</p>
                        {detail.activity.estimated_minutes ? <span className="inline-flex items-center gap-1.5 text-sm text-slate-500"><Clock3 className="h-4 w-4" />预计 {detail.activity.estimated_minutes} 分钟</span> : null}
                    </div>
                    <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">{detail.activity.title}</h1>
                    <p className="mt-2 max-w-3xl leading-7 text-slate-600">{detail.activity.objective}</p>
                </header>

                <section aria-label="任务说明" className="grid gap-5 border-b border-slate-100 bg-slate-50/60 px-5 py-5 md:grid-cols-[minmax(0,1fr)_minmax(240px,0.65fr)] md:px-8">
                    <div>
                        <div className="flex gap-3 rounded-2xl bg-amber-50 p-4 text-amber-950">
                            <Lightbulb className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                            <div><h2 className="text-sm font-semibold">为什么要做</h2><p className="mt-1 text-sm leading-6 text-amber-900/80">{detail.activity.why_it_matters}</p></div>
                        </div>
                        <h2 className="mt-5 text-sm font-semibold text-slate-900">怎么完成</h2>
                        <ol className="mt-3 grid gap-2 sm:grid-cols-3">{detail.activity.steps.map((step, index) => <li key={`${index}-${step}`} className="flex gap-2 rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-700"><span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">{index + 1}</span><span>{step}</span></li>)}</ol>
                    </div>
                    <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
                        <h2 className="text-sm font-semibold text-emerald-950">完成标准</h2>
                        <ul className="mt-3 space-y-2">{detail.activity.success_criteria.map((criterion) => <li key={criterion} className="flex gap-2 text-sm leading-6 text-emerald-900"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />{criterion}</li>)}</ul>
                    </div>
                </section>

                <div className="px-5 py-6 md:px-8">
                    <div className="space-y-5">
                        {detail.display.has_result ? <ActivityResultPanel detail={detail} /> : null}
                        {!detail.display.result_only || detail.display.keeps_runner_visible ? <Runner detail={detail} onRefresh={onRefresh} /> : null}
                    </div>
                </div>
            </article>
        </div>
    </main>;
}
