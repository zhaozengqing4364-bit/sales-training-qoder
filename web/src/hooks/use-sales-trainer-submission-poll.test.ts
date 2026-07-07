import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SalesTrainerAudioSubmission } from "@/lib/api/types";

const { getAudioSubmissionMock } = vi.hoisted(() => ({
    getAudioSubmissionMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        salesTrainer: {
            getAudioSubmission: getAudioSubmissionMock,
        },
    },
    getApiErrorMessage: (err: unknown) =>
        err instanceof Error ? err.message : String(err),
}));

import { useSalesTrainerSubmissionPoll } from "./use-sales-trainer-submission-poll";

const mockSubmission = (
    overrides: Partial<SalesTrainerAudioSubmission> = {},
): SalesTrainerAudioSubmission =>
    ({
        submission_id: "sub-1",
        unit_id: "unit-1",
        user_id: "user-1",
        purpose: "general_audio_scoring",
        original_filename: "pitch.wav",
        content_type: "audio/wav",
        size_bytes: 1024,
        storage_key: "/tmp/pitch.wav",
        status: "scoring",
        created_at: "2026-07-07T00:00:00Z",
        ...overrides,
    }) as unknown as SalesTrainerAudioSubmission;

/** 在 fake timers 下推进微任务 + 宏任务，让异步 fetch 链路收敛。 */
async function settle(ms = 0) {
    await act(async () => {
        await vi.advanceTimersByTimeAsync(ms);
    });
}

describe("useSalesTrainerSubmissionPoll", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        vi.clearAllMocks();
    });
    afterEach(() => {
        vi.useRealTimers();
    });

    it("stops polling when status reaches a terminal state (scored)", async () => {
        getAudioSubmissionMock.mockResolvedValue(
            mockSubmission({ status: "scored" }),
        );

        const { result } = renderHook(() =>
            useSalesTrainerSubmissionPoll("sub-1"),
        );

        await settle(0);

        expect(result.current.submission?.status).toBe("scored");
        expect(result.current.isPolling).toBe(false);
        expect(result.current.timedOut).toBe(false);
        expect(result.current.error).toBeNull();
    });

    it("stops polling on error and surfaces the message", async () => {
        getAudioSubmissionMock.mockRejectedValue(new Error("network down"));

        const { result } = renderHook(() =>
            useSalesTrainerSubmissionPoll("sub-1"),
        );

        await settle(0);

        expect(result.current.error).toBe("network down");
        expect(result.current.isPolling).toBe(false);
        expect(result.current.submission).toBeNull();
    });

    it("stops polling with a timeout hint after totalTimeoutMs when still non-terminal", async () => {
        getAudioSubmissionMock.mockResolvedValue(
            mockSubmission({ status: "scoring" }),
        );

        const { result } = renderHook(() =>
            useSalesTrainerSubmissionPoll("sub-1", { totalTimeoutMs: 5_000 }),
        );

        // 首次拉取进入轮询
        await settle(0);
        expect(result.current.isPolling).toBe(true);

        // 推进超过总超时（含若干轮间隔），应停止并提示
        await settle(6_000);

        expect(result.current.timedOut).toBe(true);
        expect(result.current.isPolling).toBe(false);
        expect(result.current.error).toContain("评分耗时较长");
    });

    it("refresh resets timeout and resumes polling", async () => {
        getAudioSubmissionMock.mockResolvedValue(
            mockSubmission({ status: "scoring" }),
        );

        const { result } = renderHook(() =>
            useSalesTrainerSubmissionPoll("sub-1", { totalTimeoutMs: 5_000 }),
        );

        await settle(0);
        expect(result.current.isPolling).toBe(true);
        await settle(6_000);
        expect(result.current.timedOut).toBe(true);

        // 手动 refresh 应重置超时状态，重新进入轮询
        await act(async () => {
            await result.current.refresh();
        });
        await settle(0);

        expect(result.current.timedOut).toBe(false);
        expect(result.current.isPolling).toBe(true);
    });
});
