import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "./page";

const {
    getOverviewMock,
    getTrendsMock,
    getAgentsMock,
    getLeaderboardMock,
    getManagerLiteListsMock,
    getOperatingPackMock,
    remindFromManagerLiteMock,
    exportReportMock,
    getDashboardMock,
    getSupportRuntimeFaultsMock,
} = vi.hoisted(() => ({
    getOverviewMock: vi.fn(),
    getTrendsMock: vi.fn(),
    getAgentsMock: vi.fn(),
    getLeaderboardMock: vi.fn(),
    getManagerLiteListsMock: vi.fn(),
    getOperatingPackMock: vi.fn(),
    remindFromManagerLiteMock: vi.fn(),
    exportReportMock: vi.fn(),
    getDashboardMock: vi.fn(),
    getSupportRuntimeFaultsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
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
                getOperatingPack: getOperatingPackMock,
                remindFromManagerLite: remindFromManagerLiteMock,
                exportReport: exportReportMock,
            },
            analyticsOpen: {
                ...actual.api.analyticsOpen,
                getDashboard: getDashboardMock,
            },
            supportRuntime: {
                ...actual.api.supportRuntime,
                getFaults: getSupportRuntimeFaultsMock,
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
    ManagerLitePanel: ({
        data,
        onRemind,
    }: {
        data: { not_passed: Array<{ user_id: string }> };
        onRemind?: (userId: string) => Promise<void>;
    }) => (
        <div>
            <div>ManagerLitePanel:{data.not_passed.length}</div>
            {data.not_passed[0] ? (
                <button onClick={() => void onRemind?.(data.not_passed[0].user_id)}>触发主管提醒</button>
            ) : null}
        </div>
    ),
}));

describe("AnalyticsPage", () => {
    beforeEach(() => {
        getOverviewMock.mockReset();
        getTrendsMock.mockReset();
        getAgentsMock.mockReset();
        getLeaderboardMock.mockReset();
        getManagerLiteListsMock.mockReset();
        getOperatingPackMock.mockReset();
        remindFromManagerLiteMock.mockReset();
        exportReportMock.mockReset();
        getDashboardMock.mockReset();
        getSupportRuntimeFaultsMock.mockReset();

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
        getSupportRuntimeFaultsMock.mockResolvedValue({
            generated_at: "2026-03-26T09:40:00Z",
            items: [
                {
                    source: "session",
                    severity: "blocking",
                    kind: "kb_lock_blocked_search_failed",
                    summary: "知识库锁定模式下检索失败，最近 3 个会话被阻断。",
                    detected_at: "2026-03-26T09:30:00Z",
                    session_id: "session-1",
                    scenario_type: "sales",
                    session_status: "completed",
                    report_status: "completed",
                    diagnostics: {
                        linked_asset_changes: [
                            {
                                asset_type: "knowledge_base",
                                asset_id: "kb-1",
                                asset_name: "石犀产品知识库",
                                admin_path: "/admin/knowledge",
                                latest_change_label: "最近文档：竞品对比",
                                change_count_7d: 2,
                                impact_level: "high",
                                health_status: "blocking",
                            },
                        ],
                    },
                },
            ],
            count: 1,
            limit: 20,
            severity: null,
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
        getOperatingPackMock.mockResolvedValue({
            score_basis: "session_evidence_projection_evaluable_only",
            weekly_summary: {
                window_days: 7,
                window_start: "2026-03-19T00:00:00Z",
                window_end: "2026-03-26T00:00:00Z",
                completed_sessions: 0,
                evaluable_sessions: 0,
                not_evaluable_sessions: 0,
                degraded_sessions: 0,
                active_departments: 0,
                at_risk_users: 0,
                improving_users: 0,
                top_issue_family: null,
                top_blocker_family: null,
                top_not_evaluable_reason: null,
                top_degraded_reason: null,
            },
            cohort_issue_buckets: [],
            department_issue_buckets: [],
            repeated_blocker_families: [],
            degradation_breakdown: {
                not_evaluable_reasons: [],
                degraded_reasons: [],
            },
            manager_lists: {
                not_passed: [],
                inactive_streak: [],
                improving: [],
            },
        });
    });

    it("renders weekly operating-pack summary, cohort buckets, and projection-backed manager lists", async () => {
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
            top_issue_families: [],
            not_evaluable_reasons: [],
        });
        getTrendsMock.mockResolvedValue({
            trend_data: [],
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
                issue_family_distribution: [],
                not_evaluable_reasons: [],
                repeated_main_issues: [],
                repeated_next_goals: [],
            },
        });
        getLeaderboardMock.mockResolvedValue({ leaderboard: [] });
        getManagerLiteListsMock.mockResolvedValue({
            not_passed: [],
            inactive_streak: [],
            improving: [],
        });
        getOperatingPackMock.mockResolvedValue({
            score_basis: "session_evidence_projection_evaluable_only",
            weekly_summary: {
                window_days: 7,
                window_start: "2026-03-19T00:00:00Z",
                window_end: "2026-03-26T00:00:00Z",
                completed_sessions: 8,
                evaluable_sessions: 7,
                not_evaluable_sessions: 1,
                degraded_sessions: 1,
                active_departments: 2,
                at_risk_users: 4,
                improving_users: 1,
                top_issue_family: {
                    issue_family: "value_expression",
                    issue_type: "value_expression",
                    issue_text: "价值表达还停留在产品功能。",
                    count: 2,
                    user_count: 2,
                    department_count: 2,
                },
                top_blocker_family: {
                    issue_family: "value_expression",
                    issue_type: "value_expression",
                    issue_text: "价值表达还停留在产品功能。",
                    count: 2,
                    user_count: 2,
                    department_count: 2,
                },
                top_not_evaluable_reason: {
                    reason: "INSUFFICIENT_TURN_DATA",
                    count: 1,
                },
                top_degraded_reason: {
                    reason: "message_scores",
                    count: 1,
                },
            },
            cohort_issue_buckets: [
                {
                    issue_family: "value_expression",
                    issue_type: "value_expression",
                    issue_text: "价值表达还停留在产品功能。",
                    count: 2,
                    user_count: 2,
                    department_count: 2,
                },
                {
                    issue_family: "evidence_gap",
                    issue_type: "evidence_gap",
                    issue_text: "案例证据还不够扎实。",
                    count: 2,
                    user_count: 1,
                    department_count: 1,
                },
            ],
            department_issue_buckets: [
                {
                    department: "North",
                    session_count: 7,
                    evaluable_sessions: 6,
                    not_evaluable_sessions: 1,
                    issue_buckets: [
                        {
                            issue_family: "evidence_gap",
                            issue_type: "evidence_gap",
                            issue_text: "案例证据还不够扎实。",
                            count: 2,
                            user_count: 1,
                        },
                    ],
                    degradation_breakdown: {
                        not_evaluable_reasons: [
                            {
                                reason: "INSUFFICIENT_TURN_DATA",
                                count: 1,
                            },
                        ],
                        degraded_reasons: [
                            {
                                reason: "message_scores",
                                count: 1,
                            },
                        ],
                    },
                },
            ],
            repeated_blocker_families: [
                {
                    issue_family: "value_expression",
                    issue_type: "value_expression",
                    issue_text: "价值表达还停留在产品功能。",
                    count: 2,
                    user_count: 2,
                    department_count: 2,
                },
            ],
            degradation_breakdown: {
                not_evaluable_reasons: [
                    {
                        reason: "INSUFFICIENT_TURN_DATA",
                        count: 1,
                    },
                ],
                degraded_reasons: [
                    {
                        reason: "message_scores",
                        count: 1,
                    },
                ],
            },
            manager_lists: {
                not_passed: [
                    {
                        user_id: "user-risk",
                        user_name: "South Risk",
                        department: "South",
                        overall_result: "fail",
                        session_id: "session-risk",
                        session_start_time: "2026-03-25T10:00:00Z",
                        issue_family: "value_expression",
                    },
                ],
                inactive_streak: [
                    {
                        user_id: "user-inactive",
                        user_name: "Inactive User",
                        department: "North",
                        last_session_at: "2026-03-18T10:00:00Z",
                        inactive_days: 8,
                    },
                ],
                improving: [
                    {
                        user_id: "user-good",
                        user_name: "Improving User",
                        department: "North",
                        pass_gain: 100,
                        baseline_pass_rate: 0,
                        current_pass_rate: 100,
                    },
                ],
            },
        });

        render(<AnalyticsPage />);

        await waitFor(() => {
            expect(getOperatingPackMock).toHaveBeenCalledWith({
                time_range: "7d",
                scenario_type: undefined,
                limit: 10,
                inactive_days: 7,
            });
        });

        expect(await screen.findByText("本周经营节奏包")).toBeTruthy();
        expect(screen.getByText(/本周已完成 8 次训练，其中 7 次可评估，1 次证据不足；当前有 4 位风险成员、1 位显著回升成员。/)).toBeTruthy();
        expect(screen.getByText("反复卡点 Top 1")).toBeTruthy();
        expect(screen.getAllByText("价值表达还停留在产品功能。", { exact: false }).length).toBeGreaterThan(0);
        expect(screen.getByText("部门问题面")).toBeTruthy();
        expect(screen.getByText("North")).toBeTruthy();
        expect(screen.getByText(/本周 7 次训练 · 6 次可评估 · 1 次证据不足/)).toBeTruthy();
        expect(screen.getByText("ManagerLitePanel:1")).toBeTruthy();
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
        expect(screen.getAllByText("对话轮次不足，暂无法形成稳定评估。").length).toBeGreaterThan(0);
        expect(screen.getByText("证据补强")).toBeTruthy();
        expect(screen.getByText("下一轮先补 ROI 与客户案例证据。")).toBeTruthy();
        expect(screen.getByText("当前榜首：张三")).toBeTruthy();
        expect(screen.getByText("最近主问题：异议回应")).toBeTruthy();
        expect(screen.getByText("下一轮重点：下一步承诺")).toBeTruthy();
        expect(screen.getByText("异常关联资产变更")).toBeTruthy();
        expect(screen.getByText("知识库锁定模式下检索失败，最近 3 个会话被阻断。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "知识库 · 石犀产品知识库" }).getAttribute("href")).toBe("/admin/knowledge");
        expect(screen.getByText(/最近文档：竞品对比/)).toBeTruthy();
    });

    it("sends the current manager-lite reminder through the admin operating-pack surface and refreshes the page data", async () => {
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
            top_issue_families: [],
            not_evaluable_reasons: [],
        });
        getTrendsMock.mockResolvedValue({
            trend_data: [],
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
                issue_family_distribution: [],
                not_evaluable_reasons: [],
                repeated_main_issues: [],
                repeated_next_goals: [],
            },
        });
        getLeaderboardMock.mockResolvedValue({ leaderboard: [] });
        getOperatingPackMock.mockResolvedValue({
            score_basis: "session_evidence_projection_evaluable_only",
            weekly_summary: {
                window_days: 7,
                window_start: "2026-03-19T00:00:00Z",
                window_end: "2026-03-26T00:00:00Z",
                completed_sessions: 8,
                evaluable_sessions: 7,
                not_evaluable_sessions: 1,
                degraded_sessions: 1,
                active_departments: 2,
                at_risk_users: 1,
                improving_users: 1,
                top_issue_family: null,
                top_blocker_family: null,
                top_not_evaluable_reason: null,
                top_degraded_reason: null,
            },
            cohort_issue_buckets: [],
            department_issue_buckets: [],
            repeated_blocker_families: [],
            degradation_breakdown: {
                not_evaluable_reasons: [],
                degraded_reasons: [],
            },
            manager_lists: {
                not_passed: [
                    {
                        user_id: "user-risk",
                        user_name: "South Risk",
                        department: "South",
                        overall_result: "fail",
                        session_id: "session-risk",
                        session_start_time: "2026-03-25T10:00:00Z",
                        issue_family: "value_expression",
                    },
                ],
                inactive_streak: [],
                improving: [],
            },
        });

        render(<AnalyticsPage />);

        expect(await screen.findByText("ManagerLitePanel:1")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "触发主管提醒" }));

        await waitFor(() => {
            expect(remindFromManagerLiteMock).toHaveBeenCalledWith({
                user_id: "user-risk",
                note: "请按本周训练目标完成一次练习并提交结果。",
            });
        });
        await waitFor(() => {
            expect(getOperatingPackMock).toHaveBeenCalledTimes(2);
        });
    });

    it("exports the current analytics window through the existing admin CSV surface", async () => {
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
            top_issue_families: [],
            not_evaluable_reasons: [],
        });
        getTrendsMock.mockResolvedValue({
            trend_data: [],
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
                issue_family_distribution: [],
                not_evaluable_reasons: [],
                repeated_main_issues: [],
                repeated_next_goals: [],
            },
        });
        getLeaderboardMock.mockResolvedValue({ leaderboard: [] });

        render(<AnalyticsPage />);

        expect(await screen.findByText("当前看板口径")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "7天" }));

        await waitFor(() => {
            expect(getOverviewMock).toHaveBeenLastCalledWith({
                time_range: "7d",
                scenario_type: undefined,
            });
        });

        fireEvent.click(screen.getByRole("button", { name: "导出报表" }));

        await waitFor(() => {
            expect(exportReportMock).toHaveBeenCalledWith({
                time_range: "7d",
                format: "csv",
            });
        });
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
        getSupportRuntimeFaultsMock.mockResolvedValue({
            generated_at: "2026-03-26T09:40:00Z",
            items: [],
            count: 0,
            limit: 20,
            severity: null,
        });

        render(<AnalyticsPage />);

        expect(await screen.findByText("当前看板口径")).toBeTruthy();
        expect(screen.getByText(/只纳入 0 次可评估的已完成训练；0 次证据不足会话/)).toBeTruthy();
        expect(screen.getByText("当前时间范围内还没有形成稳定重复的问题家族。")).toBeTruthy();
        expect(screen.getByText("当前时间范围内没有证据不足会话，所有已完成训练都纳入统一分数口径。")).toBeTruthy();
        expect(screen.getByText("当前时间范围内还没有形成稳定重复的下一轮重点。")).toBeTruthy();
        expect(screen.queryByText(/当前榜首：/)).toBeNull();
        expect(screen.getByText("当前 blocking / warning 异常还没有指向最近资产变更。")).toBeTruthy();
    });
});
