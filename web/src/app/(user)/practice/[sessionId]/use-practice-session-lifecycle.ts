"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SessionStatus } from "@/lib/api/types";
import type { ConnectionState } from "@/hooks/use-practice-websocket";
import { debug } from "@/lib/debug";

interface UsePracticeSessionLifecycleParams {
    sessionId: string;
    connectionState: ConnectionState;
    sessionStatus: SessionStatus;
    isRecordingRef: React.RefObject<boolean>;
    stopRecording: () => void;
}

export function usePracticeSessionLifecycle({
    sessionId,
    connectionState,
    sessionStatus,
    isRecordingRef,
    stopRecording,
}: UsePracticeSessionLifecycleParams) {
    const router = useRouter();
    const [isEndingSession, setIsEndingSession] = React.useState(false);
    const [pendingLifecycleAction, setPendingLifecycleAction] = React.useState<"pause" | "resume" | null>(null);
    const [lifecycleError, setLifecycleError] = React.useState<string | null>(null);
    const hasStartedSessionRef = React.useRef(false);
    const hasNavigatedToReportRef = React.useRef(false);

    const isSessionTerminal = sessionStatus === "completed" || sessionStatus === "scoring";
    const isSessionPaused = sessionStatus === "paused";
    const canToggleLifecycle =
        !isSessionTerminal
        && (sessionStatus === "in_progress" || sessionStatus === "paused")
        && !isEndingSession
        && pendingLifecycleAction === null;

    React.useEffect(() => {
        hasStartedSessionRef.current = false;
        hasNavigatedToReportRef.current = false;
        setIsEndingSession(false);
        setPendingLifecycleAction(null);
        setLifecycleError(null);
    }, [sessionId]);

    React.useEffect(() => {
        if (connectionState !== "connected") {
            hasStartedSessionRef.current = false;
            return;
        }

        if (sessionStatus !== "preparing" || hasStartedSessionRef.current) {
            return;
        }

        hasStartedSessionRef.current = true;

        void api.practice.startSession(sessionId).catch((error) => {
            debug.warn("[PracticeSession] Failed to start session via REST lifecycle", {
                sessionId,
                error,
            });
        });
    }, [connectionState, sessionId, sessionStatus]);

    React.useEffect(() => {
        if (!isSessionTerminal || hasNavigatedToReportRef.current) {
            return;
        }

        hasNavigatedToReportRef.current = true;
        setLifecycleError(null);

        if (isRecordingRef.current) {
            stopRecording();
        }

        router.push(`/practice/${sessionId}/report`);
    }, [isRecordingRef, isSessionTerminal, router, sessionId, stopRecording]);

    const handleTogglePauseResume = React.useCallback(async () => {
        if (!canToggleLifecycle) {
            return;
        }

        const action = sessionStatus === "paused" ? "resume" : "pause";
        setPendingLifecycleAction(action);

        try {
            if (action === "pause" && isRecordingRef.current) {
                stopRecording();
            }

            await api.practice.controlLifecycle(sessionId, action);
        } catch (error) {
            debug.warn(`[PracticeSession] Failed to ${action} session lifecycle`, {
                sessionId,
                error,
            });
        } finally {
            setPendingLifecycleAction(null);
        }
    }, [canToggleLifecycle, isRecordingRef, sessionId, sessionStatus, stopRecording]);

    const handleEndSession = React.useCallback(async () => {
        if (isEndingSession || isSessionTerminal) {
            return;
        }

        setLifecycleError(null);
        setIsEndingSession(true);

        if (isRecordingRef.current) {
            stopRecording();
        }

        try {
            await api.practice.endSession(sessionId);
        } catch (error) {
            const message = getApiErrorMessage(error);
            debug.warn("[PracticeSession] Failed to end session lifecycle", {
                sessionId,
                error,
                message,
            });
            setLifecycleError(message);
            setIsEndingSession(false);
        }
    }, [isEndingSession, isRecordingRef, isSessionTerminal, sessionId, stopRecording]);

    return {
        canToggleLifecycle,
        handleEndSession,
        handleTogglePauseResume,
        isEndingSession,
        isSessionPaused,
        isSessionTerminal,
        lifecycleError,
        pendingLifecycleAction,
    };
}
