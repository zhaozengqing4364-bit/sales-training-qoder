import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import NewcomerActivityPage from "./page";

const { getActivityMock } = vi.hoisted(() => ({
    getActivityMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getActivity: getActivityMock,
            },
        },
    };
});

vi.mock("@/components/newcomer-training/activity-shell", () => ({
    ActivityShell: ({ detail }: { detail: { activity: { title: string } } }) => (
        <div>活动内容：{detail.activity.title}</div>
    ),
}));
vi.mock("@/lib/newcomer-training/ux-events", () => ({ trackFoundationUxEvent: vi.fn() }));

function detail(title = "产品知识学习"): FoundationActivityWorkspace {
    return {
        contract_version: "activity_workspace_v1",
        generated_at: "2026-07-16T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_activity", "execute_activity"],
        enrollment_version: 1,
        activity: {
            id: "product-lesson",
            type: "lesson",
            title,
            objective: "掌握产品知识",
            why_it_matters: "为客户沟通打基础",
            steps: ["学习", "检查", "完成"],
            success_criteria: ["完成必修检查点"],
            estimated_minutes: 10,
        },
        attempt: null,
        runner: {
            kind: "lesson", detail_id: "not-started", status: "not_started", version: 0,
            title, objectives: [], key_concepts: [], examples: [], checkpoints: [], practice_hints: [], progress: null,
        },
        task: null,
        outcome: null,
        available_commands: ["start"],
        recovery: { input_preserved: true, refresh_on_version_conflict: true, retry_from_current_activity: true },
    };
}

describe("NewcomerActivityPage", () => {
    beforeEach(() => {
        getActivityMock.mockReset();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("shows a slow-load explanation, times out, and retries successfully", async () => {
        vi.useFakeTimers();
        getActivityMock
            .mockImplementationOnce(() => new Promise(() => {}))
            .mockResolvedValueOnce(detail());

        await act(async () => {
            render(<NewcomerActivityPage params={Promise.resolve({ activityId: "product-lesson" })} />);
        });
        await act(async () => { await vi.advanceTimersByTimeAsync(1_100); });
        expect(screen.getByRole("status").textContent).toContain("正在获取任务材料和当前进度");
        await act(async () => { await vi.advanceTimersByTimeAsync(9_000); });
        expect(screen.getByRole("alert").textContent).toContain("加载时间过长");

        fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
        await act(async () => { await Promise.resolve(); });

        expect(screen.getByText("活动内容：产品知识学习")).toBeTruthy();
        expect(getActivityMock).toHaveBeenCalledTimes(2);
    });

    it("ignores a stale response after the activity route changes", async () => {
        let resolveFirst: ((value: FoundationActivityWorkspace) => void) | undefined;
        getActivityMock
            .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
            .mockResolvedValueOnce(detail("客户理解学习"));

        let rerender: ReturnType<typeof render>["rerender"] | undefined;
        await act(async () => {
            ({ rerender } = render(<NewcomerActivityPage params={Promise.resolve({ activityId: "first" })} />));
        });
        await act(async () => {
            rerender?.(<NewcomerActivityPage params={Promise.resolve({ activityId: "second" })} />);
        });

        expect(await screen.findByText("活动内容：客户理解学习")).toBeTruthy();
        act(() => resolveFirst?.(detail("过期的产品知识任务")));
        await waitFor(() => expect(screen.queryByText("活动内容：过期的产品知识任务")).toBeNull());
    });

    it("waits for an in-flight task refresh before scheduling another poll", async () => {
        vi.useFakeTimers();
        let resolvePoll: ((value: FoundationActivityWorkspace) => void) | undefined;
        getActivityMock
            .mockResolvedValueOnce({ ...detail(), task: { task_id: "task-1", state: "processing" } })
            .mockImplementationOnce(() => new Promise((resolve) => { resolvePoll = resolve; }));

        await act(async () => {
            render(<NewcomerActivityPage params={Promise.resolve({ activityId: "product-lesson" })} />);
            await Promise.resolve();
        });
        await act(async () => { await vi.advanceTimersByTimeAsync(9_000); });
        expect(getActivityMock).toHaveBeenCalledTimes(2);

        await act(async () => {
            resolvePoll?.(detail());
            await Promise.resolve();
        });
        expect(screen.getByText("活动内容：产品知识学习")).toBeTruthy();
    });
});
