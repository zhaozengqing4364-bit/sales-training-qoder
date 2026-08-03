"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileQuestion, RefreshCw, Search, ShieldAlert } from "lucide-react";

import { AdminPageHeader } from "@/components/admin/admin-layout-shells";
import { FoundationAdminCapabilityBoundary } from "@/components/admin/newcomer-training/workspace-nav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/glass-modal";
import { Input } from "@/components/ui/input";
import { api, getApiErrorMessage } from "@/lib/api/client";
import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";
import type {
    FoundationBatchPreview,
    FoundationQuestionCandidate,
    FoundationQuestionGenerationBatch,
} from "@/lib/api/types/foundation-admin";

type ReviewCommand = "approve" | "reject" | "supersede";

const COMMAND_LABELS: Record<ReviewCommand, string> = {
    approve: "批准入库",
    reject: "拒绝候选题",
    supersede: "标记为已替代",
};
const REVIEW_PAGE_SIZE = 20;

export function FoundationQuestionReviewWorkspace() {
    const queryClient = useQueryClient();
    const pathname = usePathname();
    const router = useRouter();
    const searchParams = useSearchParams();
    const tokenStore = useRef(createIdempotencyTokenStore());
    const statusParam = searchParams.get("status");
    const status = statusParam === "all" ? "" : statusParam ?? "generated";
    const submittedSearch = searchParams.get("q") ?? "";
    const selectedBatchId = searchParams.get("batch") ?? "";
    const parsedPage = Number(searchParams.get("page"));
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const [selected, setSelected] = useState<string[]>([]);
    const [focusedId, setFocusedId] = useState<string | null>(null);
    const [command, setCommand] = useState<ReviewCommand>("approve");
    const [reason, setReason] = useState("");
    const [preview, setPreview] = useState<FoundationBatchPreview | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [result, setResult] = useState<Record<string, unknown> | null>(null);
    const [sourceRevisionId, setSourceRevisionId] = useState("");
    const [unitRevisionId, setUnitRevisionId] = useState("");
    const [promptRevisionId, setPromptRevisionId] = useState("");
    const [routingRevisionId, setRoutingRevisionId] = useState("");
    const [requestedCount, setRequestedCount] = useState("10");
    const [generationMessage, setGenerationMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const navigateFilters = (updates: {
        status?: string;
        q?: string;
        batch?: string;
        page?: number;
    }) => {
        const next = new URLSearchParams(searchParams.toString());
        Object.entries(updates).forEach(([key, value]) => {
            if (value === "" || value === 1 || value === undefined) next.delete(key);
            else next.set(key, String(value));
        });
        router.replace(`${pathname}${next.size ? `?${next}` : ""}`);
    };

    const generationOptions = useQuery({
        queryKey: ["foundation-admin", "question-generation-options"],
        queryFn: () => api.admin.newcomerTraining.getQuestionGenerationOptions(),
    });
    const sourceOptions = useQuery({
        queryKey: ["foundation-admin", "question-generation-sources"],
        queryFn: () => api.admin.newcomerTraining.listResourcesV2({ resource_type: "source_document", status: "active", page_size: 100 }),
    });
    const unitOptions = useQuery({
        queryKey: ["foundation-admin", "question-generation-units"],
        queryFn: () => api.admin.newcomerTraining.listResourcesV2({ resource_type: "learning_unit", status: "active", page_size: 100 }),
    });
    const batches = useQuery({
        queryKey: ["foundation-admin", "question-generation-batches"],
        queryFn: () => api.admin.newcomerTraining.listQuestionGenerationBatches(),
    });
    const candidates = useQuery({
        queryKey: ["foundation-admin", "question-candidates", status, selectedBatchId, submittedSearch, page],
        queryFn: () => api.admin.newcomerTraining.listCandidatesV2({ status: status || undefined, batch_id: selectedBatchId || undefined, search: submittedSearch || undefined, page, page_size: REVIEW_PAGE_SIZE }),
        placeholderData: (previous) => previous,
    });
    const items = useMemo(() => candidates.data?.items ?? [], [candidates.data]);
    const focused = items.find((item) => item.candidate_id === focusedId) ?? items[0] ?? null;
    const sourceItems = useMemo(() => sourceOptions.data?.items.filter((item) => item.published_revision_id) ?? [], [sourceOptions.data]);
    const unitItems = useMemo(() => unitOptions.data?.items.filter((item) => item.published_revision_id) ?? [], [unitOptions.data]);
    const sourceLabels = useMemo(() => new Map(sourceItems.map((item) => [item.published_revision_id, item.title])), [sourceItems]);
    const unitLabels = useMemo(() => new Map(unitItems.map((item) => [item.published_revision_id, item.title])), [unitItems]);

    const generationMutation = useMutation({
        mutationFn: async () => {
            const count = Number(requestedCount);
            const prompt = generationOptions.data?.prompt_options.find((item) => item.revision_id === (promptRevisionId || generationOptions.data?.prompt_options[0]?.revision_id));
            const route = generationOptions.data?.model_routing_options.find((item) => item.revision_id === (routingRevisionId || generationOptions.data?.model_routing_options[0]?.revision_id));
            if (!sourceRevisionId || !unitRevisionId) throw new Error("请选择已经随发布计划生效的材料和学习单元。");
            if (!Number.isInteger(count) || count < 1 || count > 100) throw new Error("生成数量必须是 1 到 100 的整数。");
            if (!prompt || !route) throw new Error("题目生成治理配置尚未就绪，请联系系统管理员。");
            const key = `question-generation:${sourceRevisionId}:${unitRevisionId}:${count}:${prompt.revision_id}:${route.revision_id}`;
            const value = await api.admin.newcomerTraining.startQuestionGenerationV2({
                source_revision_id: sourceRevisionId,
                learning_unit_revision_id: unitRevisionId,
                requested_count: count,
                prompt_template_id: prompt.template_id,
                prompt_revision_id: prompt.revision_id,
                model_routing_profile_id: route.profile_id,
                model_routing_revision_id: route.revision_id,
            }, tokenStore.current.tokenFor(key));
            tokenStore.current.complete(key);
            return value;
        },
        onSuccess: async (value) => {
            setGenerationMessage(value.task_id ? "题目生成任务已提交，可离开页面；任务进度和结果会持续保留。" : "题目生成批次已创建，请刷新查看状态。");
            setError(null);
            await queryClient.invalidateQueries({ queryKey: ["foundation-admin", "question-generation-batches"] });
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    const previewMutation = useMutation({
        mutationFn: async () => {
            if (selected.length === 0) throw new Error("请至少选择一道候选题。");
            if (!reason.trim()) throw new Error("请填写本次审核依据。");
            return api.admin.newcomerTraining.previewCandidateBulkReview({ command, candidate_ids: selected, review_reason: reason.trim() });
        },
        onSuccess: (value) => {
            setPreview(value);
            setResult(null);
            setDialogOpen(true);
            setError(null);
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });
    const confirmMutation = useMutation({
        mutationFn: async () => {
            if (!preview) throw new Error("审核预览已失效，请重新预览。");
            const key = `candidate-review:${preview.review_id ?? preview.impact_hash}:${command}`;
            const value = await api.admin.newcomerTraining.confirmCandidateBulkReview(preview, tokenStore.current.tokenFor(key));
            tokenStore.current.complete(key);
            return value;
        },
        onSuccess: async (value) => {
            setResult(value);
            setSelected([]);
            setError(null);
            await queryClient.invalidateQueries({ queryKey: ["foundation-admin", "question-candidates"] });
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    return (
        <FoundationAdminCapabilityBoundary capability="review_questions">
            <main className="px-4 py-6 md:px-6">
                <div className="mx-auto max-w-[1500px] space-y-6">
                    <AdminPageHeader
                        title="题库审核"
                        description="生成结果先作为候选草稿进入人工审核；只有批准后的精确修订才能进入正式测验。"
                        icon={<FileQuestion className="h-7 w-7 text-blue-600" />}
                        secondaryActions={<Button type="button" variant="outline" onClick={() => void candidates.refetch()} disabled={candidates.isFetching}><RefreshCw className={`mr-2 h-4 w-4 ${candidates.isFetching ? "animate-spin" : ""}`} />刷新队列</Button>}
                    />

                    <section aria-labelledby="question-generation-title" className="rounded-2xl border border-slate-200 bg-white p-5">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <h2 id="question-generation-title" className="font-semibold text-slate-950">生成候选题</h2>
                                <p className="mt-1 text-sm text-slate-600">从已随发布计划生效的材料和学习单元创建可恢复任务；生成结果仍需规则检查和人工审核。</p>
                            </div>
                            <Link href="/admin/newcomer-training/settings" prefetch={false} className="text-sm font-semibold text-blue-700 underline">查看治理设置</Link>
                        </div>
                        {generationOptions.isPending || sourceOptions.isPending || unitOptions.isPending ? (
                            <div aria-label="正在加载题目生成选项" className="mt-4 h-24 animate-pulse rounded-xl bg-slate-100" />
                        ) : generationOptions.error || sourceOptions.error || unitOptions.error ? (
                            <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">题目生成选项加载失败：{getApiErrorMessage(generationOptions.error ?? sourceOptions.error ?? unitOptions.error)}</div>
                        ) : !generationOptions.data?.ready ? (
                            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{generationOptions.data?.empty_message ?? "题目生成治理配置尚未就绪。"}</div>
                        ) : (
                            <div className="mt-4 grid gap-4 lg:grid-cols-3">
                                <label className="space-y-1 text-sm font-medium text-slate-700">已发布材料<select className={selectClassName} value={sourceRevisionId} onChange={(event) => { setSourceRevisionId(event.target.value); setGenerationMessage(null); }}><option value="">请选择材料</option>{sourceItems.map((item) => <option key={item.resource_id} value={item.published_revision_id ?? ""}>{item.title}</option>)}</select></label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">已发布学习单元<select className={selectClassName} value={unitRevisionId} onChange={(event) => { setUnitRevisionId(event.target.value); setGenerationMessage(null); }}><option value="">请选择学习单元</option>{unitItems.map((item) => <option key={item.resource_id} value={item.published_revision_id ?? ""}>{item.title}</option>)}</select></label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">生成数量<Input inputMode="numeric" value={requestedCount} onChange={(event) => setRequestedCount(event.target.value)} /></label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">生成模板<select className={selectClassName} value={promptRevisionId || generationOptions.data.prompt_options[0]?.revision_id || ""} onChange={(event) => setPromptRevisionId(event.target.value)}>{generationOptions.data.prompt_options.map((item) => <option key={item.revision_id} value={item.revision_id}>{item.label}</option>)}</select></label>
                                <label className="space-y-1 text-sm font-medium text-slate-700">模型策略<select className={selectClassName} value={routingRevisionId || generationOptions.data.model_routing_options[0]?.revision_id || ""} onChange={(event) => setRoutingRevisionId(event.target.value)}>{generationOptions.data.model_routing_options.map((item) => <option key={item.revision_id} value={item.revision_id}>{item.label}</option>)}</select></label>
                                <div className="flex items-end"><Button type="button" className="w-full" onClick={() => { setError(null); generationMutation.mutate(); }} disabled={generationMutation.isPending}>{generationMutation.isPending ? "正在提交…" : "开始生成候选题"}</Button></div>
                            </div>
                        )}
                        {generationMessage ? <div role="status" className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">{generationMessage} <Link href="/admin/newcomer-training/assessments" prefetch={false} className="font-semibold underline">查看任务进度</Link></div> : null}
                    </section>

                    <section aria-labelledby="generation-batches-title" className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="generation-batches-title" className="font-semibold text-slate-950">生成批次</h2><p className="mt-1 text-sm text-slate-600">选择批次可只审核本次生成结果。</p></div><Button type="button" size="sm" variant={selectedBatchId ? "outline" : "primary"} onClick={() => { navigateFilters({ batch: "", page: 1 }); setSelected([]); setFocusedId(null); }}>全部批次</Button></div>
                        {batches.isPending ? <div className="mt-3 h-20 animate-pulse rounded-xl bg-slate-100" /> : batches.error ? <div role="alert" className="mt-3 text-sm text-red-700">批次加载失败：{getApiErrorMessage(batches.error)}</div> : batches.data?.items.length ? <div className="mt-3 grid gap-2 lg:grid-cols-3">{batches.data.items.map((batch) => <GenerationBatchRow key={batch.batch_id} batch={batch} selected={selectedBatchId === batch.batch_id} sourceLabel={sourceLabels.get(batch.source_revision_id) ?? "已发布材料"} unitLabel={unitLabels.get(batch.learning_unit_revision_id) ?? "已发布学习单元"} onSelect={() => { navigateFilters({ batch: batch.batch_id, page: 1 }); setSelected([]); setFocusedId(null); }} />)}</div> : <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">还没有题目生成批次，可在上方选择材料与学习单元后创建。</p>}
                    </section>

                    <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 lg:grid-cols-[180px_minmax(220px,1fr)_auto]">
                        <label className="space-y-1 text-sm font-medium text-slate-700">审核状态<select className={selectClassName} value={status} onChange={(event) => { navigateFilters({ status: event.target.value || "all", page: 1 }); setSelected([]); setFocusedId(null); }}><option value="generated">待开始审核</option><option value="in_review">审核中</option><option value="approved">已批准</option><option value="rejected">已拒绝</option><option value="superseded">已替代</option><option value="">全部状态</option></select></label>
                        <form role="search" className="flex items-end gap-2" onSubmit={(event) => { event.preventDefault(); const value = String(new FormData(event.currentTarget).get("q") ?? "").trim(); navigateFilters({ q: value, page: 1 }); setSelected([]); setFocusedId(null); }}><label className="relative min-w-0 flex-1"><span className="sr-only">搜索题干</span><Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-slate-400" /><Input key={submittedSearch} name="q" defaultValue={submittedSearch} className="pl-10" placeholder="搜索题干内容" /></label><Button type="submit" variant="outline">搜索</Button></form>
                        <div className="flex items-end"><Badge variant="gray">已选择 {selected.length} 题</Badge></div>
                    </div>

                    {error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</div> : null}

                    <div className="grid min-h-[620px] gap-4 xl:grid-cols-[minmax(420px,0.9fr)_minmax(460px,1.1fr)]">
                        <section aria-labelledby="candidate-queue-title" className="rounded-2xl border border-slate-200 bg-white p-4">
                            <h2 id="candidate-queue-title" className="mb-3 font-semibold text-slate-950">候选题队列</h2>
                            {candidates.isPending ? <div className="space-y-2">{[0, 1, 2].map((item) => <div key={item} className="h-28 animate-pulse rounded-xl bg-slate-100" />)}</div> : candidates.error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-900">{getApiErrorMessage(candidates.error)}<button type="button" className="ml-2 font-semibold underline" onClick={() => void candidates.refetch()}>重试</button></div> : items.length === 0 ? <div className="grid min-h-80 place-items-center text-center"><div><CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" /><h3 className="mt-3 font-semibold text-slate-950">当前筛选下没有候选题</h3><p className="mt-2 text-sm text-slate-500">题目生成任务完成后会进入这里等待人工审核。</p></div></div> : <><div className="space-y-2">{items.map((item) => <CandidateRow key={item.candidate_id} item={item} focused={focused?.candidate_id === item.candidate_id} checked={selected.includes(item.candidate_id)} onFocus={() => setFocusedId(item.candidate_id)} onCheck={(checked) => setSelected((current) => checked ? [...current, item.candidate_id] : current.filter((id) => id !== item.candidate_id))} />)}</div><nav aria-label="候选题分页" className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 text-sm text-slate-500"><span>共 {candidates.data?.total ?? 0} 题 · 第 {page} 页</span><div className="flex gap-2"><Button size="sm" variant="outline" disabled={page === 1} onClick={() => { navigateFilters({ page: page - 1 }); setSelected([]); setFocusedId(null); }}>上一页</Button><Button size="sm" variant="outline" disabled={page * REVIEW_PAGE_SIZE >= (candidates.data?.total ?? 0)} onClick={() => { navigateFilters({ page: page + 1 }); setSelected([]); setFocusedId(null); }}>下一页</Button></div></nav></>}
                        </section>

                        <section aria-label="候选题审核详情" className="rounded-2xl border border-slate-200 bg-white p-5">
                            {focused ? <CandidateDetail item={focused} /> : <div className="grid min-h-80 place-items-center text-sm text-slate-500">选择候选题查看来源、答案和能力映射。</div>}
                        </section>
                    </div>

                    <section aria-labelledby="bulk-review-title" className="rounded-2xl border border-slate-200 bg-white p-5">
                        <h2 id="bulk-review-title" className="font-semibold text-slate-950">批量审核</h2>
                        <p className="mt-1 text-sm text-slate-600">先预览逐项资格和影响，再确认执行；单题失败不会掩盖其他题目的结果。</p>
                        <div className="mt-4 grid gap-4 lg:grid-cols-[190px_minmax(260px,1fr)_auto] lg:items-end">
                            <label className="space-y-1 text-sm font-medium text-slate-700">审核动作<select className={selectClassName} value={command} onChange={(event) => { setCommand(event.target.value as ReviewCommand); setPreview(null); }}><option value="approve">批准入库</option><option value="reject">拒绝候选题</option><option value="supersede">标记为已替代</option></select></label>
                            <label className="space-y-1 text-sm font-medium text-slate-700">审核依据<Input value={reason} onChange={(event) => { setReason(event.target.value); setPreview(null); }} maxLength={2000} placeholder="说明答案、来源、能力映射或拒绝原因" /></label>
                            <Button type="button" onClick={() => previewMutation.mutate()} disabled={selected.length === 0 || previewMutation.isPending}>{previewMutation.isPending ? "正在预览…" : `预览${COMMAND_LABELS[command]}`}</Button>
                        </div>
                    </section>
                </div>
            </main>

            <Dialog open={dialogOpen} onOpenChange={(open) => { if (!confirmMutation.isPending) setDialogOpen(open); }}>
                <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto">
                    <DialogHeader><DialogTitle>批量审核影响预览</DialogTitle><DialogDescription>逐项确认当前候选题仍满足审核条件。</DialogDescription></DialogHeader>
                    {result ? <BatchResultPanel result={result} /> : preview ? <div className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><Summary label="可执行" value={`${preview.eligible_count} 题`} tone="green" /><Summary label="无法执行" value={`${preview.failure_count} 题`} tone={preview.failure_count ? "red" : "gray"} /></div><div className="space-y-2">{preview.items.map((item) => <div key={item.candidate_id} className={`rounded-xl border p-3 text-sm ${item.status === "eligible" ? "border-emerald-100 bg-emerald-50" : "border-red-100 bg-red-50"}`}><span className="font-medium">{item.status === "eligible" ? "可以执行" : "无法执行"}</span>{item.reason ? <p className="mt-1 text-xs text-slate-600">{item.reason}</p> : null}</div>)}</div></div> : null}
                    {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
                    <DialogFooter><Button type="button" variant="ghost" onClick={() => setDialogOpen(false)} disabled={confirmMutation.isPending}>{result ? "关闭" : "取消"}</Button>{!result && preview ? <Button type="button" onClick={() => confirmMutation.mutate()} disabled={preview.eligible_count === 0 || confirmMutation.isPending}>{confirmMutation.isPending ? "正在执行…" : `确认${COMMAND_LABELS[command]}`}</Button> : null}</DialogFooter>
                </DialogContent>
            </Dialog>
        </FoundationAdminCapabilityBoundary>
    );
}

function GenerationBatchRow({ batch, selected, sourceLabel, unitLabel, onSelect }: { batch: FoundationQuestionGenerationBatch; selected: boolean; sourceLabel: string; unitLabel: string; onSelect: () => void }) {
    const presentation = generationBatchPresentation(batch.status);
    return (
        <div className={`rounded-xl border p-3 ${selected ? "border-blue-300 bg-blue-50" : "border-slate-200"}`}>
            <button type="button" aria-pressed={selected} className="w-full text-left" onClick={onSelect}>
                <div className="flex items-start justify-between gap-2"><span className="font-medium text-slate-950">{sourceLabel}</span><Badge variant={presentation.variant}>{presentation.label}</Badge></div>
                <p className="mt-1 truncate text-xs text-slate-500">{unitLabel}</p>
                <p className="mt-2 text-xs text-slate-600">计划 {batch.requested_count} 题 · 已生成 {batch.candidate_count} 题 · {new Date(batch.created_at).toLocaleString("zh-CN")}</p>
            </button>
            {batch.recovery_available ? <Link href="/admin/newcomer-training/assessments" prefetch={false} className="mt-2 inline-block text-xs font-semibold text-blue-700 underline">查看失败原因并恢复</Link> : null}
        </div>
    );
}

function CandidateRow({ item, focused, checked, onFocus, onCheck }: { item: FoundationQuestionCandidate; focused: boolean; checked: boolean; onFocus: () => void; onCheck: (value: boolean) => void }) {
    return <div className={`rounded-xl border p-4 ${focused ? "border-blue-300 bg-blue-50" : "border-slate-200"}`}><div className="flex items-start gap-3"><input aria-label={`选择题目：${item.content.stem}`} type="checkbox" className="mt-1 h-4 w-4" checked={checked} onChange={(event) => onCheck(event.target.checked)} /><button type="button" onClick={onFocus} className="min-w-0 flex-1 text-left"><div className="flex flex-wrap items-center gap-2"><Badge variant="gray">生成草稿</Badge>{item.risk_level === "high" ? <Badge variant="red">需重点复核</Badge> : null}<Badge variant={item.gate_status === "passed" ? "green" : "orange"}>{item.gate_status === "passed" ? "规则检查通过" : "规则检查待处理"}</Badge></div><p className="mt-3 line-clamp-2 text-sm font-medium leading-6 text-slate-950">{item.content.stem}</p><p className="mt-2 text-xs text-slate-500">{questionTypeLabel(item.content.question_type)} · {difficultyLabel(item.content.difficulty)} · {new Date(item.created_at).toLocaleString("zh-CN")}</p></button></div></div>;
}

function CandidateDetail({ item }: { item: FoundationQuestionCandidate }) {
    const gateWarning = item.gate_status !== "passed";
    return <div className="space-y-5"><div><div className="flex flex-wrap gap-2"><Badge variant="gray">候选草稿</Badge><Badge variant={item.risk_level === "high" ? "red" : "blue"}>{item.risk_level === "high" ? "高风险复核" : "常规复核"}</Badge></div><h2 className="mt-4 text-lg font-semibold leading-8 text-slate-950">{item.content.stem}</h2></div>{gateWarning ? <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />自动规则检查未完全通过，批准前必须核对重复、答案和来源。</div> : null}{item.content.options.length > 0 ? <section><h3 className="text-sm font-semibold text-slate-700">选项与参考答案</h3><div className="mt-2 space-y-2">{item.content.options.map((option) => <div key={option.option_id} className={`rounded-xl border p-3 text-sm ${option.is_correct ? "border-emerald-200 bg-emerald-50 text-emerald-950" : "border-slate-200 text-slate-700"}`}><span className="font-medium">{option.is_correct ? "参考正确项 · " : ""}</span>{option.text}</div>)}</div></section> : <section><h3 className="text-sm font-semibold text-slate-700">参考答案</h3><p className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">{item.content.reference_answer}</p></section>}<section><h3 className="text-sm font-semibold text-slate-700">解析与评分依据</h3><p className="mt-2 text-sm leading-6 text-slate-700">{item.content.explanation}</p></section><section className="grid gap-3 sm:grid-cols-2"><div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">能力映射</p><p className="mt-1 text-sm font-medium text-slate-900">{item.content.competency_keys.join("、") || "尚未映射"}</p></div><div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">来源位置</p><p className="mt-1 text-sm font-medium text-slate-900">已关联 {item.content.source_anchor_ids.length} 处来源</p></div></section></div>;
}

function BatchResultPanel({ result }: { result: Record<string, unknown> }) {
    const items = Array.isArray(result.items) ? result.items.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : [];
    const succeeded = typeof result.succeeded_count === "number" ? result.succeeded_count : items.filter((item) => item.status === "succeeded").length;
    const failed = typeof result.failure_count === "number" ? result.failure_count : items.filter((item) => item.status === "failed").length;
    return <div role="status" className="space-y-4"><div className={`rounded-xl border p-4 ${failed ? "border-amber-200 bg-amber-50" : "border-emerald-200 bg-emerald-50"}`}><h3 className="font-semibold text-slate-950">{failed ? "批量审核部分完成" : "批量审核已完成"}</h3><p className="mt-1 text-sm text-slate-700">成功 {succeeded} 题，未成功 {failed} 题。结果已持久化，可只修正失败项后重新预览。</p></div>{items.length ? <div className="space-y-2">{items.map((item, index) => <div key={String(item.candidate_id ?? index)} className={`rounded-xl border p-3 text-sm ${item.status === "succeeded" ? "border-emerald-100 bg-emerald-50" : "border-red-100 bg-red-50"}`}><span className="font-medium">{item.status === "succeeded" ? "已完成" : "未完成"}</span>{typeof item.message === "string" ? <p className="mt-1 text-xs text-slate-600">{item.message}</p> : null}</div>)}</div> : null}</div>;
}

function Summary({ label, value, tone }: { label: string; value: string; tone: "green" | "red" | "gray" }) { return <div className={`rounded-xl border p-4 ${tone === "green" ? "border-emerald-200 bg-emerald-50" : tone === "red" ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold text-slate-950">{value}</p></div>; }
function questionTypeLabel(value: FoundationQuestionCandidate["content"]["question_type"]): string { return { single_choice: "单选题", multiple_choice: "多选题", true_false: "判断题", short_answer: "简答题" }[value]; }
function difficultyLabel(value: FoundationQuestionCandidate["content"]["difficulty"]): string { return { easy: "基础", medium: "进阶", hard: "挑战" }[value]; }
function generationBatchPresentation(status: FoundationQuestionGenerationBatch["status"]): { label: string; variant: "gray" | "blue" | "green" | "red" | "orange" } {
    const presentations: Record<FoundationQuestionGenerationBatch["status"], { label: string; variant: "gray" | "blue" | "green" | "red" | "orange" }> = {
        queued: { label: "等待生成", variant: "gray" },
        running: { label: "正在生成", variant: "blue" },
        completed: { label: "生成完成", variant: "green" },
        failed: { label: "生成失败", variant: "red" },
        cancelled: { label: "已取消", variant: "orange" },
    };
    return presentations[status];
}
const selectClassName = "h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
