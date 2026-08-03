"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, RefreshCw, RotateCcw, ShieldCheck } from "lucide-react";

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
    FoundationReleasePlan,
    FoundationRollbackPreview,
} from "@/lib/api/types/foundation-admin";

export function FoundationReleaseWorkspace() {
    const queryClient = useQueryClient();
    const tokens = useRef(createIdempotencyTokenStore());
    const [pathId, setPathId] = useState("");
    const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
    const [targetPlanId, setTargetPlanId] = useState("");
    const [reason, setReason] = useState("");
    const [preview, setPreview] = useState<FoundationRollbackPreview | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const paths = useQuery({
        queryKey: ["foundation-admin", "paths", "release-options"],
        queryFn: () => api.admin.newcomerTraining.listPaths({ limit: 100 }),
    });
    const releases = useQuery({
        queryKey: ["foundation-admin", "release-plans", pathId],
        queryFn: () => api.admin.newcomerTraining.listReleasePlans(pathId || undefined),
    });
    const pathById = useMemo(
        () => new Map(paths.data?.items.map((item) => [item.path_id, item]) ?? []),
        [paths.data],
    );
    const selectedPlan = releases.data?.items.find((item) => item.release_plan_id === selectedPlanId)
        ?? releases.data?.items[0]
        ?? null;
    const activePlanId = selectedPlan ? pathById.get(selectedPlan.path_id)?.active_release_plan_id ?? null : null;
    const activePlan = releases.data?.items.find((item) => item.release_plan_id === activePlanId) ?? null;
    const stableTargets = releases.data?.items.filter((item) => (
        item.path_id === selectedPlan?.path_id
        && item.release_plan_id !== activePlanId
        && ["published", "superseded"].includes(item.status)
    )) ?? [];

    const rollbackPreview = useMutation({
        mutationFn: async () => {
            if (!activePlan) throw new Error("当前路径没有可回滚的生效发布。");
            if (!targetPlanId) throw new Error("请选择一个已知稳定的历史发布。");
            if (!reason.trim()) throw new Error("请填写回滚原因。");
            return api.admin.newcomerTraining.previewReleaseRollback(
                activePlan.release_plan_id,
                targetPlanId,
                reason.trim(),
            );
        },
        onSuccess: async (value) => {
            setPreview(value);
            setError(null);
            await releases.refetch();
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });
    const rollbackConfirm = useMutation({
        mutationFn: async () => {
            if (!preview) throw new Error("回滚预览已失效，请重新预览。");
            const currentActive = releases.data?.items.find(
                (item) => item.release_plan_id === preview.active_release_plan_id,
            );
            if (!currentActive) throw new Error("当前生效发布已经变化，请刷新后重试。");
            const key = `rollback-release:${preview.active_release_plan_id}:${preview.impact_hash}`;
            const value = await api.admin.newcomerTraining.confirmReleaseRollback(
                preview.active_release_plan_id,
                preview,
                currentActive.version,
                tokens.current.tokenFor(key),
            );
            tokens.current.complete(key);
            return value;
        },
        onSuccess: async () => {
            setDialogOpen(false);
            setPreview(null);
            setReason("");
            setTargetPlanId("");
            setResult("已恢复已知稳定发布。活跃学员仍使用其原冻结版本，后续新分配使用恢复后的版本。");
            setError(null);
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "release-plans"] }),
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "paths"] }),
            ]);
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    return (
        <FoundationAdminCapabilityBoundary capability="publish_releases">
            <main className="px-4 py-6 md:px-6">
                <div className="mx-auto max-w-[1450px] space-y-6">
                    <AdminPageHeader
                        title="发布记录"
                        description="查看完整依赖校验和影响结果；回滚只重新激活已知稳定发布，不改写历史修订。"
                        icon={<History className="h-7 w-7 text-blue-600" />}
                        primaryAction={<Button asChild><Link href="/admin/newcomer-training/paths" prefetch={false}>进入路径发布</Link></Button>}
                        secondaryActions={<Button type="button" variant="outline" onClick={() => void Promise.all([paths.refetch(), releases.refetch()])} disabled={paths.isFetching || releases.isFetching}><RefreshCw className={`mr-2 h-4 w-4 ${paths.isFetching || releases.isFetching ? "animate-spin" : ""}`} />刷新记录</Button>}
                    />

                    {result ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{result}</div> : null}
                    {error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</div> : null}

                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <label className="space-y-1 text-sm font-medium text-slate-700">
                            路径范围
                            <select className={selectClassName} value={pathId} onChange={(event) => { setPathId(event.target.value); setSelectedPlanId(null); setTargetPlanId(""); setPreview(null); }}>
                                <option value="">全部路径</option>
                                {paths.data?.items.map((item) => <option key={item.path_id} value={item.path_id}>{item.title}</option>)}
                            </select>
                        </label>
                    </div>

                    <div className="grid min-h-[620px] gap-4 lg:grid-cols-[minmax(380px,0.9fr)_minmax(480px,1.1fr)]">
                        <section aria-label="发布记录列表" className="rounded-2xl border border-slate-200 bg-white p-4">
                            {releases.isPending ? <LoadingRows /> : releases.error ? <ErrorState message={getApiErrorMessage(releases.error)} onRetry={() => void releases.refetch()} /> : releases.data?.items.length === 0 ? <EmptyState /> : <div className="space-y-2">{releases.data?.items.map((plan) => {
                                const path = pathById.get(plan.path_id);
                                const active = path?.active_release_plan_id === plan.release_plan_id;
                                return <button key={plan.release_plan_id} type="button" onClick={() => { setSelectedPlanId(plan.release_plan_id); setTargetPlanId(""); setPreview(null); setResult(null); setError(null); }} className={`w-full rounded-xl border p-4 text-left ${selectedPlan?.release_plan_id === plan.release_plan_id ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}><div className="flex items-start justify-between gap-3"><div><p className="font-medium text-slate-950">{path?.title ?? "已归档路径"}</p><p className="mt-1 text-xs text-slate-500">{new Date(plan.created_at).toLocaleString("zh-CN")}</p></div><div className="flex flex-wrap justify-end gap-1"><ReleaseStatusBadge status={plan.status} />{active ? <Badge variant="green">当前生效</Badge> : null}</div></div><p className="mt-3 line-clamp-2 text-sm text-slate-600">{plan.reason}</p></button>;
                            })}</div>}
                        </section>

                        <section aria-label="发布详情" className="rounded-2xl border border-slate-200 bg-white p-5">
                            {!selectedPlan ? <div className="grid min-h-80 place-items-center text-sm text-slate-500">选择一条发布记录查看校验、影响和回滚选项。</div> : <ReleaseDetail plan={selectedPlan} pathTitle={pathById.get(selectedPlan.path_id)?.title ?? "已归档路径"} active={selectedPlan.release_plan_id === activePlanId} />}
                            {selectedPlan && activePlan ? <div className="mt-6 border-t border-slate-100 pt-5"><h3 className="font-semibold text-slate-950">恢复历史稳定发布</h3><p className="mt-1 text-sm text-slate-600">回滚不会迁移活跃学员；执行前必须选择同一路径的稳定记录并预览影响。</p>{stableTargets.length ? <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]"><select aria-label="回滚目标" className={selectClassName} value={targetPlanId} onChange={(event) => { setTargetPlanId(event.target.value); setPreview(null); }}><option value="">选择历史稳定发布</option>{stableTargets.map((item) => <option key={item.release_plan_id} value={item.release_plan_id}>{new Date(item.published_at ?? item.created_at).toLocaleString("zh-CN")} · {item.reason.slice(0, 30)}</option>)}</select><Button type="button" variant="outline" onClick={() => { setReason(""); setPreview(null); setDialogOpen(true); setError(null); }} disabled={!targetPlanId}><RotateCcw className="mr-2 h-4 w-4" />预览回滚</Button></div> : <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">还没有可恢复的历史稳定发布。</p>}</div> : null}
                        </section>
                    </div>
                </div>
            </main>

            <Dialog open={dialogOpen} onOpenChange={(open) => { if (!rollbackConfirm.isPending) setDialogOpen(open); }}>
                <DialogContent className="max-w-lg">
                    <DialogHeader><DialogTitle>预览回滚影响</DialogTitle><DialogDescription>仅切换后续新分配使用的稳定发布；当前活跃学员的冻结版本保持不变。</DialogDescription></DialogHeader>
                    <label className="space-y-1 text-sm font-medium text-slate-700">回滚原因<Input value={reason} onChange={(event) => { setReason(event.target.value); setPreview(null); }} maxLength={2000} placeholder="说明为什么需要恢复此版本" /></label>
                    {preview ? <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><div className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4" />影响已锁定</div><p>活跃学员：继续使用原冻结版本</p><p>后续新分配：使用所选历史稳定版本</p><p>预览有效期至 {new Date(preview.expires_at).toLocaleString("zh-CN")}</p></div> : null}
                    {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
                    <DialogFooter><Button type="button" variant="ghost" onClick={() => setDialogOpen(false)} disabled={rollbackConfirm.isPending}>取消</Button>{preview ? <Button type="button" variant="destructive" onClick={() => rollbackConfirm.mutate()} disabled={rollbackConfirm.isPending}>{rollbackConfirm.isPending ? "正在恢复…" : "确认恢复此稳定发布"}</Button> : <Button type="button" onClick={() => rollbackPreview.mutate()} disabled={rollbackPreview.isPending || !reason.trim()}>{rollbackPreview.isPending ? "正在检查…" : "生成影响预览"}</Button>}</DialogFooter>
                </DialogContent>
            </Dialog>
        </FoundationAdminCapabilityBoundary>
    );
}

function ReleaseDetail({ plan, pathTitle, active }: { plan: FoundationReleasePlan; pathTitle: string; active: boolean }) {
    const issues = Array.isArray(plan.validation_report.issues) ? plan.validation_report.issues : [];
    return <div className="space-y-5"><div className="flex items-start justify-between gap-3"><div><p className="text-sm text-slate-500">{pathTitle}</p><h2 className="mt-1 text-xl font-semibold text-slate-950">发布检查与影响</h2></div><div className="flex gap-1"><ReleaseStatusBadge status={plan.status} />{active ? <Badge variant="green">当前生效</Badge> : null}</div></div><dl className="grid gap-3 sm:grid-cols-2"><Info label="依赖对象" value={`${plan.target_revisions.length} 个精确修订`} /><Info label="依赖关系" value={plan.dependency_graph.acyclic === false ? "存在循环" : "无循环引用"} /><Info label="发布时间" value={plan.published_at ? new Date(plan.published_at).toLocaleString("zh-CN") : "尚未发布"} /><Info label="发布依据" value={plan.reason} /></dl><ImpactSummary plan={plan} />{issues.length ? <section><h3 className="font-semibold text-slate-950">校验结果</h3><div className="mt-3 space-y-2">{issues.map((issue, index) => <div key={`${issue.code}-${index}`} className={`rounded-xl border p-3 text-sm ${issue.severity === "blocker" ? "border-red-200 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}><p className="font-medium">{issue.severity === "blocker" ? "阻止发布" : issue.severity === "warning" ? "需要确认" : "改进建议"}</p><p className="mt-1">{issue.message}</p></div>)}</div></section> : <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">引用、能力映射、运行合同和依赖关系已通过本次发布计划检查。</div>}{plan.validation_report.publish_failure?.message ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"><p className="font-semibold">发布未完成，旧版本仍然有效</p><p className="mt-1">{plan.validation_report.publish_failure.message}</p></div> : null}</div>;
}

function ImpactSummary({ plan }: { plan: FoundationReleasePlan }) {
    const impact = plan.impact_preview;
    return <section><h3 className="font-semibold text-slate-950">影响预览</h3><div className="mt-3 grid gap-3 sm:grid-cols-3"><Info label="当前版本活跃学员" value={`${numberValue(impact.active_enrollments_on_current_revision)} 人`} /><Info label="进行中的训练任务" value={`${numberValue(impact.active_attempts)} 项`} /><Info label="自动迁移" value={impact.automatic_migration === true ? "会自动迁移" : "不会自动迁移"} /></div><p className="mt-3 text-sm text-slate-600">已有 Enrollment 保持冻结；发布只影响后续明确分配。</p></section>;
}

function ReleaseStatusBadge({ status }: { status: string }) {
    const label = { ready: "可发布", blocked: "有阻塞", publishing: "发布中", published: "已发布", superseded: "历史稳定", failed: "发布失败" }[status] ?? "状态待确认";
    return <Badge variant={status === "published" || status === "ready" ? "green" : status === "blocked" || status === "failed" ? "red" : status === "publishing" ? "orange" : "gray"}>{label}</Badge>;
}

function Info({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-slate-200 p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-slate-900">{value}</dd></div>; }
function numberValue(value: unknown): number { return typeof value === "number" && Number.isFinite(value) ? value : 0; }
function LoadingRows() { return <div className="space-y-2">{[0, 1, 2].map((item) => <div key={item} className="h-28 animate-pulse rounded-xl bg-slate-100" />)}</div>; }
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) { return <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-900">{message}<button type="button" className="ml-2 font-semibold underline" onClick={onRetry}>重试</button></div>; }
function EmptyState() { return <div className="grid min-h-80 place-items-center text-center"><div><History className="mx-auto h-8 w-8 text-slate-400" /><h2 className="mt-3 font-semibold text-slate-950">还没有发布记录</h2><p className="mt-2 text-sm text-slate-500">从路径编辑器创建发布计划后，校验和影响记录会保留在这里。</p></div></div>; }
const selectClassName = "h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
