import Link from "next/link";

import type { JourneyPageViewModel } from "@/lib/newcomer-training/view-models";
import { FoundationUxSignal } from "./foundation-ux-signal";
import { JourneyOutline } from "./journey-outline";
import { LearnerMissionCard } from "./learner-mission-card";

export function JourneyHome({ journey }: { journey: JourneyPageViewModel }) {
    const unavailable = journey.status === "not_enrolled" || journey.status === "blocked";
    return (
        <main className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
            <FoundationUxSignal event="journey_entered" />
            {journey.status === "awaiting_review" ? <FoundationUxSignal event="review_requested" dimension="review" /> : null}
            <div className="mx-auto max-w-5xl">
                <header className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div className="min-w-0">
                        <p className="text-sm font-medium text-blue-700">你的学习任务</p>
                        <p className="mt-1 break-words text-lg font-semibold text-slate-950">{journey.pathTitle}</p>
                        <p className="mt-1 text-sm text-slate-500">{journey.progressLabel}</p>
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm font-medium">
                        <Link href="/newcomer-training/dossier" className="text-blue-700 underline-offset-4 hover:underline">查看训练档案</Link>
                        <Link href="/newcomer-training/notifications" className="text-slate-600 underline-offset-4 hover:text-slate-950 hover:underline">查看通知与任务</Link>
                    </div>
                </header>

                {journey.dataFreshness === "stale" ? (
                    <div role="status" className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                        当前展示的是上次成功加载的训练进度。刷新后可获取最新结果。
                    </div>
                ) : null}

                {unavailable ? (
                    <section role="status" className="rounded-3xl border border-amber-200 bg-white p-7 shadow-sm">
                        <p className="text-xl font-semibold text-slate-950">{journey.statusLabel}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{journey.statusReason}</p>
                    </section>
                ) : journey.mission ? (
                    <LearnerMissionCard mission={journey.mission} actionHref={journey.missionHref ?? undefined} />
                ) : journey.status === "completed" ? (
                    <section aria-live="polite" data-motion-kind="spatial" className="motion-completion-reveal rounded-3xl border border-emerald-200 bg-white p-7 shadow-sm">
                        <p className="text-xl font-semibold text-emerald-950">当前训练已全部完成</p>
                        <p className="mt-2 text-sm text-slate-600">你可以在训练记录中查看成绩和反馈。</p>
                    </section>
                ) : (
                    <section role="status" className="rounded-3xl border border-blue-200 bg-white p-7 shadow-sm">
                        <p className="text-xl font-semibold text-slate-950">{journey.statusLabel}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{journey.statusReason ?? "结果更新后会在这里显示下一步。"}</p>
                    </section>
                )}

                {journey.stages.length > 0 ? (
                    <section className="mt-8">
                        <div className="mb-4">
                            <h2 className="text-lg font-semibold text-slate-950">完整训练安排</h2>
                            <p className="mt-1 text-sm text-slate-500">一次只需完成当前任务，后续内容会按顺序解锁。</p>
                        </div>
                        <JourneyOutline stages={journey.stages} currentStageId={journey.currentStageId} />
                    </section>
                ) : null}

                <section aria-labelledby="recent-progress-title" className="mt-8 rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="flex flex-wrap items-end justify-between gap-3">
                        <div>
                            <h2 id="recent-progress-title" className="font-semibold text-slate-950">最近进展</h2>
                            <p className="mt-1 text-sm text-slate-500">结果由训练记录提供，不在页面重新计算。</p>
                        </div>
                        <Link href="/history?source=newcomer-training" className="text-sm font-medium text-blue-700 underline-offset-4 hover:underline">查看全部训练记录</Link>
                    </div>
                    {journey.recentProgress.length === 0 ? (
                        <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">完成第一项训练后，进展和结果会保存在这里。</p>
                    ) : (
                        <ol className="mt-3 divide-y divide-slate-100">
                            {journey.recentProgress.map((item) => (
                                <li key={item.id}>
                                    <Link href={item.href} className="flex flex-col gap-1 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 sm:flex-row sm:items-center sm:justify-between">
                                        <span className="min-w-0">
                                            <span className="block break-words text-sm font-medium text-slate-900">{item.title}</span>
                                            <span className="mt-0.5 block text-xs text-slate-500">{new Date(item.producedAt).toLocaleString("zh-CN")}</span>
                                        </span>
                                        <span className="shrink-0 text-sm text-slate-700">{item.resultLabel}{item.scoreLabel ? ` · ${item.scoreLabel}` : ""}</span>
                                    </Link>
                                </li>
                            ))}
                        </ol>
                    )}
                </section>
            </div>
        </main>
    );
}
