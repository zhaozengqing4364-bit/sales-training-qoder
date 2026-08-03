"use client";

import { use, useEffect, useRef, useState } from "react";

import { ActivityShell } from "@/components/newcomer-training/activity-shell";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import {
    toActivityViewModel,
    type FoundationActivityViewModel,
} from "@/lib/newcomer-training/view-models";
import { trackFoundationUxEvent } from "@/lib/newcomer-training/ux-events";
import { getFoundationUserErrorMessage } from "@/lib/newcomer-training/errors";

const SLOW_LOAD_NOTICE_MS = 1_000;
const ACTIVITY_LOAD_TIMEOUT_MS = 10_000;
function isProcessing(detail: FoundationActivityViewModel): boolean {
    return detail.display.is_processing;
}

export default function NewcomerActivityPage({
    params,
}: {
    params: Promise<{ activityId: string }>;
}) {
    const { activityId } = use(params);
    const [reloadVersion, setReloadVersion] = useState(0);
    const requestKey = `${activityId}:${reloadVersion}`;
    const [loaded, setLoaded] = useState<{
        requestKey: string;
        detail: FoundationActivityViewModel;
    } | null>(null);
    const [loadError, setLoadError] = useState<{
        requestKey: string;
        message: string;
    } | null>(null);
    const [slowRequestKey, setSlowRequestKey] = useState<string | null>(null);
    const [pollErrorKey, setPollErrorKey] = useState<string | null>(null);
    const emittedSignals = useRef(new Set<string>());
    const detail = loaded?.requestKey === requestKey ? loaded.detail : null;
    const error = loadError?.requestKey === requestKey ? loadError.message : null;
    const isSlowLoading = slowRequestKey === requestKey;
    const pollError = pollErrorKey === requestKey;

    useEffect(() => {
        if (!detail) return;
        const emitOnce = (key: string, event: "activity_entered" | "activity_completed" | "task_waiting") => {
            if (emittedSignals.current.has(key)) return;
            emittedSignals.current.add(key);
            trackFoundationUxEvent(event, detail.activity.type);
        };
        emitOnce(`entered:${detail.activity.id}`, "activity_entered");
        if (detail.attempt?.status === "completed") {
            emitOnce(`completed:${detail.attempt.attempt_id}`, "activity_completed");
        }
        if (detail.display.is_processing) {
            emitOnce(`waiting:${detail.attempt?.attempt_id ?? detail.activity.id}`, "task_waiting");
        }
    }, [detail]);

    useEffect(() => {
        let active = true;
        const controller = new AbortController();

        const slowNotice = window.setTimeout(() => {
            if (active) {
                setSlowRequestKey(requestKey);
            }
        }, SLOW_LOAD_NOTICE_MS);
        const timeout = window.setTimeout(() => {
            if (!active) {
                return;
            }
            active = false;
            controller.abort();
            setLoadError({
                requestKey,
                message: "活动加载时间过长，请检查网络后重新加载。",
            });
        }, ACTIVITY_LOAD_TIMEOUT_MS);

        void api.newcomerTraining.getActivity(activityId, controller.signal)
            .then((nextDetail) => {
                if (!active) {
                    return;
                }
                setLoaded({ requestKey, detail: toActivityViewModel(nextDetail) });
            })
            .catch((cause) => {
                if (!active) {
                    return;
                }
                setLoadError({ requestKey, message: getFoundationUserErrorMessage(cause) });
            })
            .finally(() => {
                window.clearTimeout(slowNotice);
                window.clearTimeout(timeout);
            });

        return () => {
            active = false;
            controller.abort();
            window.clearTimeout(slowNotice);
            window.clearTimeout(timeout);
        };
    }, [activityId, reloadVersion, requestKey]);

    useEffect(() => {
        if (!detail || !isProcessing(detail)) {
            return;
        }
        let active = true;
        let timer: number | null = null;
        let controller: AbortController | null = null;
        let failureCount = 0;
        const poll = async () => {
            controller = new AbortController();
            try {
                const next = await api.newcomerTraining.getActivity(
                    activityId,
                    controller.signal,
                );
                if (!active) {
                    return;
                }
                setLoaded({ requestKey, detail: toActivityViewModel(next) });
                setPollErrorKey(null);
                failureCount = 0;
            } catch {
                if (active) {
                    setPollErrorKey(requestKey);
                    failureCount = Math.min(failureCount + 1, 4);
                }
            } finally {
                controller = null;
                if (active) {
                    const baseDelay = document.hidden ? 15_000 : 3_000;
                    timer = window.setTimeout(
                        () => void poll(),
                        Math.min(30_000, baseDelay * 2 ** failureCount),
                    );
                }
            }
        };
        timer = window.setTimeout(() => {
            void poll();
        }, document.hidden ? 15_000 : 3_000);
        return () => {
            active = false;
            controller?.abort();
            if (timer !== null) {
                window.clearTimeout(timer);
            }
        };
    }, [activityId, detail, requestKey]);

    if (error) {
        return (
            <div role="alert" className="mx-auto max-w-xl space-y-4 p-8 text-center">
                <p className="text-red-700">{error}</p>
                <Button type="button" variant="outline" onClick={() => setReloadVersion((value) => value + 1)}>
                    重新加载
                </Button>
            </div>
        );
    }
    if (!detail) {
        return (
            <div role="status" aria-live="polite" className="p-8 text-center text-slate-500">
                <p>正在加载活动…</p>
                {isSlowLoading ? (
                    <p className="mt-2 text-sm">正在获取任务材料和当前进度，请稍候。</p>
                ) : null}
            </div>
        );
    }
    return (
        <>
            {pollError ? (
                <div role="status" className="mx-auto mt-4 max-w-3xl rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
                    结果刷新暂时失败，系统会继续重试。
                </div>
            ) : null}
            <ActivityShell
                detail={detail}
                onRefresh={(nextDetail: FoundationActivityWorkspace) => setLoaded({ requestKey, detail: toActivityViewModel(nextDetail) })}
            />
        </>
    );
}
