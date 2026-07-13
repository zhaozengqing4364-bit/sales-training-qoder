"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, RefreshCw, Search, Users } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { SalesTrainerAdminModuleNav } from "@/components/admin/sales-trainer/module-nav";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { AdminJourneyListResponse } from "@/lib/api/types/newcomer-training";
import { useSalesTrainerAdminRouteAccess } from "@/lib/sales-trainer/use-admin-route-access";

const PAGE_SIZE = 20;

export default function NewcomerTrainingLearnersPage() {
    const pathname = usePathname();
    const routeAccess = useSalesTrainerAdminRouteAccess(pathname);
    const [data, setData] = useState<AdminJourneyListResponse | null>(null);
    const [departmentInput, setDepartmentInput] = useState("");
    const [department, setDepartment] = useState("");
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await api.admin.newcomerTraining.listJourneys({ department: department || undefined, limit: PAGE_SIZE, offset })); }
        catch (cause) { setData(null); setError(getApiErrorMessage(cause)); }
        finally { setLoading(false); }
    }, [department, offset]);
    useEffect(() => { void load(); }, [load]);

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6"><div className="mx-auto max-w-6xl space-y-5"><AdminPageHeader title="学员进度" description="查看每位新人的当前主线、完成进度和下一步，具体评分与达标结论继续使用现有权威记录。" icon={<Users className="h-7 w-7 text-blue-600" />} secondaryActions={<SalesTrainerAdminModuleNav currentPath={pathname} capabilities={routeAccess.capabilities} />} />
        <form className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row" onSubmit={(event) => { event.preventDefault(); setOffset(0); setDepartment(departmentInput.trim()); }}><label className="flex-1 text-sm font-medium text-slate-700">部门筛选<input aria-label="部门筛选" value={departmentInput} onChange={(event) => setDepartmentInput(event.target.value)} placeholder="留空查看全部可管理部门" className="mt-1 h-11 w-full rounded-xl border border-slate-200 px-3" /></label><Button type="submit" className="self-end"><Search className="mr-2 h-4 w-4" />筛选</Button></form>
        {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">正在加载学员进度…</div> : error ? <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><p>{error}</p><Button className="mt-3" variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />重新加载</Button></div> : data?.items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><h2 className="font-semibold text-slate-900">还没有进入新人训练的学员</h2><p className="mt-2 text-sm text-slate-500">学员首次进入已发布的新人训练后，会自动出现在这里。</p></div> : <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="divide-y divide-slate-100">{data?.items.map((item) => <article key={item.learner_id} className="grid gap-4 p-5 md:grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.4fr)_auto] md:items-center"><div><h2 className="font-semibold text-slate-900">{item.learner_name || "未命名学员"}</h2><p className="mt-1 text-sm text-slate-500">{item.department || "未记录部门"}</p></div><div><div className="flex items-center justify-between text-sm"><span className="text-slate-600">训练完成度</span><strong className="text-slate-900">{Math.round(item.journey.progress.percent)}%</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.max(0, Math.min(100, item.journey.progress.percent))}%` }} /></div><p className="mt-2 text-sm text-slate-600">{item.journey.primary_next_action ? `下一步：${item.journey.primary_next_action.label}` : item.journey.progress.completed ? "全部训练已完成" : "当前没有可执行任务"}</p></div><Button asChild variant="outline"><Link href={`/admin/newcomer-training/learners/${encodeURIComponent(item.learner_id)}`}>查看训练详情<ArrowRight className="ml-2 h-4 w-4" /></Link></Button></article>)}</div><div className="flex items-center justify-between border-t border-slate-100 p-4 text-sm text-slate-500"><span>共 {data?.total ?? 0} 位学员</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>上一页</Button><Button size="sm" variant="outline" disabled={offset + PAGE_SIZE >= (data?.total ?? 0)} onClick={() => setOffset(offset + PAGE_SIZE)}>下一页</Button></div></div></div>}
    </div></main>;
}
