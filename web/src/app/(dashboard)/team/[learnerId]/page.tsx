"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, CheckCircle2, Lock, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useTeamJourneyDetail } from "@/hooks/use-team-journey-detail";
import { getApiErrorMessage } from "@/lib/api/client";
import { activityStatusLabel, journeyRiskActivities } from "@/lib/team-journey/view-models";

export default function TeamLearnerDetailPage() {
    const { learnerId } = useParams<{ learnerId: string }>();
    const state = useTeamJourneyDetail({ learnerId });
    if (state.isLoading) return <Skeleton className="h-72 rounded-3xl" />;
    if (state.isError || !state.journey) return <EmptyState title="学员训练记录不存在或无权查看" description={state.error ? getApiErrorMessage(state.error) : "请返回团队列表重试。"} actionLabel="重新加载" onAction={() => void state.refetch()} />;
    const journey = state.journey;
    const risks = journeyRiskActivities(journey);
    return <main className="space-y-6 pb-20"><Link href="/team" className="text-sm text-slate-600">← 返回团队</Link><header className="rounded-3xl bg-white p-6 shadow-sm"><p className="text-sm text-blue-700">新人训练路径</p><h1 className="mt-1 text-2xl font-semibold text-slate-900">{journey.path_title}</h1><div className="mt-4 flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-blue-600" style={{ width: `${journey.progress.percent}%` }} /></div><span className="text-sm text-slate-600">{journey.progress.completed_count}/{journey.progress.total_required}</span></div>{risks.length > 0 && <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="mr-2 inline h-4 w-4" />需要辅导：{risks.slice(0, 3).map((item) => item.title).join("、")}</div>}</header>{journey.phases.map((phase) => <section key={phase.phase_id} className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold text-slate-900">{phase.title}</h2><div className="mt-4 space-y-4">{phase.modules.map((moduleConfig) => <div key={moduleConfig.module_id}><h3 className="text-sm font-medium text-slate-700">{moduleConfig.title}</h3><ul className="mt-2 space-y-2">{moduleConfig.activities.map((activity) => <li key={activity.activity_id} className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm">{activity.completed ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : activity.locked ? <Lock className="h-4 w-4 text-slate-400" /> : <span className="h-2 w-2 rounded-full bg-blue-600" />}<span className="flex-1 text-slate-800">{activity.title}</span><span className="text-slate-500">{activityStatusLabel(activity)}</span>{typeof activity.score === "number" && <span className="font-medium text-slate-700">{activity.score}{typeof activity.max_score === "number" ? `/${activity.max_score}` : ""}</span>}</li>)}</ul></div>)}</div></section>)}<Button variant="outline" onClick={() => void state.refetch()}><RefreshCw className="mr-2 h-4 w-4" />刷新</Button></main>;
}
