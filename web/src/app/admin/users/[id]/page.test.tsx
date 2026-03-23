import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UserDetailPage from "./page";

const {
    pushMock,
    getUserStatsMock,
    getUserSessionsMock,
    getUserProgressMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    getUserStatsMock: vi.fn(),
    getUserSessionsMock: vi.fn(),
    getUserProgressMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
        back: vi.fn(),
    }),
    useParams: () => ({
        id: "user-1",
    }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("recharts", () => ({
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    Line: () => <div />,
    XAxis: () => <div />,
    YAxis: () => <div />,
    CartesianGrid: () => <div />,
    Tooltip: () => <div />,
    Legend: () => <div />,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getUserStats: getUserStatsMock,
                getUserSessions: getUserSessionsMock,
                getUserProgress: getUserProgressMock,
            },
        },
    };
});

describe("UserDetailPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        getUserStatsMock.mockReset();
        getUserSessionsMock.mockReset();
        getUserProgressMock.mockReset();

        getUserStatsMock.mockResolvedValue({
            user: {
                id: "user-1",
                user_id: "user-1",
                display_name: "张三",
                email: "zhangsan@example.com",
                department: "销售一部",
                role: "user",
                is_active: true,
                status: "active",
                created_at: "2026-03-01T00:00:00Z",
                total_sessions: 2,
                total_duration_minutes: 8,
                average_score: 55,
            },
            statistics: {
                total_sessions: 2,
                completed_sessions: 2,
                completion_rate: 100,
                average_score: 55,
                best_score: 60,
                worst_score: 50,
                total_duration_minutes: 8,
                last_practice: "2026-03-23T09:00:00Z",
                unique_agents_used: 1,
                unique_personas_used: 1,
            },
            agent_usage: [],
            persona_usage: [],
        });
        getUserProgressMock.mockResolvedValue({
            trend_data: [],
            improvement_rate: 0,
            total_data_points: 0,
        });
    });

    it("renders unified preview copy and a report CTA for completed sessions", async () => {
        getUserSessionsMock.mockResolvedValue({
            items: [
                {
                    session_id: "session-1",
                    start_time: "2026-03-23T09:00:00Z",
                    end_time: "2026-03-23T09:04:00Z",
                    status: "completed",
                    duration_minutes: 4,
                    scenario_name: "大客户销售演练",
                    scenario_type: "sales",
                    agent_name: "销售教练",
                    persona_name: "采购经理",
                    scores: {
                        logic: 40,
                        accuracy: 50,
                        completeness: 60,
                        overall: 50,
                    },
                    interruption_count: 1,
                    overall_result: "fail",
                    evaluable: true,
                    not_evaluable_reason: null,
                    main_issue: {
                        issue_type: "main_capability_not_passed",
                        issue_text: "关键异议回应不够具体。",
                        recovery_rule: "先回应风险，再补证据。",
                    },
                    next_goal: {
                        goal_type: "single_next_goal",
                        goal_text: "下一轮先把异议处理说完整。",
                        rule: "至少完成 1 次完整异议回应。",
                    },
                    feedback_summary: "关键异议回应不够具体。",
                },
            ],
            total: 1,
            page: 1,
            page_size: 10,
            has_more: false,
        } as any);

        render(<UserDetailPage />);

        await waitFor(() => {
            expect(getUserSessionsMock).toHaveBeenCalledWith("user-1", { page: 1, page_size: 10 });
        });

        expect(await screen.findByText("关键异议回应不够具体。"))
            .toBeTruthy();
        expect(screen.getByText("下一轮先把异议处理说完整。"))
            .toBeTruthy();
        const reportLink = screen.getByRole("link", { name: "查看报告" }) as HTMLAnchorElement;
        expect(reportLink.getAttribute("href")).toBe("/practice/session-1/report");
    });
});
