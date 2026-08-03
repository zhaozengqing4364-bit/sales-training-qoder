"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Plus, RefreshCw, Search } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";

const STATUS_LABELS: Record<string, string> = {
    draft: "草稿",
    active: "已发布",
    archived: "已归档",
};

export function FoundationPathList() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const tokenStore = useRef(createIdempotencyTokenStore());
    const [query, setQuery] = useState("");
    const [submittedQuery, setSubmittedQuery] = useState("");
    const [showCreate, setShowCreate] = useState(false);
    const [stableKey, setStableKey] = useState("");
    const [title, setTitle] = useState("");
    const [formError, setFormError] = useState<string | null>(null);

    const paths = useQuery({
        queryKey: ["foundation-admin", "paths", submittedQuery],
        queryFn: () => api.admin.newcomerTraining.listPaths({ query: submittedQuery || undefined, limit: 100 }),
    });
    const create = useMutation({
        mutationFn: async () => {
            const normalizedKey = stableKey.trim();
            const normalizedTitle = title.trim();
            if (!normalizedKey || !normalizedTitle) throw new Error("请填写路径名称和业务编码。");
            const inputKey = `create-path:${normalizedKey}:${normalizedTitle}`;
            const result = await api.admin.newcomerTraining.createPathV2(
                { stable_key: normalizedKey, title: normalizedTitle },
                tokenStore.current.tokenFor(inputKey),
            );
            tokenStore.current.complete(inputKey);
            return result;
        },
        onSuccess: async (result) => {
            await queryClient.invalidateQueries({ queryKey: ["foundation-admin", "paths"] });
            router.push(`/admin/newcomer-training/paths/${encodeURIComponent(result.path_id)}/edit`);
        },
        onError: (error) => setFormError(getApiErrorMessage(error)),
    });
    const items = useMemo(() => paths.data?.items ?? [], [paths.data]);

    return (
        <FoundationAdminCapabilityBoundary capability="edit_paths">
            <main className="px-4 py-6 md:px-6">
                <div className="mx-auto max-w-7xl space-y-6">
                    <AdminPageHeader
                        title="路径与版本"
                        description="按阶段和训练活动维护工作修订；发布新版本不会自动迁移在训学员。"
                        icon={<Boxes className="h-7 w-7 text-blue-600" />}
                        primaryAction={(
                            <Button type="button" onClick={() => setShowCreate((value) => !value)}>
                                <Plus className="mr-2 h-4 w-4" />新建训练路径
                            </Button>
                        )}
                    />

                    {showCreate ? (
                        <section aria-labelledby="create-path-title" className="rounded-2xl border border-blue-200 bg-blue-50/60 p-5">
                            <h2 id="create-path-title" className="font-semibold text-slate-950">新建训练路径</h2>
                            <p className="mt-1 text-sm text-slate-600">先创建路径主体，随后在三栏编辑器中补充阶段、活动和资源。</p>
                            <form
                                className="mt-4 grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end"
                                onSubmit={(event) => {
                                    event.preventDefault();
                                    setFormError(null);
                                    create.mutate();
                                }}
                            >
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    路径名称
                                    <Input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} placeholder="例如：新人销售基础训练" />
                                </label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">
                                    业务编码
                                    <Input value={stableKey} onChange={(event) => setStableKey(event.target.value)} maxLength={120} placeholder="例如：sales-foundation" />
                                    <span className="block text-xs font-normal text-slate-500">用于版本追踪，创建后不再修改。</span>
                                </label>
                                <Button type="submit" disabled={create.isPending}>{create.isPending ? "正在创建…" : "创建并编辑"}</Button>
                            </form>
                            {formError ? <p role="alert" className="mt-3 text-sm text-red-700">{formError}</p> : null}
                        </section>
                    ) : null}

                    <form
                        role="search"
                        className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row"
                        onSubmit={(event) => {
                            event.preventDefault();
                            setSubmittedQuery(query.trim());
                        }}
                    >
                        <label className="relative flex-1">
                            <span className="sr-only">搜索路径</span>
                            <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-400" />
                            <Input value={query} onChange={(event) => setQuery(event.target.value)} className="pl-10" placeholder="按路径名称或业务编码搜索" />
                        </label>
                        <Button type="submit" variant="outline">搜索</Button>
                        <Button type="button" variant="ghost" onClick={() => void paths.refetch()} disabled={paths.isFetching}>
                            <RefreshCw className={`mr-2 h-4 w-4 ${paths.isFetching ? "animate-spin" : ""}`} />刷新
                        </Button>
                    </form>

                    {paths.isPending ? (
                        <div aria-label="正在加载训练路径" className="space-y-2 rounded-2xl border border-slate-200 bg-white p-5">
                            {[0, 1, 2].map((item) => <div key={item} className="h-16 animate-pulse rounded-xl bg-slate-100" />)}
                        </div>
                    ) : paths.error ? (
                        <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-950">
                            <h2 className="font-semibold">训练路径加载失败</h2>
                            <p className="mt-2 text-sm">{getApiErrorMessage(paths.error)}</p>
                            <Button type="button" variant="outline" className="mt-4 bg-white" onClick={() => void paths.refetch()}>重新加载</Button>
                        </div>
                    ) : items.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
                            <h2 className="font-semibold text-slate-950">{submittedQuery ? "没有匹配的训练路径" : "还没有训练路径"}</h2>
                            <p className="mt-2 text-sm text-slate-500">{submittedQuery ? "调整搜索条件后重试。" : "新建路径后，可按阶段编排完整新人训练。"}</p>
                        </div>
                    ) : (
                        <section aria-label="训练路径列表" className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                            <div className="divide-y divide-slate-100">
                                {items.map((path) => (
                                    <article key={path.path_id} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(220px,1.5fr)_180px_170px_auto] lg:items-center">
                                        <div className="min-w-0">
                                            <h2 className="truncate font-semibold text-slate-950">{path.title}</h2>
                                            <p className="mt-1 truncate text-xs text-slate-500">业务编码：{path.stable_key}</p>
                                        </div>
                                        <div><Badge variant={path.status === "active" ? "green" : "gray"}>{STATUS_LABELS[path.status] ?? "状态待确认"}</Badge></div>
                                        <div className="text-sm text-slate-600">
                                            <p>{path.active_release_plan_id ? "已有生效发布" : "尚未发布"}</p>
                                            <p className="mt-1 text-xs text-slate-400">更新于 {new Date(path.updated_at).toLocaleString("zh-CN")}</p>
                                        </div>
                                        <Button asChild variant="outline" size="sm">
                                            <Link href={`/admin/newcomer-training/paths/${encodeURIComponent(path.path_id)}/edit`} prefetch={false}>打开编辑器</Link>
                                        </Button>
                                    </article>
                                ))}
                            </div>
                        </section>
                    )}
                </div>
            </main>
        </FoundationAdminCapabilityBoundary>
    );
}
