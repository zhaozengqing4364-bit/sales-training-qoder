"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Circle, Lock, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { FoundationAdminLearnerDetail } from "@/lib/api/types/foundation-admin";

export default function NewcomerTrainingLearnerDetailPage() {
    const params = useParams();
    const learnerId = Array.isArray(params.learnerId) ? params.learnerId[0] : String(params.learnerId || "");
    const [detail, setDetail] = useState<FoundationAdminLearnerDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const load = useCallback(async () => { if (!learnerId) return; setLoading(true); setError(null); try { setDetail(await api.admin.newcomerTraining.getLearner(learnerId)); } catch (cause) { setError(getApiErrorMessage(cause)); } finally { setLoading(false); } }, [learnerId]);
    useEffect(() => { void load(); }, [load]);

    if (loading) return <main className="p-8 text-center text-sm text-slate-500">正在加载训练详情…</main>;
    if (error || !detail) return <main className="mx-auto max-w-3xl p-6"><div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><p>{error ?? "训练详情不可用"}</p><Button variant="outline" className="mt-3" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />重新加载</Button></div></main>;

    const journey = detail.journey;
    return <main className="min-h-screen bg-slate-50 p-4 md:p-6"><div className="mx-auto max-w-5xl space-y-5"><Link href="/admin/newcomer-training/learners" className="text-sm text-slate-600">← 返回学员进度</Link><header className="rounded-3xl bg-slate-900 p-6 text-white"><p className="text-sm text-blue-200">{detail.learner.name || "未命名学员"} · {detail.cohort.name}</p><h1 className="mt-1 text-2xl font-semibold">{journey.path?.title ?? "训练配置待处理"}</h1><p className="mt-2 text-sm text-slate-300">{journey.status_label}{journey.status_reason ? ` · ${journey.status_reason}` : ""}</p><div className="mt-5 flex items-center gap-4"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700"><div className="h-full bg-blue-400" style={{ width: `${journey.progress.percentage}%` }} /></div><strong>{journey.progress.percentage}%</strong></div></header><nav aria-label="相关训练记录" className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link href={`/admin/newcomer-training/cohorts/${encodeURIComponent(detail.cohort.cohort_id)}`}>查看所属班级</Link></Button><Button asChild variant="outline"><Link href="/admin/newcomer-training/reviews">进入达标复核</Link></Button></nav><div className="space-y-4">{journey.stages.map((stage) => <section key={stage.stage_id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex items-center justify-between border-b border-slate-100 p-5"><div><h2 className="font-semibold text-slate-900">{stage.title}</h2><p className="mt-1 text-sm text-slate-500">{stage.objective}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{stage.status === "completed" ? "已完成" : stage.status === "locked" ? "尚未解锁" : "当前阶段"}</span></div><ol className="space-y-2 p-5">{stage.activities.map((activity) => <li key={activity.activity_id} className="flex items-center gap-3 rounded-xl bg-slate-50 px-3 py-3">{activity.status === "completed" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : activity.status === "locked" ? <Lock className="h-4 w-4 text-slate-400" /> : <Circle className="h-4 w-4 text-blue-600" />}<span className="min-w-0 flex-1 text-sm font-medium text-slate-800">{activity.title}</span><span className="text-xs text-slate-500">{activity.status_label}</span><ChevronRight className="h-4 w-4 text-slate-300" /></li>)}</ol></section>)}</div></div></main>;
}
