import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "./page";

const {
    getOverviewMock,
    getTrendsMock,
    getAgentsMock,
    getLeaderboardMock,
    getManagerLiteListsMock,
    remindFromManagerLiteMock,
    exportReportMock,
    getDashboardMock,
} = vi.hoisted(() => ({
    getOverviewMock: vi.fn(),
    getTrendsMock: vi.fn(),
    getAgentsMock: vi.fn(),
    getLeaderboardMock: vi.fn(),
    getManagerLiteListsMock: vi.fn(),
    remindFromManagerLiteMock: vi.fn(),
    exportReportMock: vi.fn(),
    getDashboardMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            analytics: {
                ...actual.api.analytics,
                getOverview: getOverviewMock,
                getTrends: getTrendsMock,
                getAgents: getAgentsMock,
                getLeaderboard: getLeaderboardMock,
                getManagerLiteLists: getManagerLiteListsMock,
                remindFromManagerLite: remindFromManagerLiteMock,
                exportReport: exportReportMock,
            },
            analyticsOpen: {
                ...actual.api.analyticsOpen,
                getDashboard: getDashboardMock,
            },
        },
    };
});

vi.mock("@/components/analytics/TrendsChart", () => ({
    TrendsChart: ({ data }: { data: unknown[] }) => <div>TrendsChart:{data.length}</div>,
}));

vi.mock("@/components/analytics/ScoreDistributionChart", () => ({
    ScoreDistributionChart: () => <div>ScoreDistributionChart</div>,
}));

vi.mock("@/components/analytics/AgentRankingChart", () => ({
    AgentRankingChart: () => <div>AgentRankingChart</div>,
}));

vi.mock("@/components/analytics/LeaderboardTable", () => ({
    LeaderboardTable: ({ data }: { data: unknown[] }) => <div>LeaderboardTable:{data.length}</div>,
}));

vi.mock("@/components/admin/manager-lite-panel", () => ({
    ManagerLitePanel: ({ data }: { data: { not_passed: unknown[] } }) => (
        <div>ManagerLitePanel:{data.not_passed.length}</div>
    ),
}));

describe("AnalyticsPage", () => {
    beforeEach(() => {
        getOverviewMock.mockReset();
        getTrendsMock.mockReset();
        getAgentsMock.mockReset();
        getLeaderboardMock.mockReset();
        getManagerLiteListsMock.mockReset();
        remindFromManagerLiteMock.mockReset();
        exportReportMock.mockReset();
        getDashboardMock.mockReset();

        remindFromManagerLiteMock.mockResolvedValue({ sent: true, reminder_id: "rem-1", user_id: "user-1" });
        exportReportMock.mockResolvedValue(undefined);
        getDashboardMock.mockResolvedValue({
            total_sessions: 15,
            completed_sessions: 12,
            completion_rate: 80,
            average_scores: {
                logic: 72,
                accuracy: 74,
                completeness: 70,
                overall: 72,
            },
            engagement: {
                average_duration_seconds: 240,
                average_interruptions_per_session: 1,
            },
            quality: {
                sessions_with_high_vagueness: 2,
                sessions_with_forbidden_words: 1,
            },
            effectiveness: {
                pass_rate_3min_flow: 66.7,
                pass_rate_5turn_defense: 58.3,
                pass_rate_4step_structure: 75,
                next_day_retry_rate: 41.7,
            },
        });
        getAgentsMock.mockResolvedValue({
            agent_stats: [],
            persona_stats: [],
            scenario_distribution: {
                sales: 10,
                presentation: 5,
            },
        });
        getManagerLiteListsMock.mockResolvedValue({
            not_passed: [],
            inactive_streak: [],
            improving: [],
        });
    });

    it("renders projection-backed score meaning, issue families, and evidence-insufficient reasoning", async () => {
        getOverviewMock.mockResolvedValue({
            total_users: 12,
            active_users_today: 4,
            active_users_week: 8,
            total_sessions: 15,
            sessions_today: 2,
            completed_sessions: 15,
            completion_rate: 100,
            average_score: 78.4,
            average_duration_minutes: 4.5,
            growth: {
                users_rate: 0,
                sessions_rate: 15,
                score_rate: 4,
            },
            evaluable_sessions: 12,
            not_evaluable_sessions: 3,
            score_basis: "session_evidence_projection_evaluable_only",
            top_issue_families: [
                {
                    issue_type: "evidence_gap",
                    issue_text: "最近都卡在 ROI 证据不具体。",
                    count: 4,
                },
            ],
            not_evaluable_reasons: [
                {
                    reason: "INSUFFICIENT_TURN_DATA",
                    count: 3,
                },
            ],
        });
        getTrendsMock.mockResolvedValue({
            trend_data: [
                {
                    date: "2026-03-01T00:00:00+00:00",
                    sessions_count: 4,
                    average_score: 76,
                    active_users: 3,
                    evaluable_session_count: 3,
                    not_evaluable_session_count: 1,
                },
            ],
            score_distribution: {
                excellent: 3,
                good: 5,
                fair: 3,
                poor: 1,
            },
            projection_summary: {
                average_score: 78.4,
                best_score: 92,
                evaluable_sessions: 12,
                not_evaluable_sessions: 3,
                score_basis: "session_evidence_projection_evaluable_only",
                issue_family_distribution: [
                    {
                        issue_type: "evidence_gap",
                        issue_text: "最近都卡在 ROI 证据不具体。",
                        count: 4,
                    },
                ],
                not_evaluable_reasons: [
                    {
                        reason: "INSUFFICIENT_TURN_DATA",
                        count: 3,
                    },
                ],
                repeated_main_issues: [
                    {
                        issue_type: "evidence_gap",
                        issue_text: "最近都卡在 ROI 证据不具体。",
                        count: 4,
                    },
                ],
                repeated_next_goals: [
                    {
                        goal_type: "evidence_backing",
                        goal_text: "下一轮先补 ROI 与客户案例证据。",
                        count: 4,
                    },
                ],
            },
        });
        getLeaderboardMock.mockResolvedValue({
            leaderboard: [
                {
                    rank: 1,
                    user_id: "user-1",
                    username: "张三",
                    department: "销售一部",
                    total_sessions: 8,
                    average_score: 88.6,
                    best_score: 93,
                    total_duration_minutes: 32,
                    evaluable_sessions: 8,
                    not_evaluable_sessions: 1,
                    primary_issue_type: "objection_response",
                    primary_next_goal_type: "next_step_commitment",
                    score_basis: "session_evidence_projection_evaluable_only",
                },
            ],
        });

        render(<AnalyticsPage />);

        await waitFor(() => {
            expect(getOverviewMock).toHaveBeenCalledWith({
                time_range: "30d",
                scenario_type: undefined,
            });
        });

        expect(await screen.findByText("当前看板口径")).toBeTruthy();
        expect(screen.getByText(/综合分、分布和排行榜只纳入 12 次可评估的已完成训练；3 次证据不足会话/)).toBeTruthy();
        expect(screen.getByText("统一训练证据 · 仅统计可评估的已完成训练")).toBeTruthy();
        expect(screen.getByText("证据支撑")).toBeTruthy();
        expect(screen.getByText("最近都卡在 ROI 证据不具体。", { exact: false })).toBeTruthy();
        expect(screen.getByText("对话轮次不足，暂无法形成稳定评估。")).toBeTruthy();
        expect(screen.getByText("证据补强")).toBeTruthy();
        expect(screen.getByText("下一轮先补 ROI 与客户案例证据。")).toBeTruthy();
        expect(screen.getByText("当前榜首：张三")).toBeTruthy();
        expect(screen.getByText("最近主问题：异议回应")).toBeTruthy();
        expect(screen.getByText("下一轮重点：下一步承诺")).toBeTruthy();
    });

    it("keeps evidence-language placeholders visible when there is no stable repeated signal", async () => {
        getOverviewMock.mockResolvedValue({
            total_users: 4,
            active_users_today: 0,
            active_users_week: 1,
            total_sessions: 2,
            sessions_today: 0,
            completed_sessions: 2,
            completion_rate: 100,
            average_score: 0,
            average_duration_minutes: 1,
            growth: {
                users_rate: 0,
                sessions_rate: 0,
                score_rate: 0,
            },
            evaluable_sessions: 0,
            not_evaluable_sessions: 0,
            score_basis: "session_evidence_projection_evaluable_only",
            top_issue_families: [],
            not_evaluable_reasons: [],
        });
        getTrendsMock.mockResolvedValue({
            trend_data: [],
            score_distribution: {
                excellent: 0,
                good: 0,
                fair: 0,
                poor: 0,
            },
            projection_summary: {
                average_score: 0,
                best_score: 0,
                evaluable_sessions: 0,
                not_evaluable_sessions: 0,
                score_basis: "session_evidence_projection_evaluable_only",
                issue_family_distribution: [],
                not_evaluable_reasons: [],
                repeated_main_issues: [],
                repeated_next_goals: [],
            },
        });
        getLeaderboardMock.mockResolvedValue({ leaderboard: [] });

        render(<AnalyticsPage />);

        expect(await screen.findByText("当前看板口径")).toBeTruthy();
        expect(screen.getByText(/只纳入 0 次可评估的已完成训练；0 次证据不足会话/)).toBeTruthy();
        expect(screen.getByText("当前时间范围内还没有形成稳定重复的问题家族。")).toBeTruthy();
        expect(screen.getByText("当前时间范围内没有证据不足会话，所有已完成训练都纳入统一分数口径。")).toBeTruthy();
        expect(screen.getByText("当前时间范围内还没有形成稳定重复的下一轮重点。")).toBeTruthy();
        expect(screen.queryByText(/当前榜首：/)).toBeNull();
    });
});
