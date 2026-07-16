"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowRight, CalendarDays, RefreshCw, Search, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/hooks/use-current-user";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { TeamScopeResponse, TeamWorkbenchResponse } from "@/lib/api/types";
import type { AdminJourneyListResponse } from "@/lib/api/types/newcomer-training";
import { toTeamJourneyRow } from "@/lib/team-journey/view-models";

type RangeKey = "7" | "30" | "90" | "custom";

const SEARCH_DEBOUNCE_MS = 300;

function isoDate(date: Date) { return date.toISOString().slice(0, 10); }
export function rangeDates(range: RangeKey, customFrom: string, customTo: string) {
    const end = customTo ? new Date(`${customTo}T23:59:59+08:00`) : new Date();
    const start = range === "custom" && customFrom ? new Date(`${customFrom}T00:00:00+08:00`) : new Date(end.getTime() - (Number(range) - 1) * 86_400_000);
    const duration = end.getTime() - start.getTime() + 1;
    return { current: { date_from: start.toISOString(), date_to: end.toISOString() }, previous: { date_from: new Date(start.getTime() - duration).toISOString(), date_to: new Date(end.getTime() - duration).toISOString() } };
}

export default function TeamDashboardPage() {
    const { data: currentUser } = useCurrentUser();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [scope, setScope] = useState<TeamScopeResponse | null>(null);
    const [scopeLoading, setScopeLoading] = useState(true);
    const [scopeError, setScopeError] = useState<string | null>(null);
    const [journeys, setJourneys] = useState<AdminJourneyListResponse | null>(null);
    const [journeysRefreshing, setJourneysRefreshing] = useState(false);
    const [journeysError, setJourneysError] = useState<string | null>(null);
    const [insights, setInsights] = useState<TeamWorkbenchResponse | null>(null);
    const [insightsRefreshing, setInsightsRefreshing] = useState(false);
    const [insightsError, setInsightsError] = useState<string | null>(null);
    const [previous, setPrevious] = useState<TeamWorkbenchResponse | null>(null);
    const [previousRefreshing, setPreviousRefreshing] = useState(false);
    const [previousError, setPreviousError] = useState<string | null>(null);
    const teamId = searchParams.get("team") ?? "all";
    const range = (searchParams.get("range") as RangeKey | null) ?? "30";
    const query = searchParams.get("q") ?? "";
    const riskOnly = searchParams.get("risk") === "1";
    const customFrom = searchParams.get("from") ?? isoDate(new Date(Date.now() - 29 * 86_400_000));
    const customTo = searchParams.get("to") ?? isoDate(new Date());
    const [searchDraft, setSearchDraft] = useState(query);
    const requestIdRef = useRef(0);
    const scopeLoadedRef = useRef(false);
    const hasDataRef = useRef(false);

    useEffect(() => { setSearchDraft(query); }, [query]);
    useEffect(() => {
        hasDataRef.current = journeys !== null || insights !== null || previous !== null;
    }, [insights, journeys, previous]);

    const updateParams = useCallback((changes: Record<string, string | null>) => {
        const next = new URLSearchParams(searchParams.toString());
        Object.entries(changes).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
        router.replace(`/team?${next.toString()}`);
    }, [router, searchParams]);

    useEffect(() => {
        if (searchDraft === query) return;
        const timer = window.setTimeout(() => {
            updateParams({ q: searchDraft.trim() || null });
        }, SEARCH_DEBOUNCE_MS);
        return () => window.clearTimeout(timer);
    }, [query, searchDraft, updateParams]);

    const loadScope = useCallback(async () => {
        setScopeLoading(true);
        setScopeError(null);
        try {
            setScope(await api.supervisor.getTeamScope());
            scopeLoadedRef.current = true;
        } catch (reason) {
            setScopeError(getApiErrorMessage(reason));
        } finally {
            setScopeLoading(false);
        }
    }, []);

    const loadData = useCallback(async () => {
        const requestId = ++requestIdRef.current;
        const dates = rangeDates(range, customFrom, customTo);
        const hasExisting = hasDataRef.current;
        setJourneysRefreshing(hasExisting);
        setInsightsRefreshing(hasExisting);
        setPreviousRefreshing(hasExisting);
        setJourneysError(null);
        setInsightsError(null);
        setPreviousError(null);
        const journeyPromise = api.admin.newcomerTraining.listJourneys({
            limit: 100,
            team_id: teamId === "all" ? undefined : teamId,
            search: query || undefined,
        }).then((result) => {
            if (requestId !== requestIdRef.current) return;
            setJourneys(result);
            setJourneysError(null);
        }).catch((reason) => {
            if (requestId !== requestIdRef.current) return;
            setJourneysError(getApiErrorMessage(reason));
        }).finally(() => {
            if (requestId !== requestIdRef.current) return;
            setJourneysRefreshing(false);
        });
        const currentPromise = api.supervisor.getTeamWorkbench({
            ...dates.current,
            team_id: teamId === "all" ? undefined : teamId,
            search: query || undefined,
        }).then((result) => {
            if (requestId !== requestIdRef.current) return;
            setInsights(result);
            setInsightsError(null);
        }).catch((reason) => {
            if (requestId !== requestIdRef.current) return;
            setInsightsError(getApiErrorMessage(reason));
        }).finally(() => {
            if (requestId !== requestIdRef.current) return;
            setInsightsRefreshing(false);
        });
        const previousPromise = api.supervisor.getTeamWorkbench({
            ...dates.previous,
            team_id: teamId === "all" ? undefined : teamId,
            search: query || undefined,
        }).then((result) => {
            if (requestId !== requestIdRef.current) return;
            setPrevious(result);
            setPreviousError(null);
        }).catch((reason) => {
            if (requestId !== requestIdRef.current) return;
            setPreviousError(getApiErrorMessage(reason));
        }).finally(() => {
            if (requestId !== requestIdRef.current) return;
            setPreviousRefreshing(false);
        });
        await Promise.allSettled([journeyPromise, currentPromise, previousPromise]);
    }, [customFrom, customTo, query, range, teamId]);

    useEffect(() => {
        if (!scopeLoadedRef.current) {
            void loadScope().then(() => { void loadData(); });
            return;
        }
        void loadData();
    }, [customFrom, customTo, loadData, loadScope, query, range, teamId]);

    const refreshAll = useCallback(async () => {
        setJourneysRefreshing(true);
        setInsightsRefreshing(true);
        setPreviousRefreshing(true);
        await Promise.all([loadScope(), loadData()]);
    }, [loadData, loadScope]);

    const role = currentUser?.role;
    const allowedIds = useMemo(() => new Set((scope?.members ?? []).filter((member) => teamId === "all" || member.team_id === teamId).map((member) => member.learner_id)), [scope, teamId]);
    const extraByLearner = useMemo(() => new Map((insights?.learners ?? []).map((item) => [item.learner_id, item])), [insights]);
    const rows = useMemo(() => (journeys?.items ?? []).map(toTeamJourneyRow).filter((row) => allowedIds.has(row.learnerId)).filter((row) => !query || row.learnerName.toLowerCase().includes(query.toLowerCase())).filter((row) => !riskOnly || row.riskLabels.length > 0 || (extraByLearner.get(row.learnerId)?.risk_labels.length ?? 0) > 0), [allowedIds, extraByLearner, journeys, query, riskOnly]);
    const pathCompleted = rows.filter((row) => row.totalRequired > 0 && row.completedCount >= row.totalRequired).length;
    const currentExtra = insights?.extra_task_progress.completion_rate ?? 0;
    const previousExtra = previous?.extra_task_progress.completion_rate ?? 0;
    const isRefreshing = journeysRefreshing || insightsRefreshing || previousRefreshing || (scopeLoading && scope !== null);
    // Keep full-page Skeleton until the first payload (or a data error) arrives — not merely after scope resolves.
    const initialLoading =
        !scopeError &&
        journeys === null &&
        insights === null &&
        previous === null &&
        !journeysError &&
        !insightsError &&
        !previousError;

    if (role && !["training_manager", "admin", "super_admin"].includes(role)) {
        return <EmptyState title="该页面仅向销售组长和平台管理员开放" description="如需查看团队学习情况，请联系管理员建立团队关系。" icon={<Users className="h-10 w-10 text-slate-300" />} />;
    }
    if (initialLoading) {
        return <div className="space-y-3">{[1, 2, 3].map((item) => <Skeleton key={item} className="h-24 rounded-2xl" />)}</div>;
    }
    if (scopeError && !scope) {
        return <EmptyState title="团队范围加载失败" description={scopeError} actionLabel="重新加载" onAction={() => void refreshAll()} icon={<RefreshCw className="h-10 w-10 text-slate-300" />} />;
    }

    return <main className="space-y-6 pb-20">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
                <p className="text-sm font-medium text-blue-700">只读工作台</p>
                <h1 className="text-3xl font-black text-slate-900">团队训练进展</h1>
                <p className="mt-2 text-slate-500">查看管理员分配后的新人路径、额外任务和确定性风险。本期不能发布或修改任务。</p>
            </div>
            <Button variant="outline" onClick={() => void refreshAll()}><RefreshCw className="mr-2 h-4 w-4" />刷新</Button>
        </header>
        {isRefreshing ? <p role="status" aria-live="polite" className="text-sm text-slate-500">正在更新团队数据…</p> : null}
        <section className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 md:grid-cols-2 xl:grid-cols-4" aria-label="查看范围">
            {(scope?.teams.length ?? 0) > 1 ? <label className="text-sm font-medium text-slate-700">团队<select className="mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3" value={teamId} onChange={(event) => updateParams({ team: event.target.value === "all" ? null : event.target.value })}><option value="all">全部负责团队</option>{scope?.teams.map((team) => <option key={team.team_id} value={team.team_id}>{team.name}</option>)}</select></label> : <div className="text-sm font-medium text-slate-700">团队<p className="mt-1 flex h-10 items-center rounded-lg bg-slate-50 px-3 font-normal text-slate-900">{scope?.teams[0]?.name ?? "暂无负责团队"}</p></div>}
            <label className="text-sm font-medium text-slate-700">时间范围<select className="mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3" value={range} onChange={(event) => updateParams({ range: event.target.value })}><option value="7">近 7 天</option><option value="30">近 30 天</option><option value="90">近 90 天</option><option value="custom">自定义</option></select></label>
            {range === "custom" ? <><label className="text-sm font-medium text-slate-700">开始日期<Input className="mt-1" type="date" value={customFrom} onChange={(event) => updateParams({ from: event.target.value })} /></label><label className="text-sm font-medium text-slate-700">结束日期<Input className="mt-1" type="date" value={customTo} onChange={(event) => updateParams({ to: event.target.value })} /></label></> : <div className="md:col-span-2 flex items-center text-sm text-slate-500"><CalendarDays className="mr-2 h-4 w-4" />对比紧邻的同等时长周期</div>}
        </section>
        <section className="grid gap-4 md:grid-cols-2" aria-label="进度概览">
            <article className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-sm font-medium text-slate-500">新人训练路径</p>
                {journeysError ? <div role="alert" className="mt-3 space-y-2 text-sm text-red-700"><p>{journeysError}</p><Button size="sm" variant="outline" onClick={() => void loadData()}>重试路径数据</Button></div> : <><p className="mt-2 text-3xl font-bold text-slate-900">{pathCompleted}/{rows.length}</p><p className="mt-1 text-sm text-slate-600">已完成路径人数；不与额外任务混合计算</p></>}
            </article>
            <article className="rounded-2xl border border-slate-200 bg-white p-5">
                <p className="text-sm font-medium text-slate-500">管理员额外分配任务</p>
                {insightsError ? <div role="alert" className="mt-3 space-y-2 text-sm text-red-700"><p>{insightsError}</p><Button size="sm" variant="outline" onClick={() => void loadData()}>重试额外任务</Button></div> : <>
                    <p className="mt-2 text-3xl font-bold text-slate-900">{Math.round(currentExtra)}%</p>
                    {previousError ? <p className="mt-1 text-sm text-amber-700">上一同期暂不可用，无法比较</p> : <p className={`mt-1 text-sm ${currentExtra >= previousExtra ? "text-emerald-700" : "text-amber-700"}`}>较上一同期 {currentExtra >= previousExtra ? "+" : ""}{Math.round(currentExtra - previousExtra)} 个百分点</p>}
                </>}
            </article>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white">
            <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center">
                <label className="relative flex-1"><span className="sr-only">搜索成员</span><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><Input className="pl-9" placeholder="搜索成员姓名" value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} /></label>
                <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={riskOnly} onChange={(event) => updateParams({ risk: event.target.checked ? "1" : null })} />只看需关注</label>
            </div>
            {journeysError ? <div role="alert" className="space-y-2 p-8 text-sm text-red-700"><p>{journeysError}</p><Button variant="outline" onClick={() => void loadData()}>重试成员列表</Button></div>
                : rows.length === 0 ? <div className="p-8"><EmptyState title="当前范围没有成员" description="请调整团队、日期或筛选条件；团队关系由平台管理员维护。" icon={<Users className="h-10 w-10 text-slate-300" />} /></div>
                : <div className="divide-y divide-slate-100">{rows.map((row) => { const extra = extraByLearner.get(row.learnerId); const hasRisk = row.riskLabels.length > 0 || (extra?.risk_labels.length ?? 0) > 0; return <Link key={row.learnerId} href={`/team/${encodeURIComponent(row.learnerId)}?${searchParams.toString()}`} className="flex items-center gap-4 p-5 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-100 font-semibold text-slate-700">{row.learnerName.slice(0, 1)}</div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold text-slate-900">{row.learnerName}</h2>{hasRisk ? <span className="rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-800"><AlertTriangle className="mr-1 inline h-3 w-3" />需关注</span> : null}</div><p className="mt-1 text-sm text-slate-500">路径 {row.completedCount}/{row.totalRequired} · 额外任务 {extra?.extra_task_progress.completed_tasks ?? 0}/{extra?.extra_task_progress.total_tasks ?? 0}</p><p className="mt-1 truncate text-xs text-slate-600">{row.riskLabels.length ? `依据：${row.riskLabels.join("、")}未通过` : hasRisk ? `依据：${extra?.risk_labels[0] ?? "任务结果"}` : "当前未命中风险规则"}</p></div><ArrowRight className="h-4 w-4 text-slate-400" /></Link>; })}</div>}
        </section>
    </main>;
}
