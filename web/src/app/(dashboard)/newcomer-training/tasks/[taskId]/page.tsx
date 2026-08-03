"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Clock3, RefreshCw, TriangleAlert, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { FoundationTaskStatus } from "@/lib/api/types/newcomer-training";
import { generateClientId } from "@/lib/client-id";
import { trackFoundationUxEvent } from "@/lib/newcomer-training/ux-events";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";

const TERMINAL_STATES = new Set(["cancelled", "succeeded", "dead_letter"]);
const ACTIVE_POLL_MS = 3_000;
const HIDDEN_POLL_MS = 15_000;
const MAX_FAILURE_POLL_MS = 30_000;

export default function FoundationTaskPage({
    params,
}: {
    params: Promise<{ taskId: string }>;
}) {
    const { taskId } = use(params);
    const [task, setTask] = useState<FoundationTaskStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);
    const [cancelPending, setCancelPending] = useState(false);
    const cancelToken = useRef<string | null>(null);
    const waitingTracked = useRef(false);

    useEffect(() => {
        if (!task || TERMINAL_STATES.has(task.state) || waitingTracked.current) return;
        waitingTracked.current = true;
        trackFoundationUxEvent("task_waiting", "background_task");
    }, [task]);

    const refresh = useCallback(async (signal?: AbortSignal) => {
        const next = await api.newcomerTraining.getTask(taskId, signal);
        setTask(next);
        setError(null);
        return next;
    }, [taskId]);

    useEffect(() => {
        const update = () => setOnline(window.navigator.onLine);
        window.addEventListener("online", update);
        window.addEventListener("offline", update);
        return () => {
            window.removeEventListener("online", update);
            window.removeEventListener("offline", update);
        };
    }, []);

    useEffect(() => {
        let active = true;
        let timer: number | null = null;
        let controller: AbortController | null = null;
        let failureCount = 0;

        const schedule = (next: FoundationTaskStatus | null) => {
            if (!active || (next && TERMINAL_STATES.has(next.state))) return;
            const base = document.hidden ? HIDDEN_POLL_MS : ACTIVE_POLL_MS;
            const delay = Math.min(MAX_FAILURE_POLL_MS, base * 2 ** failureCount);
            timer = window.setTimeout(() => void poll(), delay);
        };
        const poll = async () => {
            if (!active) return;
            if (!window.navigator.onLine) {
                schedule(null);
                return;
            }
            controller = new AbortController();
            try {
                const next = await refresh(controller.signal);
                failureCount = 0;
                schedule(next);
            } catch (cause) {
                if (!active) return;
                failureCount = Math.min(failureCount + 1, 4);
                setError(`任务状态暂时无法更新：${getFoundationUserErrorMessage(cause)}。已保留上次结果，系统会继续重试。`);
                schedule(null);
            } finally {
                controller = null;
                if (active) setLoading(false);
            }
        };

        void poll();
        return () => {
            active = false;
            controller?.abort();
            if (timer !== null) window.clearTimeout(timer);
        };
    }, [refresh, taskId]);

    const requestCancel = async () => {
        cancelToken.current ??= generateClientId();
        setCancelPending(true);
        setError(null);
        try {
            const next = await api.newcomerTraining.requestTaskCancel(taskId, cancelToken.current);
            setTask(next);
        } catch (cause) {
            setError(`取消请求未提交：${getFoundationUserErrorMessage(cause)}。任务仍按上次状态运行，可以重试。`);
        } finally {
            setCancelPending(false);
        }
    };

    if (loading && !task) {
        return <main role="status" className="mx-auto max-w-2xl p-8 text-center text-slate-500">正在读取任务进度…</main>;
    }
    if (!task) {
        return <main className="mx-auto max-w-2xl space-y-4 p-8 text-center"><p role="alert" className="text-red-700">{error ?? "任务状态暂时无法读取。"}</p><Button onClick={() => window.location.reload()}>重新加载任务</Button></main>;
    }

    const completed = task.state === "succeeded";
    const terminalFailure = task.state === "dead_letter";
    const cancelled = task.state === "cancelled";
    const Icon = completed ? CheckCircle2 : terminalFailure ? TriangleAlert : Clock3;

    return (
        <main className="min-h-screen bg-slate-50 px-4 py-6 md:px-6 md:py-8">
            <div className="mx-auto max-w-2xl space-y-5">
                <Link href="/newcomer-training/notifications" className="text-sm font-medium text-slate-600 hover:text-slate-950 hover:underline">← 返回通知与任务</Link>
                <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
                    <div className="flex items-start gap-3">
                        <Icon aria-hidden="true" className="mt-1 h-6 w-6 shrink-0 text-blue-700" />
                        <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-blue-700">{task.state_label}</p>
                            <h1 className="mt-1 break-words text-2xl font-semibold text-slate-950">{task.title}</h1>
                            <p className="mt-2 text-sm leading-6 text-slate-600">任务已由系统持久保存，离开本页不会中断处理。网络中断也不会被当作任务失败。</p>
                        </div>
                    </div>

                    {task.progress ? (
                        <section aria-label="任务进度" className="mt-6 rounded-2xl bg-slate-50 p-4">
                            <p className="font-medium text-slate-900">{task.progress.label}</p>
                            {task.progress.current !== null && task.progress.total !== null ? <p className="mt-1 text-sm text-slate-600">已完成 {task.progress.current} / {task.progress.total}</p> : <p className="mt-1 text-sm text-slate-600">当前步骤完成后会自动更新。</p>}
                        </section>
                    ) : null}

                    {error ? <p role="status" className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">{error}</p> : null}
                    {!online ? <p role="status" className="mt-5 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><WifiOff aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />当前离线，页面保留上次任务状态；恢复网络后会继续刷新。</p> : null}
                    {task.error ? <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-3 text-sm leading-6 text-red-900">{task.error.message}{task.error.retryable ? " 系统仍可继续重试。" : " 请返回当前训练查看可用恢复操作。"}</p> : null}
                    {cancelled ? <p role="status" className="mt-5 text-sm text-slate-700">任务已取消；此前已经写入的业务结果不会丢失。</p> : null}

                    <div className="mt-6 flex flex-wrap gap-3">
                        {task.result_path ? <Button asChild><Link href={task.result_path}>查看业务结果</Link></Button> : null}
                        {!TERMINAL_STATES.has(task.state) ? <Button type="button" variant="outline" onClick={() => void refresh().catch((cause) => setError(getFoundationUserErrorMessage(cause)))}><RefreshCw className="mr-2 h-4 w-4" />刷新进度</Button> : null}
                        {task.can_cancel ? <Button type="button" variant="outline" disabled={cancelPending} onClick={() => void requestCancel()}>{cancelPending ? "正在提交取消…" : "取消后台任务"}</Button> : null}
                        {!task.result_path && TERMINAL_STATES.has(task.state) ? <Button asChild variant="outline"><Link href="/newcomer-training">返回当前训练</Link></Button> : null}
                    </div>
                </article>
            </div>
        </main>
    );
}
