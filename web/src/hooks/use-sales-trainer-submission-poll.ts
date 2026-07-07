"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioSubmission } from "@/lib/api/types";
import { isTerminalSubmissionStatus } from "@/lib/sales-trainer/learner-presenter";

const POLL_INTERVALS_MS = [2000, 4000, 8000];
const MAX_POLL_INTERVAL_MS = 30000;
// 总超时：超过此时间仍在非终态则停止轮询并提示用户稍后刷新。
// submission 通常 1-3 分钟完成；给到 10 分钟兜底长时间转写/评分。
const DEFAULT_TOTAL_TIMEOUT_MS = 10 * 60 * 1000;

interface UseSalesTrainerSubmissionPollOptions {
    enabled?: boolean;
    /** 轮询总超时（毫秒），超时后停止并提示。默认 10 分钟。 */
    totalTimeoutMs?: number;
}

interface UseSalesTrainerSubmissionPollResult {
    submission: SalesTrainerAudioSubmission | null;
    isLoading: boolean;
    isPolling: boolean;
    error: string | null;
    /** 轮询是否因总超时停止（非终态）。用户可手动 refresh 重试。 */
    timedOut: boolean;
    refresh: () => Promise<void>;
}

export function useSalesTrainerSubmissionPoll(
    submissionId: string,
    options: UseSalesTrainerSubmissionPollOptions = {},
): UseSalesTrainerSubmissionPollResult {
    const { enabled = true, totalTimeoutMs = DEFAULT_TOTAL_TIMEOUT_MS } = options;
    const [submission, setSubmission] = useState<SalesTrainerAudioSubmission | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isPolling, setIsPolling] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [timedOut, setTimedOut] = useState(false);

    const pollAttemptRef = useRef(0);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const isMountedRef = useRef(true);
    const hasLoadedRef = useRef(false);
    const startedAtRef = useRef<number | null>(null);
    const fetchSubmissionRef = useRef<() => Promise<void>>(async () => {});

    const clearScheduledPoll = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
    }, []);

    const fetchSubmission = useCallback(async () => {
        if (!enabled || !submissionId) {
            return;
        }

        // 总超时检查：仍在非终态且超过 totalTimeoutMs 则停止轮询，提示用户。
        if (startedAtRef.current !== null) {
            const elapsed = Date.now() - startedAtRef.current;
            if (elapsed >= totalTimeoutMs) {
                if (!isMountedRef.current) {
                    return;
                }
                setIsPolling(false);
                setTimedOut(true);
                setError("评分耗时较长，请稍后刷新页面或重试。");
                clearScheduledPoll();
                return;
            }
        }

        if (!hasLoadedRef.current) {
            setIsLoading(true);
        }
        setError(null);

        try {
            const result = await api.salesTrainer.getAudioSubmission(submissionId);
            if (!isMountedRef.current) {
                return;
            }

            hasLoadedRef.current = true;
            setSubmission(result);
            setIsLoading(false);

            if (isTerminalSubmissionStatus(result.status)) {
                setIsPolling(false);
                setTimedOut(false);
                clearScheduledPoll();
                return;
            }

            // 下一轮调度前再做一次超时判断，避免刚到终态边缘又排一次无谓轮询。
            const nextElapsed = Date.now() - (startedAtRef.current ?? Date.now());
            if (nextElapsed >= totalTimeoutMs) {
                setIsPolling(false);
                setTimedOut(true);
                setError("评分耗时较长，请稍后刷新页面或重试。");
                clearScheduledPoll();
                return;
            }

            setIsPolling(true);
            const intervalIndex = Math.min(pollAttemptRef.current, POLL_INTERVALS_MS.length - 1);
            const delay = Math.min(POLL_INTERVALS_MS[intervalIndex], MAX_POLL_INTERVAL_MS);
            pollAttemptRef.current += 1;

            clearScheduledPoll();
            timeoutRef.current = setTimeout(() => {
                void fetchSubmissionRef.current();
            }, delay);
        } catch (loadError) {
            if (!isMountedRef.current) {
                return;
            }
            setSubmission(null);
            setError(getApiErrorMessage(loadError));
            setIsLoading(false);
            setIsPolling(false);
            clearScheduledPoll();
        }
    }, [clearScheduledPoll, enabled, submissionId, totalTimeoutMs]);

    useEffect(() => {
        fetchSubmissionRef.current = fetchSubmission;
    }, [fetchSubmission]);

    useEffect(() => {
        isMountedRef.current = true;
        pollAttemptRef.current = 0;
        hasLoadedRef.current = false;
        startedAtRef.current = Date.now();
        // eslint-disable-next-line react-hooks/set-state-in-effect -- reset timeout flag on (re)mount is intentional for polling hook
        setTimedOut(false);
        clearScheduledPoll();

        if (!enabled || !submissionId) {
            return () => {
                isMountedRef.current = false;
                clearScheduledPoll();
            };
        }

        void fetchSubmission();

        return () => {
            isMountedRef.current = false;
            clearScheduledPoll();
        };
    }, [clearScheduledPoll, enabled, fetchSubmission, submissionId]);

    const refresh = useCallback(async () => {
        // 手动刷新：重置超时窗口，给评分一个新的等待周期。
        startedAtRef.current = Date.now();
        setTimedOut(false);
        setError(null);
        await fetchSubmission();
    }, [fetchSubmission]);

    return {
        submission,
        isLoading,
        isPolling,
        error,
        timedOut,
        refresh,
    };
}
