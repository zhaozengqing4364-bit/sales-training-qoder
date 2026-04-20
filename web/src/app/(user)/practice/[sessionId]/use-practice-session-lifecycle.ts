"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SessionStatus } from "@/lib/api/types";
import type { ConnectionState } from "@/hooks/use-practice-websocket";
import { debug } from "@/lib/debug";
import type { AudioFlushResult, AudioFlushStatus } from "@/hooks/use-continuous-audio-uploader";

interface UsePracticeSessionLifecycleParams {
    sessionId: string;
    connectionState: ConnectionState;
    sessionStatus: SessionStatus;
    isRecordingRef: React.RefObject<boolean>;
    stopRecording: () => void;
    flushAudioEvidence?: () => Promise<AudioFlushResult>;
}

export interface PracticeLifecycleError {
    action: "start" | "pause" | "resume" | "end";
    message: string;
    guidance: string;
}

function buildLifecycleError(action: PracticeLifecycleError["action"], error: unknown): PracticeLifecycleError {
    const backendMessage = getApiErrorMessage(error).trim();

    if (action === "start") {
        return {
            action,
            message: backendMessage && backendMessage !== "请求失败，请稍后重试。"
                ? `启动训练失败，可重试。${backendMessage}`
                : "启动训练失败，可重试。",
            guidance: "请先确认连接正常，再点击“重试启动”；如果仍失败，可刷新页面后重新进入训练。",
        };
    }

    if (action === "pause") {
        return {
            action,
            message: "暂停失败，请再试一次。",
            guidance: "你可以先继续当前对话，稍后再暂停；如果按钮持续无响应，再结束本次练习后重新进入。",
        };
    }

    if (action === "resume") {
        return {
            action,
            message: "继续失败，请确认连接后再试一次。",
            guidance: "如果仍无法恢复，请先重新连接或刷新页面，再回到当前会话继续练习。",
        };
    }

    return {
        action,
        message: backendMessage && backendMessage !== "结束失败，请重试" && backendMessage !== "会话结束失败"
            ? `结束失败，请再试一次。${backendMessage}`
            : "结束失败，请再试一次。",
        guidance: "请先确认连接正常，再点击“结束练习”；如果仍失败，可先重新连接后重试结束。",
    };
}

export function usePracticeSessionLifecycle({
    sessionId,
    connectionState,
    sessionStatus,
    isRecordingRef,
    stopRecording,
    flushAudioEvidence,
}: UsePracticeSessionLifecycleParams) {
    const router = useRouter();
    const [isEndingSession, setIsEndingSession] = React.useState(false);
    const [pendingLifecycleAction, setPendingLifecycleAction] = React.useState<"pause" | "resume" | null>(null);
    const [lifecycleError, setLifecycleError] = React.useState<PracticeLifecycleError | null>(null);
    const [audioEvidenceFlushStatus, setAudioEvidenceFlushStatus] = React.useState<"idle" | "flushing" | AudioFlushStatus>("idle");
    const [audioEvidenceFlushMessage, setAudioEvidenceFlushMessage] = React.useState<string | null>(null);
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
        setAudioEvidenceFlushStatus("idle");
        setAudioEvidenceFlushMessage(null);
    }, [sessionId]);

    const handleStartSession = React.useCallback(async () => {
        hasStartedSessionRef.current = true;
        setLifecycleError(null);

        try {
            await api.practice.startSession(sessionId);
        } catch (error) {
            hasStartedSessionRef.current = false;
            debug.warn("[PracticeSession] Failed to start session via REST lifecycle", {
                sessionId,
                error,
            });
            setLifecycleError(buildLifecycleError("start", error));
        }
    }, [sessionId]);

    React.useEffect(() => {
        if (connectionState !== "connected") {
            hasStartedSessionRef.current = false;
            return;
        }

        if (sessionStatus !== "preparing" || hasStartedSessionRef.current) {
            return;
        }

        void handleStartSession();
    }, [connectionState, handleStartSession, sessionStatus]);

    React.useEffect(() => {
        if (!isSessionTerminal || hasNavigatedToReportRef.current) {
            return;
        }

        hasNavigatedToReportRef.current = true;
        setLifecycleError(null);

        const flushThenNavigate = async () => {
            setAudioEvidenceFlushStatus("flushing");
            setAudioEvidenceFlushMessage("正在保存最后一段音频证据，完成后进入报告。");

            if (isRecordingRef.current) {
                stopRecording();
            }

            try {
                const result = flushAudioEvidence
                    ? await flushAudioEvidence()
                    : { status: "completed" as const, pendingUploads: 0 };
                setAudioEvidenceFlushStatus(result.status);
                if (result.status === "completed") {
                    setAudioEvidenceFlushMessage("音频证据已保存，正在进入报告。");
                } else if (result.status === "timeout") {
                    setAudioEvidenceFlushMessage("音频证据保存超时，报告页会以证据缺失口径解释影响范围。");
                } else {
                    setAudioEvidenceFlushMessage(result.error || "音频证据保存失败，报告页会以证据缺失口径解释影响范围。");
                }
            } catch (error) {
                const message = getApiErrorMessage(error);
                debug.warn("[PracticeSession] Audio evidence flush failed before report navigation", {
                    sessionId,
                    error,
                    message,
                });
                setAudioEvidenceFlushStatus("failed");
                setAudioEvidenceFlushMessage(message || "音频证据保存失败，报告页会以证据缺失口径解释影响范围。");
            } finally {
                router.push(`/practice/${sessionId}/report`);
            }
        };

        void flushThenNavigate();
    }, [flushAudioEvidence, isRecordingRef, isSessionTerminal, router, sessionId, stopRecording]);

    const handleTogglePauseResume = React.useCallback(async () => {
        if (!canToggleLifecycle) {
            return;
        }

        const action = sessionStatus === "paused" ? "resume" : "pause";
        setLifecycleError(null);
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
            setLifecycleError(buildLifecycleError(action, error));
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
            setLifecycleError(buildLifecycleError("end", error));
            setIsEndingSession(false);
        }
    }, [isEndingSession, isRecordingRef, isSessionTerminal, sessionId, stopRecording]);

    return {
        canToggleLifecycle,
        handleEndSession,
        handleStartSession,
        handleTogglePauseResume,
        isEndingSession,
        isSessionPaused,
        isSessionTerminal,
        lifecycleError,
        audioEvidenceFlushMessage,
        audioEvidenceFlushStatus,
        pendingLifecycleAction,
    };
}
