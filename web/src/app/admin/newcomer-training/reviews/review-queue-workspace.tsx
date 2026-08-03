"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, RefreshCw } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { ApiRequestError, api, getApiErrorMessage } from "@/lib/api/client";
import type { ReadinessReviewQueueV1 } from "@/lib/api/types/newcomer-training";
import {
    READINESS_STATE_OPTIONS,
    normalizeReadinessState,
    readinessQueueLearnerName,
    readinessRiskLabel,
} from "./readiness-view-model";

const PAGE_SIZE = 20;

export function ReadinessReviewQueueWorkspace() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const state = normalizeReadinessState(searchParams.get("state"));
    const cohortId = searchParams.get("cohort_id") ?? "";
    const offset = Math.max(0, Number(searchParams.get("offset") ?? "0") || 0);
    const [queue, setQueue] = useState<ReadinessReviewQueueV1 | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [permissionDenied, setPermissionDenied] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [stateDraft, setStateDraft] = useState(state);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        setPermissionDenied(false);
        try {
            setQueue(await api.admin.newcomerTraining.listReadinessReviews({
                state: state || undefined,
                cohort_id: cohortId || undefined,
                limit: PAGE_SIZE,
                offset,
            }));
        } catch (loadError) {
            setQueue(null);
            if (loadError instanceof ApiRequestError && loadError.status === 403) {
                setPermissionDenied(true);
            } else {
                setError(getApiErrorMessage(loadError));
            }
        } finally {
            setIsLoading(false);
        }
    }, [cohortId, offset, state]);

    useEffect(() => {
        void load();
    }, [load]);

    useEffect(() => {
        setStateDraft(state);
    }, [state]);

    function navigate(nextOffset: number, nextState = stateDraft, nextCohort = cohortId) {
        const params = new URLSearchParams();
        if (nextState.trim()) params.set("state", nextState.trim());
        if (nextCohort.trim()) params.set("cohort_id", nextCohort.trim());
        if (nextOffset > 0) params.set("offset", String(nextOffset));
        router.push(`/admin/newcomer-training/reviews${params.size ? `?${params}` : ""}`);
    }

    return (
        <main className="min-h-screen bg-slate-50 p-4 md:p-6" aria-busy={isLoading}>
            <div className="mx-auto max-w-6xl space-y-5">
                <AdminPageHeader
                    title="达标复核"
                    description="按风险和等待状态处理训练档案；AI 初评只提供依据，正式达标由有权限的复核人记录。"
                    icon={<ClipboardCheck className="h-7 w-7 text-blue-600" />}
                    secondaryActions={<Button variant="outline" onClick={() => void load()} disabled={isLoading}><RefreshCw className="mr-2 h-4 w-4" />刷新</Button>}
                />

                <GlassCard className="p-4">
                    <form
                        className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]"
                        onSubmit={(event) => { event.preventDefault(); navigate(0); }}
                    >
                        <div><label htmlFor="review-state" className="text-sm font-medium text-slate-800">复核状态</label><select id="review-state" value={stateDraft} onChange={(event) => setStateDraft(event.target.value)} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm">{READINESS_STATE_OPTIONS.map((option) => <option key={option.value || "all"} value={option.value}>{option.label}</option>)}</select></div>
                        <Button type="submit" className="self-end">应用筛选</Button>
                    </form>
                    {cohortId ? <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-blue-50 px-3 py-2 text-sm text-blue-900"><span>当前只显示从班级工作区进入的复核范围。</span><Button type="button" variant="ghost" size="sm" onClick={() => navigate(0, stateDraft, "")}>清除班级范围</Button></div> : null}
                </GlassCard>

                {isLoading ? <GlassCard className="p-6 text-sm text-slate-600">正在加载复核队列...</GlassCard> : null}
                {permissionDenied ? <GlassCard className="border-amber-200 p-6"><h2 className="font-semibold text-slate-950">当前账号不能查看达标复核</h2><p className="mt-2 text-sm text-slate-600">系统没有加载任何学员档案。请联系培训负责人申请复核范围，或返回其他已授权工作区。</p></GlassCard> : null}
                {error ? <GlassCard className="border-red-200 p-6"><p role="alert" className="text-sm text-red-700">复核队列加载失败：{error}</p><Button variant="outline" className="mt-4" onClick={() => void load()}>重新加载</Button></GlassCard> : null}
                {!isLoading && !error && !permissionDenied && queue?.data_freshness === "stale" ? <GlassCard className="border-amber-200 p-4 text-sm text-amber-900">当前队列可能不是最新结果，请刷新后再记录复核结论。</GlassCard> : null}
                {!isLoading && !error && !permissionDenied && queue?.items.length === 0 ? <GlassCard className="p-8 text-center"><h2 className="font-semibold text-slate-950">{state || cohortId ? "当前筛选范围没有复核档案" : "当前没有待复核档案"}</h2><p className="mt-2 text-sm text-slate-600">{state || cohortId ? "清除筛选条件查看全部档案。" : "等待学员完成必修训练并生成有效证据。"}</p>{state || cohortId ? <Button variant="outline" className="mt-4" onClick={() => { setStateDraft(""); navigate(0, "", ""); }}>清除筛选条件</Button> : null}</GlassCard> : null}

                {!isLoading && !error && !permissionDenied && queue?.items.map((item) => (
                    <GlassCard key={item.object_id} className="p-5">
                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0 space-y-2">
                                <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold text-slate-950">{readinessQueueLearnerName(item)}</h2><Badge className={item.risk_band === "high" ? "bg-red-50 text-red-700" : item.risk_band === "medium" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}>{readinessRiskLabel(item.risk_band)}</Badge></div>
                                <p className="text-sm text-slate-600">{item.object_summary.learner.cohort_name ?? "班级待补充"} · {item.object_summary.path.title}</p>
                                <p className="text-sm text-slate-700">{item.queue_reason}</p>
                                {item.evidence_gaps.length > 0 ? <p className="text-sm text-amber-700">存在 {item.evidence_gaps.length} 项能力证据缺口</p> : null}
                            </div>
                            <Button asChild><Link href={item.primary_action.href}>{item.primary_action.label}</Link></Button>
                        </div>
                    </GlassCard>
                ))}

                {queue && !permissionDenied ? <nav aria-label="复核队列分页" className="flex items-center justify-between"><p className="text-sm text-slate-600">共 {queue.total} 条</p><div className="flex gap-2"><Button variant="outline" disabled={offset === 0} onClick={() => navigate(Math.max(0, offset - PAGE_SIZE))}>上一页</Button><Button variant="outline" disabled={offset + PAGE_SIZE >= queue.total} onClick={() => navigate(offset + PAGE_SIZE)}>下一页</Button></div></nav> : null}
            </div>
        </main>
    );
}
