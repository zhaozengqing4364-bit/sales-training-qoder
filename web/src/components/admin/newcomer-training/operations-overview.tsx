"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle2, RefreshCw } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";

import { useFoundationAdminCapabilities } from "./workspace-nav";

export function FoundationOperationsOverview() {
    const capabilityQuery = useFoundationAdminCapabilities();
    const overview = useQuery({
        queryKey: ["foundation-admin", "workspace"],
        queryFn: () => api.admin.newcomerTraining.getWorkspace(),
        enabled: capabilityQuery.data?.capabilities.includes("view_overview") === true,
        refetchInterval: 60_000,
    });
    const denied = !capabilityQuery.isPending && !capabilityQuery.data?.capabilities.includes("view_overview");
    return (
        <main className="px-4 py-6 md:px-6">
            <div className="mx-auto max-w-7xl space-y-5">
                <AdminPageHeader
                    title="新人训练运营工作台"
                    description="从需要处理的工作开始，完成路径发布、题目审核、评测恢复和达标复核。"
                    icon={<CheckCircle2 className="h-7 w-7 text-blue-600" />}
                />
                {capabilityQuery.isPending ? (
                    <LoadingRows />
                ) : capabilityQuery.error ? (
                    <ErrorState message={getApiErrorMessage(capabilityQuery.error)} retry={() => void capabilityQuery.refetch()} />
                ) : denied ? (
                    <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-950">
                        <h2 className="font-semibold">当前账号不能查看运营总览</h2>
                        <p className="mt-2 text-sm">{capabilityQuery.data?.permission_help}</p>
                    </div>
                ) : overview.isPending ? (
                    <LoadingRows />
                ) : overview.error ? (
                    <ErrorState message={getApiErrorMessage(overview.error)} retry={() => void overview.refetch()} />
                ) : overview.data?.is_partial ? (
                    <div role="status" className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                        部分队列暂未同步，已展示可确认的待办；稍后可重新加载。
                    </div>
                ) : null}
                {overview.data && overview.data.action_items.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
                        <CheckCircle2 className="mx-auto h-9 w-9 text-emerald-600" aria-hidden />
                        <h2 className="mt-3 font-semibold text-slate-950">当前没有待处理工作</h2>
                        <p className="mt-2 text-sm text-slate-500">新的审核、失败任务或发布阻塞出现后会集中显示在这里。</p>
                    </div>
                ) : overview.data ? (
                    <section aria-labelledby="action-queue-title" className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 px-5 py-4">
                            <div>
                                <h2 id="action-queue-title" className="font-semibold text-slate-950">当前待办</h2>
                                <p className="mt-1 text-sm text-slate-500">按失败风险和等待时间排序，共 {overview.data.action_items.length} 项。</p>
                            </div>
                            <Button type="button" variant="outline" size="sm" onClick={() => void overview.refetch()} disabled={overview.isFetching}>
                                <RefreshCw className={`mr-2 h-4 w-4 ${overview.isFetching ? "animate-spin" : ""}`} />
                                刷新待办
                            </Button>
                        </div>
                        <div className="divide-y divide-slate-100">
                            {overview.data.action_items.map((item) => (
                                <article key={`${item.category}-${item.id}`} className="grid gap-4 px-5 py-4 lg:grid-cols-[150px_minmax(220px,1fr)_minmax(280px,1.4fr)_auto] lg:items-center">
                                    <div className="flex items-center gap-2">
                                        {item.priority === "high" ? <AlertTriangle className="h-4 w-4 text-red-600" aria-label="高优先级" /> : null}
                                        <span className="text-sm font-semibold text-slate-700">{item.category}</span>
                                    </div>
                                    <div>
                                        <h3 className="font-medium text-slate-950">{item.title}</h3>
                                        <p className="mt-1 break-all text-xs text-slate-500">影响对象：{item.affected_object}</p>
                                    </div>
                                    <p className="text-sm leading-6 text-slate-600">{item.reason}</p>
                                    <Button asChild size="sm" variant="outline">
                                        <Link href={item.href} prefetch={false}>去处理<ArrowRight className="ml-2 h-4 w-4" /></Link>
                                    </Button>
                                </article>
                            ))}
                        </div>
                    </section>
                ) : null}
            </div>
        </main>
    );
}

function LoadingRows() {
    return <div aria-label="正在加载运营待办" className="space-y-2 rounded-2xl border border-slate-200 bg-white p-5">{[0, 1, 2].map((item) => <div key={item} className="h-16 animate-pulse rounded-xl bg-slate-100" />)}</div>;
}

function ErrorState({ message, retry }: { message: string; retry: () => void }) {
    return (
        <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900">
            <h2 className="font-semibold">运营待办加载失败</h2>
            <p className="mt-2 text-sm">{message}</p>
            <Button type="button" variant="outline" className="mt-4 bg-white" onClick={retry}><RefreshCw className="mr-2 h-4 w-4" />重新加载</Button>
        </div>
    );
}
