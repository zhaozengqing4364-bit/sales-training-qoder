"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Circle, Lock, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { JourneyResponse } from "@/lib/api/types/newcomer-training";
import { activityStatusLabel } from "@/lib/newcomer-training/presentation";

export default function NewcomerTrainingLearnerDetailPage() {
    const params = useParams();
    const learnerId = Array.isArray(params.learnerId) ? params.learnerId[0] : String(params.learnerId || "");
    const [journey, setJourney] = useState<JourneyResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const load = useCallback(async () => { if (!learnerId) return; setLoading(true); setError(null); try { setJourney(await api.admin.newcomerTraining.getLearnerJourney(learnerId)); } catch (cause) { setError(getApiErrorMessage(cause)); } finally { setLoading(false); } }, [learnerId]);
    useEffect(() => { void load(); }, [load]);

    if (loading) return <main className="p-8 text-center text-sm text-slate-500">正在加载训练详情…</main>;
    if (error || !journey) return <main className="mx-auto max-w-3xl p-6"><div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><p>{error ?? "训练详情不可用"}</p><Button variant="outline" className="mt-3" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />重新加载</Button></div></main>;

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6"><div className="mx-auto max-w-5xl space-y-5"><Link href="/admin/newcomer-training/learners" className="text-sm text-slate-600">← 返回学员进度</Link><header className="rounded-3xl bg-slate-900 p-6 text-white"><p className="text-sm text-blue-200">学员训练详情</p><h1 className="mt-1 text-2xl font-semibold">{journey.path_title}</h1><div className="mt-5 flex items-center gap-4"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700"><div className="h-full bg-blue-400" style={{ width: `${journey.progress.percent}%` }} /></div><strong>{Math.round(journey.progress.percent)}%</strong></div></header><nav aria-label="相关训练记录" className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link href={`/admin/sales-trainer/training-records?learner_id=${encodeURIComponent(learnerId)}`}>查看训练记录</Link></Button><Button asChild variant="outline"><Link href={`/admin/sales-trainer/audio-submissions?learner_id=${encodeURIComponent(learnerId)}`}>查看录音</Link></Button><Button asChild variant="outline"><Link href={`/admin/sales-trainer/readiness/${encodeURIComponent(learnerId)}`}>达标验收</Link></Button></nav><div className="space-y-4">{journey.phases.map((phase) => <section key={phase.phase_id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-semibold text-slate-900">{phase.title}</h2><p className="mt-1 text-sm text-slate-500">已完成 {phase.completed_count}/{phase.total_required}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{phase.completed ? "已完成" : phase.locked ? "未解锁" : "进行中"}</span></div><div className="divide-y divide-slate-100">{phase.modules.map((moduleConfig) => <div key={moduleConfig.module_id} className="p-5"><div className="flex items-center justify-between"><h3 className="font-medium text-slate-900">{moduleConfig.title}</h3><span className="text-sm text-slate-500">{Math.round(moduleConfig.percent)}%</span></div><ol className="mt-3 space-y-2">{moduleConfig.activities.map((activity) => <li key={activity.activity_id} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3">{activity.completed ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : activity.locked ? <Lock className="h-4 w-4 text-slate-400" /> : <Circle className="h-4 w-4 text-blue-600" />}<span className="min-w-0 flex-1 text-sm font-medium text-slate-800">{activity.title}</span><span className="text-xs text-slate-500">{activityStatusLabel(activity)}</span><ChevronRight className="h-4 w-4 text-slate-300" /></li>)}</ol></div>)}</div></section>)}</div></div></main>;
}
