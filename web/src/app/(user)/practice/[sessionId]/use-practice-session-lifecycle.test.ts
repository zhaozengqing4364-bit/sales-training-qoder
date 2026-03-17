import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
                isConnected: true,
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
                    isConnected: true,
                    isRecordingRef: { current: false },
                    stopRecording: vi.fn(),
                }),
            {
                initialProps: {
                    sessionStatus: "in_progress" as const,
                },
            },
        );

        await act(async () => {
            await result.current.handleTogglePauseResume();
        });

        expect(controlLifecycle).toHaveBeenCalledWith("session-2", "pause");

        rerender({ sessionStatus: "paused" });

        await act(async () => {
            await result.current.handleTogglePauseResume();
        });

        expect(controlLifecycle).toHaveBeenNthCalledWith(2, "session-2", "resume");
    });

    it("ends session, stops recording and navigates to report page", async () => {
        const stopRecording = vi.fn();
        const { result } = renderHook(() =>
            usePracticeSessionLifecycle({
                sessionId: "session-3",
                connectionState: "connected",
                sessionStatus: "in_progress",
                isConnected: true,
                isRecordingRef: { current: true },
                stopRecording,
            }),
        );

        await act(async () => {
            await result.current.handleEndSession();
        });

        expect(endSession).toHaveBeenCalledWith("session-3");
        expect(stopRecording).toHaveBeenCalledTimes(1);
        expect(generateComprehensiveReport).toHaveBeenCalledWith("session-3");
        expect(routerPush).toHaveBeenCalledWith("/practice/session-3/report");
    });
});
