"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, RefreshCw, RotateCcw, StopCircle } from "lucide-react";

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
    FoundationAssessmentTask,
    FoundationAudioChangePreview,
} from "@/lib/api/types/foundation-admin";

type TaskCommand = "redrive" | "cancel" | "regrade" | "invalidate" | null;

export function FoundationAssessmentOperationsWorkspace() {
    const queryClient = useQueryClient();
    const tokenStore = useRef(createIdempotencyTokenStore());
    const [state, setState] = useState("");
    const [selectedTask, setSelectedTask] = useState<FoundationAssessmentTask | null>(null);
    const [command, setCommand] = useState<TaskCommand>(null);
    const [reason, setReason] = useState("");
    const [audioPreview, setAudioPreview] = useState<FoundationAudioChangePreview | null>(null);
    const [resultMessage, setResultMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const tasks = useQuery({
        queryKey: ["foundation-admin", "assessment-tasks", state],
        queryFn: () => api.admin.newcomerTraining.listAssessmentTasks({ state: state || undefined, limit: 100 }),
        refetchInterval: 30_000,
    });
    const detail = useQuery({
        queryKey: ["foundation-admin", "assessment-task-detail", selectedTask?.task_id],
        queryFn: () => api.admin.newcomerTraining.getAssessmentTaskDetail(selectedTask?.task_id ?? ""),
        enabled: Boolean(selectedTask),
        refetchInterval: selectedTask ? 15_000 : false,
    });
    const execute = useMutation({
        mutationFn: async () => {
            if (!selectedTask || !command) throw new Error("请选择需要处理的任务。");
            if (!reason.trim()) throw new Error("请填写本次操作原因。");
            const key = `${command}-task:${selectedTask.task_id}:${reason.trim()}`;
            let value: unknown;
            if (command === "redrive") {
                value = await api.admin.newcomerTraining.redriveAssessmentTask(selectedTask.task_id, reason.trim(), tokenStore.current.tokenFor(key));
            } else if (command === "cancel") {
                value = await api.admin.newcomerTraining.cancelAssessmentTask(selectedTask.task_id, reason.trim(), tokenStore.current.tokenFor(key));
            } else {
                if (!audioPreview) throw new Error("影响预览已失效，请重新预览。");
                value = command === "regrade"
                    ? await api.admin.newcomerTraining.confirmAudioRegrade(selectedTask.resource_id, audioPreview, tokenStore.current.tokenFor(key))
                    : await api.admin.newcomerTraining.confirmAudioInvalidation(selectedTask.resource_id, audioPreview, tokenStore.current.tokenFor(key));
            }
            tokenStore.current.complete(key);
            return value;
        },
        onSuccess: async () => {
            setResultMessage(commandResultMessage(command));
            setCommand(null);
            setReason("");
            setAudioPreview(null);
            setError(null);
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "assessment-tasks"] }),
                queryClient.invalidateQueries({ queryKey: ["foundation-admin", "assessment-task-detail"] }),
            ]);
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });
    const previewAudioChange = useMutation({
        mutationFn: async () => {
            if (!selectedTask || (command !== "regrade" && command !== "invalidate")) {
                throw new Error("请选择需要处理的录音结果。");
            }
            if (!reason.trim()) throw new Error("请填写本次操作原因。");
            return command === "regrade"
                ? api.admin.newcomerTraining.previewAudioRegrade(selectedTask.resource_id, reason.trim())
                : api.admin.newcomerTraining.previewAudioInvalidation(selectedTask.resource_id, reason.trim());
        },
        onSuccess: (value) => {
            setAudioPreview(value);
            setError(null);
        },
        onError: (caught) => setError(getApiErrorMessage(caught)),
    });

    return (
        <FoundationAdminCapabilityBoundary capability={["retry_assessments", "regrade_results"]}>
            <main className="px-4 py-6 md:px-6"><div className="mx-auto max-w-[1450px] space-y-6">
                <AdminPageHeader title="评测任务" description="统一查看录音评测、题目生成、训练教练和达标证据的持久任务；所有操作只作用于明确业务对象。" icon={<ClipboardCheck className="h-7 w-7 text-blue-600" />} secondaryActions={<Button type="button" variant="outline" onClick={() => void tasks.refetch()} disabled={tasks.isFetching}><RefreshCw className={`mr-2 h-4 w-4 ${tasks.isFetching ? "animate-spin" : ""}`} />刷新任务</Button>} />
                {resultMessage ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{resultMessage}</div> : null}
                {error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{error}</div> : null}
                <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4"><label className="space-y-1 text-sm font-medium text-slate-700">任务状态<select className={selectClassName} value={state} onChange={(event) => setState(event.target.value)}><option value="">全部状态</option><option value="queued">等待处理</option><option value="running">处理中</option><option value="retry_wait">等待重试</option><option value="cancel_requested">正在取消</option><option value="dead_letter">需要人工处理</option><option value="succeeded">已完成</option><option value="cancelled">已取消</option></select></label><p className="pb-3 text-sm text-slate-500">列表已按当前账号的组织与业务对象授权过滤。</p></div>
                <div className="grid min-h-[600px] gap-4 lg:grid-cols-[minmax(420px,0.95fr)_minmax(420px,1.05fr)]">
                    <section aria-label="评测任务列表" className="rounded-2xl border border-slate-200 bg-white p-4">{tasks.isPending ? <div className="space-y-2">{[0,1,2].map((item) => <div key={item} className="h-24 animate-pulse rounded-xl bg-slate-100" />)}</div> : tasks.error ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-900">{getApiErrorMessage(tasks.error)}<button type="button" className="ml-2 font-semibold underline" onClick={() => void tasks.refetch()}>重试</button></div> : tasks.data?.items.length === 0 ? <div className="grid min-h-80 place-items-center text-center"><div><ClipboardCheck className="mx-auto h-8 w-8 text-emerald-500" /><h2 className="mt-3 font-semibold text-slate-950">当前没有可访问任务</h2><p className="mt-2 text-sm text-slate-500">可能没有待处理任务，或当前账号尚未获得相应业务对象范围。</p></div></div> : <div className="space-y-2">{tasks.data?.items.map((task) => <button key={task.task_id} type="button" onClick={() => { setSelectedTask(task); setResultMessage(null); setError(null); }} className={`w-full rounded-xl border p-4 text-left ${selectedTask?.task_id === task.task_id ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50"}`}><div className="flex items-start justify-between gap-3"><div><p className="font-medium text-slate-950">{task.category}</p><p className="mt-1 text-sm text-slate-600">{task.business_object}</p></div><TaskStateBadge state={task.state} label={task.state_label} /></div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500"><span>已尝试 {task.attempt_count} 次</span><span>等待自 {new Date(task.waiting_since).toLocaleString("zh-CN")}</span></div>{task.failure ? <p className="mt-2 line-clamp-2 text-xs text-red-700">{task.failure}</p> : null}</button>)}</div>}</section>
                    <section aria-label="任务处理详情" className="rounded-2xl border border-slate-200 bg-white p-5">{!selectedTask ? <div className="grid min-h-80 place-items-center text-center text-sm text-slate-500">从左侧选择任务，查看进度和当前允许的恢复动作。</div> : detail.isPending ? <div className="space-y-3">{[0,1,2].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100" />)}</div> : detail.error || !detail.data ? <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900"><h2 className="font-semibold">任务详情不可访问</h2><p className="mt-2 text-sm">{getApiErrorMessage(detail.error)} 当前列表不会提供越权恢复动作。</p></div> : <div className="space-y-5"><div className="flex items-start justify-between gap-3"><div><p className="text-sm text-slate-500">{selectedTask.business_object}</p><h2 className="mt-1 text-xl font-semibold text-slate-950">{selectedTask.category}</h2></div><TaskStateBadge state={detail.data.state} label={detail.data.status_label} /></div>{detail.data.stale ? <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">任务信息已超过 5 分钟未更新，执行操作前请先刷新。</div> : null}<dl className="grid gap-3 sm:grid-cols-2"><Info label="当前步骤" value={detail.data.current_step} /><Info label="尝试次数" value={`${detail.data.attempt_count} / ${detail.data.max_attempts}`} /><Info label="最后更新" value={new Date(detail.data.updated_at).toLocaleString("zh-CN")} /><Info label="结果状态" value={detail.data.result_kind ? resultKindLabel(detail.data.result_kind) : "尚无结果"} /></dl>{detail.data.progress ? <div><div className="flex justify-between text-xs text-slate-500"><span>{detail.data.progress.label ?? "处理进度"}</span><span>{detail.data.progress.current ?? 0} / {detail.data.progress.total ?? "-"}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: progressWidth(detail.data.progress.current, detail.data.progress.total) }} /></div></div> : null}{detail.data.partial_success_message ? <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{detail.data.partial_success_message}</div> : null}{detail.data.error?.message ? <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900"><p className="font-medium">本次处理未完成</p><p className="mt-1">{detail.data.error.message}</p></div> : null}{detail.data.result_location?.startsWith("/") ? <Button asChild variant="outline"><Link href={detail.data.result_location} prefetch={false}>打开持久化结果</Link></Button> : null}<div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">{detail.data.can_redrive && selectedTask.available_actions.includes("预览重试") ? <Button type="button" onClick={() => { openCommand("redrive", setCommand, setReason, setAudioPreview, setError); }}><RotateCcw className="mr-2 h-4 w-4" />预览单项重试</Button> : null}{detail.data.can_cancel && selectedTask.available_actions.includes("申请取消") ? <Button type="button" variant="outline" onClick={() => { openCommand("cancel", setCommand, setReason, setAudioPreview, setError); }}><StopCircle className="mr-2 h-4 w-4" />预览取消</Button> : null}{selectedTask.available_actions.includes("预览重评") ? <Button type="button" variant="outline" onClick={() => { openCommand("regrade", setCommand, setReason, setAudioPreview, setError); }}><RotateCcw className="mr-2 h-4 w-4" />预览重评</Button> : null}{selectedTask.available_actions.includes("预览失效") ? <Button type="button" variant="destructive" onClick={() => { openCommand("invalidate", setCommand, setReason, setAudioPreview, setError); }}><StopCircle className="mr-2 h-4 w-4" />预览失效</Button> : null}{!hasAvailableCommand(selectedTask, detail.data.can_redrive, detail.data.can_cancel) ? <p className="text-sm text-slate-500">当前状态没有可执行恢复动作。</p> : null}</div></div>}</section>
                </div>
            </div></main>
            <Dialog open={command !== null} onOpenChange={(open) => { if (!open && !execute.isPending && !previewAudioChange.isPending) setCommand(null); }}><DialogContent className="max-w-md"><DialogHeader><DialogTitle>{commandTitle(command)}</DialogTitle><DialogDescription>{commandDescription(command)}</DialogDescription></DialogHeader><div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm"><p className="font-medium text-slate-950">影响范围</p><p className="mt-1 text-slate-600">{selectedTask?.category} · {selectedTask?.business_object} · 1 个业务对象</p></div><label className="space-y-1 text-sm font-medium text-slate-700">操作原因<Input value={reason} onChange={(event) => { setReason(event.target.value); setAudioPreview(null); }} maxLength={500} placeholder="说明为什么需要执行此操作" /></label>{audioPreview ? <AudioChangeImpact command={command} preview={audioPreview} /> : null}{error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}<DialogFooter><Button type="button" variant="ghost" onClick={() => setCommand(null)} disabled={execute.isPending || previewAudioChange.isPending}>取消</Button>{(command === "regrade" || command === "invalidate") && !audioPreview ? <Button type="button" onClick={() => previewAudioChange.mutate()} disabled={previewAudioChange.isPending || !reason.trim()}>{previewAudioChange.isPending ? "正在检查…" : "生成影响预览"}</Button> : <Button type="button" variant={command === "invalidate" ? "destructive" : "primary"} onClick={() => execute.mutate()} disabled={execute.isPending}>{execute.isPending ? "正在执行…" : confirmCommandLabel(command)}</Button>}</DialogFooter></DialogContent></Dialog>
        </FoundationAdminCapabilityBoundary>
    );
}

function TaskStateBadge({ state, label }: { state: string; label: string }) { return <Badge variant={state === "succeeded" ? "green" : state === "dead_letter" ? "red" : state === "retry_wait" || state === "cancel_requested" ? "orange" : "gray"}>{label}</Badge>; }
function Info({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-slate-200 p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-sm font-medium text-slate-900">{value}</dd></div>; }
function resultKindLabel(value: string): string { return { success: "已完整保存", partial_success: "部分结果已保存", failure: "处理失败", cancelled: "已取消" }[value] ?? "结果待确认"; }
function progressWidth(current?: number, total?: number): string { if (typeof current !== "number" || typeof total !== "number" || total <= 0) return "0%"; return `${Math.max(0, Math.min(100, current / total * 100))}%`; }
function hasAvailableCommand(task: FoundationAssessmentTask, canRedrive: boolean, canCancel: boolean): boolean { return (canRedrive && task.available_actions.includes("预览重试")) || (canCancel && task.available_actions.includes("申请取消")) || task.available_actions.includes("预览重评") || task.available_actions.includes("预览失效"); }
function openCommand(command: Exclude<TaskCommand, null>, setCommand: (value: TaskCommand) => void, setReason: (value: string) => void, setPreview: (value: FoundationAudioChangePreview | null) => void, setError: (value: string | null) => void): void { setCommand(command); setReason(""); setPreview(null); setError(null); }
function commandTitle(command: TaskCommand): string { return { redrive: "预览单项重试", cancel: "预览取消任务", regrade: "预览录音重评", invalidate: "预览结果失效" }[command ?? "cancel"]; }
function commandDescription(command: TaskCommand): string { return { redrive: "只为当前业务对象创建一次新的处理任务，不会重试其他对象。", cancel: "申请在安全检查点停止当前任务；已经保存的部分结果不会被伪装成完整成功。", regrade: "创建新的评分版本并保留历史结果；不会覆盖既有评分记录。", invalidate: "将当前正式结果标记为失效，并重新投影达标证据；历史记录仍保留。" }[command ?? "cancel"]; }
function confirmCommandLabel(command: TaskCommand): string { return { redrive: "确认只重试此任务", cancel: "确认申请取消", regrade: "确认重评当前录音", invalidate: "确认失效当前结果" }[command ?? "cancel"]; }
function commandResultMessage(command: TaskCommand): string { return { redrive: "已为该业务对象创建新的可追踪处理任务，原失败记录继续保留。", cancel: "取消申请已记录；正在执行的任务会在安全检查点停止。", regrade: "重评任务已创建；旧评分继续保留，新结果完成后可从任务结果进入。", invalidate: "当前结果已标记失效；历史记录保留，达标证据会按正式状态重新计算。" }[command ?? "cancel"]; }
function AudioChangeImpact({ command, preview }: { command: TaskCommand; preview: FoundationAudioChangePreview }) { return <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><p className="font-semibold">影响已锁定</p><p className="mt-1">{command === "regrade" ? "将追加一个新的评分版本，现有历史结果不会被覆盖。" : "当前正式结果将失效，历史记录和审计不会删除。"}</p><p className="mt-1">预览有效期至 {new Date(preview.expires_at).toLocaleString("zh-CN")}</p></div>; }
const selectClassName = "h-12 min-w-48 rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/20";
