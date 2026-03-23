import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HistoryPage from "./page";

const {
    getMyHistoryMock,
    getHistoryStatisticsMock,
    getHistoryTrendsMock,
} = vi.hoisted(() => ({
    getMyHistoryMock: vi.fn(),
    getHistoryStatisticsMock: vi.fn(),
    getHistoryTrendsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            user: {
                ...actual.api.user,
                getMyHistory: getMyHistoryMock,
            },
            dashboard: {
                ...actual.api.dashboard,
                getHistoryStatistics: getHistoryStatisticsMock,
                getHistoryTrends: getHistoryTrendsMock,
            },
        },
    };
});

describe("HistoryPage", () => {
    beforeEach(() => {
        getMyHistoryMock.mockReset();
        getHistoryStatisticsMock.mockReset();
        getHistoryTrendsMock.mockReset();
    });

    it("shows the projection-backed score and report action even when report_status is still pending", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-1",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 180,
                    overall_score: 81,
                    report_status: "pending",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: { complete: true },
                    effectiveness_snapshot: null,
                    feedback_summary: null,
                    stage_summary: [],
                    main_issue: null,
                    next_goal: null,
                },
            ],
            total: 1,
            page: 1,
            page_size: 50,
            total_pages: 1,
        });
        getHistoryStatisticsMock.mockResolvedValue({
            total_sessions: 1,
            evaluable_sessions: 1,
            not_evaluable_sessions: 0,
            average_score: 81,
            best_score: 81,
            total_practice_time_seconds: 180,
            total_practice_time_minutes: 3,
        });
        getHistoryTrendsMock.mockResolvedValue([
            {
                session_id: "session-1",
                date: "2026-03-23T00:00:00Z",
                overall_score: 81,
                evaluable: true,
                not_evaluable_reason: null,
                evidence_completeness: { complete: true },
                stage_summary: [],
                main_issue: null,
                next_goal: null,
            },
        ]);

        render(<HistoryPage />);

        await waitFor(() => {
            expect(getMyHistoryMock).toHaveBeenCalled();
        });

        const score = await screen.findByTestId("history-score-session-1");
        expect(score.textContent).toContain("81");
        const reportButton = screen.getByRole("button", { name: "报告" }) as HTMLButtonElement;
        expect(reportButton.disabled).toBe(false);
    });

    it("surfaces a not-evaluable session instead of collapsing it into a generic pending state", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-2",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 120,
                    overall_score: null,
                    report_status: "pending",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: false,
                    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
                    evidence_completeness: {
                        complete: false,
                        missing_fields: ["closing_stage"],
                    },
                    effectiveness_snapshot: null,
                    feedback_summary: null,
                    stage_summary: [],
                    main_issue: null,
                    next_goal: null,
                },
            ],
            total: 1,
            page: 1,
            page_size: 50,
            total_pages: 1,
        });
        getHistoryStatisticsMock.mockResolvedValue({
            total_sessions: 1,
            evaluable_sessions: 0,
            not_evaluable_sessions: 1,
            average_score: 0,
            best_score: 0,
            total_practice_time_seconds: 120,
            total_practice_time_minutes: 2,
        });
        getHistoryTrendsMock.mockResolvedValue([]);

        render(<HistoryPage />);

        expect(await screen.findByText("不可评估")).toBeTruthy();
        expect(screen.getByText("对话轮次不足，暂无法形成稳定评估。")).toBeTruthy();
        expect(screen.queryByText("评分中")).toBeNull();
    });
});
