import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TeamDashboardPage, { rangeDates } from "./page";

const apiMock = vi.hoisted(() => ({
    getTeamScope: vi.fn(),
    getTeamWorkbench: vi.fn(),
    listJourneys: vi.fn(),
    replace: vi.fn(),
    searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: apiMock.replace }),
    useSearchParams: () => apiMock.searchParams,
}));
vi.mock("@/hooks/use-current-user", () => ({ useCurrentUser: () => ({ data: { role: "training_manager" } }) }));
vi.mock("@/lib/api/client", () => ({
    getApiErrorMessage: (error: unknown) => String(error),
    api: {
        supervisor: { getTeamScope: apiMock.getTeamScope, getTeamWorkbench: apiMock.getTeamWorkbench },
        admin: { newcomerTraining: { listJourneys: apiMock.listJourneys } },
    },
}));

describe("TeamDashboardPage", () => {
    beforeEach(() => {
        vi.useRealTimers();
        apiMock.searchParams = new URLSearchParams();
        apiMock.replace.mockReset();
        apiMock.getTeamScope.mockReset();
        apiMock.getTeamWorkbench.mockReset();
        apiMock.listJourneys.mockReset();
        apiMock.getTeamScope.mockResolvedValue({
            teams: [{ team_id: "team-1", code: "east", name: "华东销售一组", leaders: [] }],
            members: [{ team_id: "team-1", learner_id: "learner-1", learner_name: "张三", email: "zhang@example.com" }],
        });
        apiMock.getTeamWorkbench.mockResolvedValue({
            extra_task_progress: { total_tasks: 2, completed_tasks: 1, completion_rate: 50, by_status: { completed: 1, assigned: 1 } },
            risk_groups: [],
            common_issues: [],
            learners: [{
                learner_id: "learner-1",
                learner_name: "张三",
                extra_task_progress: { total_tasks: 2, completed_tasks: 1, completion_rate: 50, by_status: {} },
                risk_labels: ["产品准确性"],
            }],
        });
        apiMock.listJourneys.mockResolvedValue({
            items: [{
                learner_id: "learner-1",
                learner_name: "张三",
                team: { team_id: "team-1", code: "east", name: "华东销售一组" },
                summary: {
                    path_revision_id: "rev-1",
                    path_title: "新人训练",
                    current_phase: { phase_id: "p1", title: "阶段一", status: "in_progress" },
                    progress: { completed: false, completed_count: 1, total_required: 3, percent: 33 },
                    primary_next_action: null,
                    risk_labels: [],
                },
            }],
            total: 1,
        });
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("明确呈现只读范围且不提供任务写入口", async () => {
        render(<TeamDashboardPage />);
        await waitFor(() => expect(screen.getByRole("heading", { name: "团队训练进展" })).toBeTruthy());
        expect(screen.getByText(/本期不能发布或修改任务/)).toBeTruthy();
        expect(screen.queryByRole("button", { name: /发布任务|分配任务/ })).toBeNull();
        expect(screen.queryByRole("combobox", { name: "团队" })).toBeNull();
    });

    it("自定义周期与上一同期等长且不重叠", () => {
        const dates = rangeDates("custom", "2026-06-01", "2026-06-30");
        const currentStart = new Date(dates.current.date_from).getTime();
        const currentEnd = new Date(dates.current.date_to).getTime();
        const previousStart = new Date(dates.previous.date_from).getTime();
        const previousEnd = new Date(dates.previous.date_to).getTime();
        expect(currentEnd - currentStart).toBe(previousEnd - previousStart);
        expect(previousEnd).toBeLessThan(currentStart);
    });

    it("搜索输入防抖至少 300ms 后才写入 URL", async () => {
        render(<TeamDashboardPage />);
        await waitFor(() => expect(screen.getByPlaceholderText("搜索成员姓名")).toBeTruthy());
        vi.useFakeTimers();
        apiMock.replace.mockClear();
        fireEvent.change(screen.getByPlaceholderText("搜索成员姓名"), { target: { value: "张" } });
        await act(async () => { vi.advanceTimersByTime(299); });
        expect(apiMock.replace).not.toHaveBeenCalled();
        await act(async () => { vi.advanceTimersByTime(1); });
        expect(apiMock.replace).toHaveBeenCalledTimes(1);
        expect(String(apiMock.replace.mock.calls[0]?.[0])).toContain("q=");
    });

    it("上一期失败时不展示虚假百分点比较", async () => {
        apiMock.getTeamWorkbench
            .mockResolvedValueOnce({
                extra_task_progress: { total_tasks: 2, completed_tasks: 1, completion_rate: 50, by_status: {} },
                risk_groups: [],
                common_issues: [],
                learners: [],
            })
            .mockRejectedValueOnce(new Error("previous unavailable"));
        render(<TeamDashboardPage />);
        await waitFor(() => expect(screen.getByText("上一同期暂不可用，无法比较")).toBeTruthy());
        expect(screen.queryByText(/较上一同期/)).toBeNull();
    });

    it("刷新时保留已有成员行且显示更新状态", async () => {
        render(<TeamDashboardPage />);
        await waitFor(() => expect(screen.getByText("张三")).toBeTruthy());
        apiMock.listJourneys.mockImplementation(() => new Promise(() => undefined));
        apiMock.getTeamWorkbench.mockImplementation(() => new Promise(() => undefined));
        await userEvent.click(screen.getByRole("button", { name: /刷新/ }));
        await waitFor(() => expect(screen.getByRole("status").textContent).toContain("正在更新团队数据"));
        expect(screen.getByText("张三")).toBeTruthy();
        expect(document.querySelectorAll(".h-24").length).toBe(0);
    });

    it("首次加载在业务数据返回前保持页面 Skeleton", async () => {
        let resolveJourneys: ((value: unknown) => void) | undefined;
        const workbenchResolvers: Array<(value: unknown) => void> = [];
        apiMock.listJourneys.mockImplementation(() => new Promise((resolve) => { resolveJourneys = resolve; }));
        apiMock.getTeamWorkbench.mockImplementation(() => new Promise((resolve) => { workbenchResolvers.push(resolve); }));
        render(<TeamDashboardPage />);
        await waitFor(() => expect(apiMock.getTeamScope).toHaveBeenCalled());
        await waitFor(() => expect(apiMock.listJourneys).toHaveBeenCalled());
        await waitFor(() => expect(workbenchResolvers.length).toBe(2));
        // Scope already resolved, but journeys/workbench still pending → must stay on Skeleton.
        expect(screen.queryByRole("heading", { name: "团队训练进展" })).toBeNull();
        expect(document.querySelectorAll(".h-24").length).toBeGreaterThan(0);
        const emptyWorkbench = {
            extra_task_progress: { total_tasks: 0, completed_tasks: 0, completion_rate: 0, by_status: {} },
            risk_groups: [],
            common_issues: [],
            learners: [],
        };
        await act(async () => {
            resolveJourneys?.({
                items: [{
                    learner_id: "learner-1",
                    learner_name: "张三",
                    team: { team_id: "team-1", code: "east", name: "华东销售一组" },
                    summary: {
                        path_revision_id: "rev-1",
                        path_title: "新人训练",
                        current_phase: null,
                        progress: { completed: false, completed_count: 0, total_required: 1, percent: 0 },
                        primary_next_action: null,
                        risk_labels: [],
                    },
                }],
                total: 1,
            });
            workbenchResolvers.forEach((resolve) => resolve(emptyWorkbench));
        });
        await waitFor(() => expect(screen.getByRole("heading", { name: "团队训练进展" })).toBeTruthy());
        expect(document.querySelectorAll(".h-24").length).toBe(0);
    });
});
