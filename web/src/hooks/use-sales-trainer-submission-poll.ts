"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SalesTrainerAudioSubmission } from "@/lib/api/types";
import { isTerminalSubmissionStatus } from "@/lib/sales-trainer/learner-presenter";

const POLL_INTERVALS_MS = [2000, 4000, 8000];
const MAX_POLL_INTERVAL_MS = 30000;

interface UseSalesTrainerSubmissionPollOptions {
    enabled?: boolean;
}

interface UseSalesTrainerSubmissionPollResult {
    submission: SalesTrainerAudioSubmission | null;
    isLoading: boolean;
    isPolling: boolean;
    error: string | null;
    refresh: () => Promise<void>;
}

export function useSalesTrainerSubmissionPoll(
    submissionId: string,
    options: UseSalesTrainerSubmissionPollOptions = {},
): UseSalesTrainerSubmissionPollResult {
    const { enabled = true } = options;
    const [submission, setSubmission] = useState<SalesTrainerAudioSubmission | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isPolling, setIsPolling] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const pollAttemptRef = useRef(0);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const isMountedRef = useRef(true);
    const hasLoadedRef = useRef(false);
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
    }, [clearScheduledPoll, enabled, submissionId]);

    useEffect(() => {
        fetchSubmissionRef.current = fetchSubmission;
    }, [fetchSubmission]);

    useEffect(() => {
        isMountedRef.current = true;
        pollAttemptRef.current = 0;
        hasLoadedRef.current = false;
        clearScheduledPoll();

        if (!enabled || !submissionId) {
            return () => {
                isMountedRef.current = false;
                clearScheduledPoll();
            };
        }

        // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch on mount is intentional for polling hook
        void fetchSubmission();

        return () => {
            isMountedRef.current = false;
            clearScheduledPoll();
        };
    }, [clearScheduledPoll, enabled, fetchSubmission, submissionId]);

    return {
        submission,
        isLoading,
        isPolling,
        error,
        refresh: fetchSubmission,
    };
}
