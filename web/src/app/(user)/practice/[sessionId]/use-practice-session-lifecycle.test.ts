import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionStatus } from "@/lib/api/types";
import { usePracticeSessionLifecycle } from "./use-practice-session-lifecycle";

const {
    routerPush,
    startSession,
    controlLifecycle,
    endSession,
    generateComprehensiveReport,
} = vi.hoisted(() => ({
    routerPush: vi.fn(),
    startSession: vi.fn(),
    controlLifecycle: vi.fn(),
    endSession: vi.fn(),
    generateComprehensiveReport: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: routerPush,
    }),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        practice: {
            startSession,
            controlLifecycle,
            endSession,
        },
        admin: {
            generateComprehensiveReport,
        },
    },
    getApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : "请求失败，请稍后重试。"),
}));

describe("usePracticeSessionLifecycle", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        startSession.mockResolvedValue(undefined);
        controlLifecycle.mockResolvedValue(undefined);
        endSession.mockResolvedValue(undefined);
        generateComprehensiveReport.mockResolvedValue(undefined);
    });

    it("starts preparing sessions via REST once websocket is connected", async () => {
        renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-1",
                connectionState: "connected",
                sessionStatus: "preparing",
                isRecordingRef: { current: false },
                stopRecording: vi.fn(),
            }),
        );

        await waitFor(() => {
            expect(startSession).toHaveBeenCalledWith("session-1");
        });
        expect(controlLifecycle).not.toHaveBeenCalled();
    });

    it("surfaces automatic start failures and allows retry", async () => {
        startSession
            .mockRejectedValueOnce(new Error("会话状态异常"))
            .mockResolvedValueOnce(undefined);

        const { result } = renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-start",
                connectionState: "connected",
                sessionStatus: "preparing",
                isRecordingRef: { current: false },
                stopRecording: vi.fn(),
            }),
        );

        await waitFor(() => {
            expect(result.current.lifecycleError).toEqual({
                action: "start",
                message: "启动训练失败，可重试。会话状态异常",
                guidance: "请先确认连接正常，再点击“重试启动”；如果仍失败，可刷新页面后重新进入训练。",
            });
        });

        await act(async () => {
            await result.current.handleStartSession();
        });

        expect(startSession).toHaveBeenCalledTimes(2);
        expect(result.current.lifecycleError).toBeNull();
    });

    it("pauses and resumes through REST lifecycle only", async () => {
        const { result, rerender } = renderHook(
            ({ sessionStatus }) =>
                usePracticeSessionLifecycle({
                    sessionId: "session-2",
                    connectionState: "connected",
                    sessionStatus,
                    isRecordingRef: { current: false },
                    stopRecording: vi.fn(),
                }),
            {
                initialProps: {
                    sessionStatus: "in_progress" as SessionStatus,
                },
            },
        );

        await act(async () => {
            await result.current.handleTogglePauseResume();
        });

        expect(controlLifecycle).toHaveBeenCalledWith("session-2", "pause");

        rerender({ sessionStatus: "paused" as SessionStatus });

        await act(async () => {
            await result.current.handleTogglePauseResume();
        });

        expect(controlLifecycle).toHaveBeenNthCalledWith(2, "session-2", "resume");
    });

    it("surfaces learner-facing guidance when pausing fails", async () => {
        controlLifecycle.mockRejectedValueOnce(new Error("后端暂时不可用"));
        const stopRecording = vi.fn();

        const { result } = renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-2b",
                connectionState: "connected",
                sessionStatus: "in_progress",
                isRecordingRef: { current: true },
                stopRecording,
            }),
        );

        await act(async () => {
            await result.current.handleTogglePauseResume();
        });

        expect(stopRecording).toHaveBeenCalledTimes(1);
        expect(result.current.pendingLifecycleAction).toBeNull();
        expect(result.current.lifecycleError).toEqual({
            action: "pause",
            message: "暂停失败，请再试一次。",
            guidance: "你可以先继续当前对话，稍后再暂停；如果按钮持续无响应，再结束本次练习后重新进入。",
        });
    });

    it("surfaces learner-facing guidance when resuming fails", async () => {
        controlLifecycle.mockRejectedValueOnce(new Error("网络连接失败"));

        const { result } = renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-2c",
                connectionState: "connected",
                sessionStatus: "paused",
                isRecordingRef: { current: false },
                stopRecording: vi.fn(),
            }),
        );

        await act(async () => {
            await result.current.handleTogglePauseResume();
        });

        expect(result.current.pendingLifecycleAction).toBeNull();
        expect(result.current.lifecycleError).toEqual({
            action: "resume",
            message: "继续失败，请确认连接后再试一次。",
            guidance: "如果仍无法恢复，请先重新连接或刷新页面，再回到当前会话继续练习。",
        });
    });

    it("waits for server terminal status before navigating to the report page", async () => {
        const stopRecording = vi.fn();
        const { result, rerender } = renderHook(
            ({ sessionStatus }) =>
                usePracticeSessionLifecycle({
                    sessionId: "session-3",
                    connectionState: "connected",
                    sessionStatus,
                    isRecordingRef: { current: true },
                    stopRecording,
                }),
            {
                initialProps: {
                    sessionStatus: "in_progress" as SessionStatus,
                },
            },
        );

        await act(async () => {
            await result.current.handleEndSession();
        });

        expect(endSession).toHaveBeenCalledWith("session-3");
        expect(stopRecording).toHaveBeenCalledTimes(1);
        expect(generateComprehensiveReport).not.toHaveBeenCalled();
        expect(result.current.isEndingSession).toBe(true);
        expect(routerPush).not.toHaveBeenCalled();

        rerender({ sessionStatus: "scoring" as SessionStatus });

        await waitFor(() => {
            expect(routerPush).toHaveBeenCalledWith("/practice/session-3/report");
        });
    });

    it("waits for bounded audio evidence flush before navigating to the report page", async () => {
        const stopRecording = vi.fn();
        let resolveFlush: ((value: { status: "completed"; pendingUploads: number; error: null }) => void) | null = null;
        const flushAudioEvidence = vi.fn(() => new Promise<{ status: "completed"; pendingUploads: number; error: null }>((resolve) => {
            resolveFlush = resolve;
        }));

        const { result, rerender } = renderHook(
            ({ sessionStatus }) =>
                usePracticeSessionLifecycle({
                    sessionId: "session-flush",
                    connectionState: "connected",
                    sessionStatus,
                    isRecordingRef: { current: true },
                    stopRecording,
                    flushAudioEvidence,
                }),
            {
                initialProps: {
                    sessionStatus: "in_progress" as SessionStatus,
                },
            },
        );

        await act(async () => {
            await result.current.handleEndSession();
        });

        rerender({ sessionStatus: "scoring" as SessionStatus });

        await waitFor(() => {
            expect(flushAudioEvidence).toHaveBeenCalledTimes(1);
        });
        expect(stopRecording).toHaveBeenCalledTimes(1);
        expect(result.current.audioEvidenceStatus).toEqual({
            status: "flushing",
            message: "正在保存最后一段音频证据，完成后进入报告页。",
            error: null,
        });
        expect(routerPush).not.toHaveBeenCalled();

        await act(async () => {
            resolveFlush?.({ status: "completed", pendingUploads: 0, error: null });
        });

        await waitFor(() => {
            expect(routerPush).toHaveBeenCalledWith("/practice/session-flush/report");
        });
        expect(result.current.audioEvidenceStatus).toEqual({
            status: "completed",
            message: "音频证据已保存，正在进入报告页。",
            error: null,
        });
    });

    it("continues to the report with an explicit audio evidence timeout explanation", async () => {
        const flushAudioEvidence = vi.fn().mockResolvedValue({
            status: "timed_out",
            pendingUploads: 1,
            error: "segment 3 still pending",
        });

        const { result, rerender } = renderHook(
            ({ sessionStatus }) =>
                usePracticeSessionLifecycle({
                    sessionId: "session-flush-timeout",
                    connectionState: "connected",
                    sessionStatus,
                    isRecordingRef: { current: false },
                    stopRecording: vi.fn(),
                    flushAudioEvidence,
                }),
            {
                initialProps: {
                    sessionStatus: "in_progress" as SessionStatus,
                },
            },
        );

        rerender({ sessionStatus: "completed" as SessionStatus });

        await waitFor(() => {
            expect(routerPush).toHaveBeenCalledWith("/practice/session-flush-timeout/report");
        });
        expect(result.current.audioEvidenceStatus).toEqual({
            status: "timed_out",
            message: "音频证据保存超时，本次报告可能缺少最后一段录音留痕。",
            error: "segment 3 still pending",
        });
    });

    it("stays on the practice page and preserves actionable backend detail when ending fails", async () => {
        endSession.mockRejectedValueOnce(new Error("报告生成超时，请稍后再试。"));

        const { result } = renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-4",
                connectionState: "connected",
                sessionStatus: "in_progress",
                isRecordingRef: { current: false },
                stopRecording: vi.fn(),
            }),
        );

        await act(async () => {
            await result.current.handleEndSession();
        });

        expect(routerPush).not.toHaveBeenCalled();
        expect(result.current.isEndingSession).toBe(false);
        expect(result.current.lifecycleError).toEqual({
            action: "end",
            message: "结束失败，请再试一次。报告生成超时，请稍后再试。",
            guidance: "请先确认连接正常，再点击“结束练习”；如果仍失败，可先重新连接后重试结束。",
        });
    });

    it("stays on the practice page and exposes the end error when ending fails", async () => {
        endSession.mockRejectedValueOnce(new Error("结束失败，请重试"));

        const { result } = renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-4",
                connectionState: "connected",
                sessionStatus: "in_progress",
                isRecordingRef: { current: false },
                stopRecording: vi.fn(),
            }),
        );

        await act(async () => {
            await result.current.handleEndSession();
        });

        expect(routerPush).not.toHaveBeenCalled();
        expect(result.current.isEndingSession).toBe(false);
        expect(result.current.lifecycleError).toEqual({
            action: "end",
            message: "结束失败，请再试一次。",
            guidance: "请先确认连接正常，再点击“结束练习”；如果仍失败，可先重新连接后重试结束。",
        });
    });
});
