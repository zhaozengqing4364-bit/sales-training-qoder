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
        expect(result.current.lifecycleError).toBe("结束失败，请重试");
    });
});
