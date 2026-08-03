"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, RefreshCw, Search, Users } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { Button } from "@/components/ui/button";
import { api, getApiErrorMessage } from "@/lib/api/client";
import type { FoundationAdminLearnerListResponse } from "@/lib/api/types/foundation-admin";

const PAGE_SIZE = 20;

export default function NewcomerTrainingLearnersPage() {
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [data, setData] = useState<FoundationAdminLearnerListResponse | null>(null);
    const search = searchParams.get("q")?.trim() ?? "";
    const parsedPage = Number(searchParams.get("page"));
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const offset = (page - 1) * PAGE_SIZE;
    const [searchInput, setSearchInput] = useState(search);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true); setError(null);
        try { setData(await api.admin.newcomerTraining.listLearners({ search: search || undefined, limit: PAGE_SIZE, offset })); }
        catch (cause) { setData(null); setError(getApiErrorMessage(cause)); }
        finally { setLoading(false); }
    }, [offset, search]);
    useEffect(() => { void load(); }, [load]);

    const navigate = (nextPage: number, nextSearch = search) => {
        const next = new URLSearchParams();
        if (nextSearch) next.set("q", nextSearch);
        if (nextPage > 1) next.set("page", String(nextPage));
        router.replace(`${pathname}${next.size ? `?${next}` : ""}`);
    };

    return <main className="min-h-screen bg-slate-50 p-4 md:p-6"><div className="mx-auto max-w-6xl space-y-5"><AdminPageHeader title="学员进度" description="查看每位新人的冻结训练版本、权威进度和下一步；正式达标结论仍由达标复核工作区记录。" icon={<Users className="h-7 w-7 text-blue-600" />} />
        <form className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row" onSubmit={(event) => { event.preventDefault(); navigate(1, searchInput.trim()); }}><label className="flex-1 text-sm font-medium text-slate-700">搜索学员<input aria-label="搜索学员" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="输入学员姓名；留空查看全部可管理学员" className="mt-1 h-11 w-full rounded-xl border border-slate-200 px-3" /></label><Button type="submit" className="self-end"><Search className="mr-2 h-4 w-4" />搜索</Button></form>
        {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">正在加载学员进度…</div> : error ? <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><p>{error}</p><Button className="mt-3" variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 h-4 w-4" />重新加载</Button></div> : data?.items.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><h2 className="font-semibold text-slate-900">{search ? "没有匹配学员" : "还没有进入新人训练的学员"}</h2><p className="mt-2 text-sm text-slate-500">{search ? "请调整姓名关键词后重新搜索。" : "在班级中分配已发布路径后，学员会出现在这里。"}</p></div> : <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><div className="min-w-[720px] divide-y divide-slate-100">{data?.items.map((item) => <article key={item.enrollment.enrollment_id} className="grid gap-4 p-5 md:grid-cols-[minmax(180px,0.8fr)_minmax(260px,1.4fr)_auto] md:items-center"><div><h2 className="break-words font-semibold text-slate-900">{item.learner.name || "未命名学员"}</h2><p className="mt-1 text-sm text-slate-500">{item.cohort.name} · {item.path.revision_label}</p></div><div><div className="flex items-center justify-between text-sm"><span className="text-slate-600">训练完成度</span><strong className="text-slate-900">{item.progress.percentage}%</strong></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${item.progress.percentage}%` }} /></div><p className="mt-2 break-words text-sm text-slate-600">{item.primary_action ? `下一步：${item.primary_action.label}` : item.status === "completed" ? "全部训练已完成" : item.status_label}</p></div><Button asChild variant="outline"><Link href={`/admin/newcomer-training/learners/${encodeURIComponent(item.learner.learner_id)}`} prefetch={false}>查看训练详情<ArrowRight className="ml-2 h-4 w-4" /></Link></Button></article>)}</div><div className="flex items-center justify-between border-t border-slate-100 p-4 text-sm text-slate-500"><span>共 {data?.total ?? 0} 位学员 · 第 {page} 页</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page === 1} onClick={() => navigate(page - 1)}>上一页</Button><Button size="sm" variant="outline" disabled={offset + PAGE_SIZE >= (data?.total ?? 0)} onClick={() => navigate(page + 1)}>下一页</Button></div></div></div>}
    </div></main>;
}
