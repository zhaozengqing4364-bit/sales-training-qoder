"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Lock, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { TeamWorkbenchMemberResponse } from "@/lib/api/types";
import type { FoundationAdminLearnerDetail } from "@/lib/api/types/foundation-admin";
import { activityStatusLabel, journeyRiskActivities } from "@/lib/team-journey/view-models";

function taskStatus(status: string) {
    return ({ assigned: "待开始", in_progress: "进行中", completed: "已完成", expired: "已逾期", cancelled: "已取消" } as Record<string, string>)[status] ?? "状态待确认";
}

function selectedRange(params: URLSearchParams) {
    const range = params.get("range") ?? "30";
    const end = params.get("to") ? new Date(`${params.get("to")}T23:59:59+08:00`) : new Date();
    const start = range === "custom" && params.get("from")
        ? new Date(`${params.get("from")}T00:00:00+08:00`)
        : new Date(end.getTime() - (Number(range) - 1) * 86_400_000);
    return { date_from: start.toISOString(), date_to: end.toISOString() };
}

export default function TeamLearnerDetailPage() {
    const { learnerId } = useParams<{ learnerId: string }>();
    const searchParams = useSearchParams();
    const [learner, setLearner] = useState<FoundationAdminLearnerDetail | null>(null);
    const [detail, setDetail] = useState<TeamWorkbenchMemberResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try {
            const [learnerResult, detailResult] = await Promise.all([
                api.admin.newcomerTraining.getLearner(learnerId),
                api.supervisor.getTeamWorkbenchMember(learnerId, selectedRange(searchParams)),
            ]);
            setLearner(learnerResult); setDetail(detailResult);
        } catch (reason) { setError(getApiErrorMessage(reason)); }
        finally { setLoading(false); }
    }, [learnerId, searchParams]);
    useEffect(() => { void load(); }, [load]);
    if (loading) return <Skeleton className="h-72 rounded-3xl" />;
    if (error || !learner) return <EmptyState title="学员训练记录不存在或无权查看" description={error ?? "请返回团队列表重试。"} actionLabel="重新加载" onAction={() => void load()} />;
    const journey = learner.journey;
    const risks = journeyRiskActivities(journey);
    return <main className="space-y-6 pb-20">
        <Link href={`/team?${searchParams.toString()}`} className="text-sm font-medium text-slate-600">← 返回团队工作台</Link>
        <header className="rounded-2xl border border-slate-200 bg-white p-6"><p className="text-sm text-blue-700">成员只读档案</p><h1 className="mt-1 text-2xl font-semibold text-slate-900">{detail?.learner_name ?? "学员训练详情"}</h1><p className="mt-1 text-sm text-slate-500">路径结果和管理员额外分配任务分别展示；销售组长不能修改或发布任务。</p></header>
        <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="path-title"><div className="flex items-start justify-between"><div><p className="text-sm text-blue-700">新人训练路径</p><h2 id="path-title" className="mt-1 text-xl font-semibold text-slate-900">{journey.path?.title ?? "训练配置待处理"}</h2><p className="mt-1 text-sm text-slate-500">{journey.status_label}</p></div><strong className="text-lg text-slate-900">{journey.progress.completed_required}/{journey.progress.total_required}</strong></div><div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-blue-600" style={{ width: `${journey.progress.percentage}%` }} /></div>{risks.length ? <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="mr-2 inline h-4 w-4" />确定性风险：{risks.slice(0, 3).map((item) => `${item.title}需要处理`).join("、")}</div> : null}</section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5" aria-labelledby="extra-title"><div className="flex items-end justify-between"><div><p className="text-sm text-violet-700">管理员额外分配</p><h2 id="extra-title" className="mt-1 text-xl font-semibold text-slate-900">额外任务</h2></div><span className="text-sm text-slate-500">{detail?.extra_task_progress.completed_tasks ?? 0}/{detail?.extra_task_progress.total_tasks ?? 0} 已完成</span></div>{detail?.training_tasks.length ? <ol className="mt-4 divide-y divide-slate-100">{detail.training_tasks.map((task) => <li key={task.task_id} className="py-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-medium text-slate-900">{task.title}</h3><span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">{taskStatus(task.status)}</span></div><p className="mt-1 text-sm text-slate-600">目标：{task.goal}</p><p className="mt-1 text-xs text-slate-500">来源：平台管理员分配 · 类型：{task.scenario_type === "presentation" ? "演示讲解" : "销售对练"}</p></li>)}</ol> : <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">管理员尚未向该成员分配额外任务。</p>}</section>
        <section className="space-y-4" aria-labelledby="timeline-title"><h2 id="timeline-title" className="text-xl font-semibold text-slate-900">路径活动明细</h2>{journey.stages.map((stage) => <article key={stage.stage_id} className="rounded-2xl border border-slate-200 bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold text-slate-900">{stage.title}</h3><p className="mt-1 text-sm text-slate-500">{stage.objective}</p></div><span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700">{stage.status === "completed" ? "已完成" : stage.status === "locked" ? "尚未解锁" : "当前阶段"}</span></div><ul className="mt-4 space-y-2">{stage.activities.map((activity) => <li key={activity.activity_id} className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm">{activity.status === "completed" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : activity.status === "locked" ? <Lock className="h-4 w-4 text-slate-400" /> : <span className="h-2 w-2 rounded-full bg-blue-600" />}<span className="flex-1 text-slate-800">{activity.title}</span><span className="text-slate-500">{activityStatusLabel(activity)}</span></li>)}</ul></article>)}</section>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />刷新</Button>
    </main>;
}
