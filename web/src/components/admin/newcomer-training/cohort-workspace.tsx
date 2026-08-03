"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Search, Users } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";

const STATUS_LABELS: Record<string, string> = {
    active: "进行中",
    paused: "已暂停",
    cancelled: "已取消",
    closed: "已结束",
    archived: "已归档",
};

export function FoundationCohortWorkspace() {
    const queryClient = useQueryClient();
    const tokenStore = useRef(createIdempotencyTokenStore());
    const [search, setSearch] = useState("");
    const [submittedSearch, setSubmittedSearch] = useState("");
    const [status, setStatus] = useState("");
    const [showCreate, setShowCreate] = useState(false);
    const [name, setName] = useState("");
    const [stableKey, setStableKey] = useState("");
    const [pathRevisionId, setPathRevisionId] = useState("");
    const [error, setError] = useState<string | null>(null);

    const cohorts = useQuery({
        queryKey: ["foundation-admin", "cohorts", submittedSearch, status],
        queryFn: () => api.admin.newcomerTraining.listCohorts({ query: submittedSearch || undefined, status: status || undefined, limit: 100 }),
    });
    const paths = useQuery({
        queryKey: ["foundation-admin", "paths", "published-options"],
        queryFn: () => api.admin.newcomerTraining.listPaths({ limit: 100 }),
    });
    const publishedPaths = useMemo(() => paths.data?.items.filter((path) => path.published_revision_id) ?? [], [paths.data]);
    const create = useMutation({
        mutationFn: async () => {
            if (!name.trim() || !stableKey.trim() || !pathRevisionId) throw new Error("请填写班级名称、业务编码并选择已发布路径版本。");
            const key = `create-cohort:${stableKey.trim()}:${pathRevisionId}`;
            const result = await api.admin.newcomerTraining.createCohort({ stable_key: stableKey.trim(), name: name.trim(), path_revision_id: pathRevisionId }, tokenStore.current.tokenFor(key));
            tokenStore.current.complete(key);
            return result;
        },
        onSuccess: async () => {
            setName(""); setStableKey(""); setPathRevisionId(""); setShowCreate(false); setError(null);
            await queryClient.invalidateQueries({ queryKey: ["foundation-admin", "cohorts"] });
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    return (
        <FoundationAdminCapabilityBoundary capability="manage_cohorts">
            <main className="px-4 py-6 md:px-6"><div className="mx-auto max-w-7xl space-y-6">
                <AdminPageHeader title="学员与班级" description="班级绑定已发布路径修订；每名学员的 Enrollment 默认冻结在分配时版本。" icon={<Users className="h-7 w-7 text-blue-600" />} primaryAction={<Button type="button" onClick={() => setShowCreate((value) => !value)}><Plus className="mr-2 h-4 w-4" />新建班级</Button>} />
                {showCreate ? <section aria-labelledby="create-cohort-title" className="rounded-2xl border border-blue-200 bg-blue-50/50 p-5"><h2 id="create-cohort-title" className="font-semibold text-slate-950">新建训练班级</h2><p className="mt-1 text-sm text-slate-600">只允许绑定已经发布的路径版本；后续发布不会改变本班已分配学员。</p><form className="mt-4 grid gap-4 lg:grid-cols-[1fr_1fr_1.3fr_auto] lg:items-end" onSubmit={(event) => { event.preventDefault(); setError(null); create.mutate(); }}><Field label="班级名称"><Input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：2026 年 8 月新人班" /></Field><Field label="业务编码"><Input value={stableKey} onChange={(event) => setStableKey(event.target.value)} placeholder="例如：2026-08" /></Field><Field label="训练路径版本"><select className={selectClassName} value={pathRevisionId} onChange={(event) => setPathRevisionId(event.target.value)}><option value="">请选择已发布路径</option>{publishedPaths.map((path) => <option key={path.path_id} value={path.published_revision_id ?? ""}>{path.title}</option>)}</select></Field><Button type="submit" disabled={create.isPending}>{create.isPending ? "正在创建…" : "创建班级"}</Button></form>{publishedPaths.length === 0 && !paths.isPending ? <p className="mt-3 text-sm text-amber-800">当前没有已发布路径，请先完成路径发布计划。</p> : null}{error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}</section> : null}
                <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-[minmax(220px,1fr)_180px_auto]"><form role="search" className="flex gap-2" onSubmit={(event) => { event.preventDefault(); setSubmittedSearch(search.trim()); }}><label className="relative min-w-0 flex-1"><span className="sr-only">搜索班级</span><Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-400" /><Input value={search} onChange={(event) => setSearch(event.target.value)} className="pl-10" placeholder="搜索班级名称或编码" /></label><Button type="submit" variant="outline">搜索</Button></form><select aria-label="班级状态" className={selectClassName} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">全部状态</option><option value="active">进行中</option><option value="paused">已暂停</option><option value="closed">已结束</option><option value="cancelled">已取消</option></select><Button type="button" variant="ghost" onClick={() => void cohorts.refetch()} disabled={cohorts.isFetching}><RefreshCw className={`mr-2 h-4 w-4 ${cohorts.isFetching ? "animate-spin" : ""}`} />刷新</Button></div>
                {cohorts.isPending ? <div aria-label="正在加载班级" className="space-y-2 rounded-2xl border border-slate-200 bg-white p-5">{[0, 1, 2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100" />)}</div> : cohorts.error ? <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900">{getApiErrorMessage(cohorts.error)}<button type="button" className="ml-2 font-semibold underline" onClick={() => void cohorts.refetch()}>重试</button></div> : cohorts.data?.items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><h2 className="font-semibold text-slate-950">{submittedSearch ? "没有匹配班级" : "还没有训练班级"}</h2><p className="mt-2 text-sm text-slate-500">创建班级后，可在详情中选择或快速新建学员并预览批量分配。</p></div> : <section aria-label="训练班级列表" className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="divide-y divide-slate-100">{cohorts.data?.items.map((cohort) => <article key={cohort.cohort_id} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(240px,1fr)_150px_150px_auto] lg:items-center"><div><h2 className="font-semibold text-slate-950">{cohort.name}</h2><p className="mt-1 text-xs text-slate-500">班级编码：{cohort.stable_key}</p></div><Badge variant={cohort.status === "active" ? "green" : cohort.status === "cancelled" ? "red" : "gray"}>{STATUS_LABELS[cohort.status] ?? "状态待确认"}</Badge><p className="text-sm text-slate-600">{cohort.enrollment_count} 名学员</p><Button asChild size="sm" variant="outline"><Link href={`/admin/newcomer-training/cohorts/${encodeURIComponent(cohort.cohort_id)}`} prefetch={false}>管理班级</Link></Button></article>)}</div></section>}
            </div></main>
        </FoundationAdminCapabilityBoundary>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="space-y-1 text-sm font-medium text-slate-700"><span>{label}</span>{children}</label>; }
const selectClassName = "h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
