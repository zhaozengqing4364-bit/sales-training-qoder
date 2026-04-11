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
