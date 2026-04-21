"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { api, getApiErrorMessage } from "@/lib/api/client";
import type { SessionStatus } from "@/lib/api/types";
import type { AudioEvidenceFlushResult } from "@/hooks/use-continuous-audio-uploader";
import type { ConnectionState } from "@/hooks/use-practice-websocket";
import { debug } from "@/lib/debug";
import { practiceUxConfig } from "@/lib/practice-ux-config";

interface UsePracticeSessionLifecycleParams {
    sessionId: string;
    connectionState: ConnectionState;
    sessionStatus: SessionStatus;
    isRecordingRef: React.RefObject<boolean>;
    stopRecording: () => void;
    flushAudioEvidence?: () => Promise<AudioEvidenceFlushResult>;
}

export interface PracticeLifecycleError {
    action: "start" | "pause" | "resume" | "end";
    message: string;
    guidance: string;
}

export type PracticeAudioEvidenceStatus =
    | { status: "idle"; message: string | null; error: string | null }
    | { status: "flushing"; message: string; error: string | null }
    | { status: "completed"; message: string; error: string | null }
    | { status: "failed"; message: string; error: string | null }
    | { status: "timed_out"; message: string; error: string | null };

export type PracticeReportTransition =
    | { status: "idle"; secondsRemaining: number; message: string | null }
    | { status: "preparing"; secondsRemaining: number; message: string }
    | { status: "ready"; secondsRemaining: number; message: string }
    | { status: "staying"; secondsRemaining: number; message: string };

function buildAudioEvidenceStatus(
    result: AudioEvidenceFlushResult,
): PracticeAudioEvidenceStatus {
    if (result.status === "completed") {
        return {
            status: "completed",
            message: "音频证据已保存，正在进入报告页。",
            error: null,
        };
    }

    if (result.status === "timed_out") {
        return {
            status: "timed_out",
            message: "音频证据保存超时，本次报告可能缺少最后一段录音留痕。",
            error: result.error,
        };
    }

    if (result.status === "failed") {
        return {
            status: "failed",
            message: "音频证据保存失败，本次报告会继续生成，但回放或证据完整度可能受影响。",
            error: result.error,
        };
    }

    return {
        status: "completed",
        message: "未检测到正在上传的音频留痕，正在进入报告页。",
        error: null,
    };
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
    const [audioEvidenceStatus, setAudioEvidenceStatus] = React.useState<PracticeAudioEvidenceStatus>({
        status: "idle",
        message: null,
        error: null,
    });
    const [reportTransition, setReportTransition] = React.useState<PracticeReportTransition>({
        status: "idle",
        secondsRemaining: 0,
        message: null,
    });
    const reportNavigationTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
    const reportCountdownTimerRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
    const hasStartedSessionRef = React.useRef(false);
    const hasNavigatedToReportRef = React.useRef(false);
    const hasStoppedRecordingForEndRef = React.useRef(false);

    const isSessionTerminal = sessionStatus === "completed" || sessionStatus === "scoring";
    const isSessionPaused = sessionStatus === "paused";
    const canToggleLifecycle =
        !isSessionTerminal
        && (sessionStatus === "in_progress" || sessionStatus === "paused")
        && !isEndingSession
        && pendingLifecycleAction === null;
    const clearReportTimers = React.useCallback(() => {
        if (reportNavigationTimerRef.current) {
            clearTimeout(reportNavigationTimerRef.current);
            reportNavigationTimerRef.current = null;
        }
        if (reportCountdownTimerRef.current) {
            clearInterval(reportCountdownTimerRef.current);
            reportCountdownTimerRef.current = null;
        }
    }, []);

    const viewReportNow = React.useCallback(() => {
        clearReportTimers();
        router.push(`/practice/${sessionId}/report`);
    }, [clearReportTimers, router, sessionId]);

    const stayOnPracticePage = React.useCallback(() => {
        clearReportTimers();
        setReportTransition({
            status: "staying",
            secondsRemaining: 0,
            message: "已取消自动跳转，你可以继续查看最后的对话内容。",
        });
    }, [clearReportTimers]);


    React.useEffect(() => {
        clearReportTimers();
        hasStartedSessionRef.current = false;
        hasNavigatedToReportRef.current = false;
        hasStoppedRecordingForEndRef.current = false;
        setIsEndingSession(false);
        setPendingLifecycleAction(null);
        setLifecycleError(null);
        setAudioEvidenceStatus({
            status: "idle",
            message: null,
            error: null,
        });
        setReportTransition({
            status: "idle",
            secondsRemaining: 0,
            message: null,
        });
    }, [clearReportTimers, sessionId]);

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
        setReportTransition({
            status: "preparing",
            secondsRemaining: 0,
            message: "正在保存收尾证据，完成后可查看报告。",
        });

        const scheduleReportTransition = () => {
            const delaySeconds = practiceUxConfig.sessionEndRedirectDelaySeconds;
            if (delaySeconds <= 0) {
                viewReportNow();
                return;
            }

            setReportTransition({
                status: "ready",
                secondsRemaining: delaySeconds,
                message: `报告已准备好。你可以继续查看最后一条对话，或等待 ${delaySeconds} 秒后自动进入报告。`,
            });

            reportCountdownTimerRef.current = setInterval(() => {
                setReportTransition((current) => {
                    if (current.status !== "ready") {
                        return current;
                    }
                    const nextSeconds = Math.max(0, current.secondsRemaining - 1);
                    return {
                        ...current,
                        secondsRemaining: nextSeconds,
                        message: `报告已准备好。你可以继续查看最后一条对话，或等待 ${nextSeconds} 秒后自动进入报告。`,
                    };
                });
            }, 1000);

            reportNavigationTimerRef.current = setTimeout(() => {
                viewReportNow();
            }, delaySeconds * 1000);
        };

        const finishAndPrepareReport = async () => {
            if (isRecordingRef.current && !hasStoppedRecordingForEndRef.current) {
                stopRecording();
                isRecordingRef.current = false;
                hasStoppedRecordingForEndRef.current = true;
            }

            if (flushAudioEvidence) {
                setAudioEvidenceStatus({
                    status: "flushing",
                    message: "正在保存最后一段音频证据，完成后进入报告页。",
                    error: null,
                });

                try {
                    const flushResult = await flushAudioEvidence();
                    setAudioEvidenceStatus(buildAudioEvidenceStatus(flushResult));
                } catch (error) {
                    const message = getApiErrorMessage(error);
                    debug.warn("[PracticeSession] Audio evidence flush failed before report navigation", {
                        sessionId,
                        error,
                        message,
                    });
                    setAudioEvidenceStatus({
                        status: "failed",
                        message: "音频证据保存失败，本次报告会继续生成，但回放或证据完整度可能受影响。",
                        error: message,
                    });
                }
            }

            scheduleReportTransition();
        };

        void finishAndPrepareReport();

        return () => {
            // Timers stay active across normal re-renders; session reset/user actions clear them explicitly.
        };
    }, [flushAudioEvidence, isRecordingRef, isSessionTerminal, sessionId, stopRecording, viewReportNow]);

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

        if (isRecordingRef.current && !hasStoppedRecordingForEndRef.current) {
            stopRecording();
            isRecordingRef.current = false;
            hasStoppedRecordingForEndRef.current = true;
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
        audioEvidenceStatus,
        reportTransition,
        viewReportNow,
        stayOnPracticePage,
        isEndingSession,
        isSessionPaused,
        isSessionTerminal,
        lifecycleError,
        pendingLifecycleAction,
    };
}
