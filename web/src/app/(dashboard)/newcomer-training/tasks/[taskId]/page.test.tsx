import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FoundationTaskStatus } from "@/lib/api/types/newcomer-training";
import FoundationTaskPage from "./page";

const { getTask, requestTaskCancel } = vi.hoisted(() => ({
    getTask: vi.fn(),
    requestTaskCancel: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
    api: { newcomerTraining: { getTask, requestTaskCancel } },
    getApiErrorMessage: (cause: unknown) => cause instanceof Error ? cause.message : "请求失败",
}));
vi.mock("@/lib/newcomer-training/ux-events", () => ({ trackFoundationUxEvent: vi.fn() }));

function task(overrides: Partial<FoundationTaskStatus> = {}): FoundationTaskStatus {
    return {
        contract_version: "task_status_v1",
        task_id: "task-1",
        title: "录音评估",
        state: "running",
        state_label: "处理中",
        progress: { current: 1, total: 3, label: "正在转写录音" },
        can_cancel: true,
        retry_after: null,
        result_location: null,
        result_path: null,
        error: null,
        updated_at: "2026-07-17T10:00:00Z",
        ...overrides,
    };
}

describe("FoundationTaskPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getTask.mockResolvedValue(task());
        requestTaskCancel.mockResolvedValue(task({ state: "cancel_requested", state_label: "正在取消", can_cancel: false }));
    });

    afterEach(() => vi.useRealTimers());

    it("keeps the last durable status visible when a later refresh fails", async () => {
        vi.useFakeTimers();
        getTask
            .mockResolvedValueOnce(task())
            .mockRejectedValueOnce(new Error("网络暂时不可用"));

        await act(async () => {
            render(<FoundationTaskPage params={Promise.resolve({ taskId: "task-1" })} />);
            await Promise.resolve();
        });
        expect(screen.getByText("正在转写录音")).toBeTruthy();

        await act(async () => { await vi.advanceTimersByTimeAsync(3_000); });

        expect(screen.getByText("正在转写录音")).toBeTruthy();
        expect(screen.getByRole("status").textContent).toContain("已保留上次结果");
    });

    it("submits an idempotent cancellation request and shows the persisted state", async () => {
        await act(async () => {
            render(<FoundationTaskPage params={Promise.resolve({ taskId: "task-1" })} />);
            await Promise.resolve();
        });
        await screen.findByText("正在转写录音");

        fireEvent.click(screen.getByRole("button", { name: "取消后台任务" }));

        await waitFor(() => expect(requestTaskCancel).toHaveBeenCalledTimes(1));
        expect(typeof requestTaskCancel.mock.calls[0]?.[1]).toBe("string");
        expect(await screen.findByText("正在取消")).toBeTruthy();
    });

    it("links a completed task to its formal business result", async () => {
        getTask.mockResolvedValue(task({
            state: "succeeded",
            state_label: "已完成",
            can_cancel: false,
            result_path: "/newcomer-training/activities/audio-1",
        }));

        await act(async () => {
            render(<FoundationTaskPage params={Promise.resolve({ taskId: "task-1" })} />);
            await Promise.resolve();
        });

        const link = await screen.findByRole("link", { name: "查看业务结果" });
        expect(link.getAttribute("href")).toBe("/newcomer-training/activities/audio-1");
        expect(screen.queryByRole("button", { name: "刷新进度" })).toBeNull();
    });
});
