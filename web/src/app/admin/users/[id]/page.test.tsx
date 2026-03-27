import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UserDetailPage from "./page";
import { ApiRequestError } from "@/lib/api/client";
import { buildAdminUserDrillInHref } from "@/lib/admin/drill-in";
import type { LinkedAssetChangeReference, SupportRuntimeFaultsResponse } from "@/lib/api/types";

const {
    pushMock,
    useSearchParamsMock,
    getUserStatsMock,
    getUserSessionsMock,
    getUserProgressMock,
    listManagerInterventionsMock,
    createManagerInterventionMock,
    remindManagerInterventionMock,
    getSupportRuntimeFaultsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    useSearchParamsMock: vi.fn(),
    getUserStatsMock: vi.fn(),
    getUserSessionsMock: vi.fn(),
    getUserProgressMock: vi.fn(),
    listManagerInterventionsMock: vi.fn(),
    createManagerInterventionMock: vi.fn(),
    remindManagerInterventionMock: vi.fn(),
    getSupportRuntimeFaultsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
        back: vi.fn(),
    }),
    useParams: () => ({
        id: "user-1",
    }),
    useSearchParams: () => useSearchParamsMock(),
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
                listManagerInterventions: listManagerInterventionsMock,
                createManagerIntervention: createManagerInterventionMock,
                remindManagerIntervention: remindManagerInterventionMock,
            },
            supportRuntime: {
                ...actual.api.supportRuntime,
                getFaults: getSupportRuntimeFaultsMock,
            },
        },
    };
});

function searchParamsFromDrillInHref(href: string): URLSearchParams {
    return new URL(href, "https://example.com").searchParams;
}

const linkedAssetChanges = [
    {
        asset_type: "knowledge_base",
        asset_label: "知识库",
        asset_id: "kb-1",
        asset_name: "石犀产品知识库",
        admin_path: "/admin/knowledge",
        latest_change_label: "最近文档：竞品对比",
        latest_change_type: "document_replace",
        last_changed_at: "2026-03-25T08:00:00Z",
        change_count_7d: 2,
        sessions_since_change: 5,
        impact_level: "high",
        health_status: "blocking",
    },
    {
        asset_type: "persona",
        asset_label: "角色",
        asset_id: "persona-1",
        asset_name: "预算压价角色",
        admin_path: "/admin/personas",
        latest_change_label: "最近策略：提高压价强度",
        latest_change_type: "policy_update",
        last_changed_at: "2026-03-25T09:00:00Z",
        change_count_7d: 1,
        sessions_since_change: 3,
        impact_level: "medium",
        health_status: "warning",
    },
    {
        asset_type: "runtime_profile",
        asset_label: "",
        asset_id: "runtime-1",
        asset_name: "销售默认 Realtime",
        admin_path: "",
        latest_change_label: "最近配置：切换 KB 锁模式",
        latest_change_type: "config_update",
        last_changed_at: "2026-03-25T10:00:00Z",
        change_count_7d: 3,
        sessions_since_change: 6,
        impact_level: "high",
        health_status: "blocking",
    },
] satisfies LinkedAssetChangeReference[];

const supportRuntimeFaultsResponse = {
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
                linked_asset_changes: linkedAssetChanges,
            },
        },
    ],
    count: 1,
    limit: 100,
    severity: null,
} satisfies SupportRuntimeFaultsResponse;

const baseStatsResponse = {
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
        total_sessions: 4,
        total_duration_minutes: 16,
        average_score: 55,
    },
    statistics: {
        total_sessions: 4,
        completed_sessions: 4,
        completion_rate: 100,
        average_score: 55,
        best_score: 70,
        worst_score: 40,
        evaluable_sessions: 3,
        not_evaluable_sessions: 1,
        score_basis: "session_evidence_projection_evaluable_only",
        total_duration_minutes: 16,
        last_practice: "2026-03-23T09:00:00Z",
        unique_agents_used: 1,
        unique_personas_used: 1,
    },
    agent_usage: [],
    persona_usage: [],
};

const baseSessionsResponse = {
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
            feedback_summary: "最近一次报告提示：还要把风险回应说具体。",
        },
    ],
    total: 1,
    page: 1,
    page_size: 10,
    has_more: false,
    manager_intervention_results: [
        {
            intervention_id: "intervention-1",
            issue_family: "evidence_gap",
            note: "优先补 ROI 和客户案例证据。",
            created_at: "2026-03-23T09:30:00Z",
            session_id: "session-1",
            session_start_time: "2026-03-23T09:00:00Z",
            status: "improved",
            reason: "issue_family_shifted",
            summary: "最近一次可评估训练的主问题已转向其他家族，说明这个主管重点已有改善。",
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
        },
    ],
};

const richProgressResponse = {
    granularity: "week",
    trend_data: [
        {
            date: "2026-03-02T00:00:00+00:00",
            sessions_count: 3,
            evaluable_session_count: 2,
            not_evaluable_session_count: 1,
            average_score: 60,
            logic_score: 55,
            accuracy_score: 61,
            completeness_score: 64,
            overall_result: "fail",
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: {
                issue_type: "objection_response",
                issue_text: "异议回应不够具体。",
                recovery_rule: "先回应风险，再补证据。",
            },
            next_goal: {
                goal_type: "objection_response_drill",
                goal_text: "下一轮继续把异议回应说完整。",
                rule: "至少完成 1 次完整异议回应。",
            },
            stage_summary: [],
            evidence_completeness: {
                complete: true,
                missing_fields: [],
                message_count: 6,
            },
        },
        {
            date: "2026-03-09T00:00:00+00:00",
            sessions_count: 1,
            evaluable_session_count: 1,
            not_evaluable_session_count: 0,
            average_score: 40,
            logic_score: 38,
            accuracy_score: 42,
            completeness_score: 40,
            overall_result: "fail",
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: {
                issue_type: "objection_response",
                issue_text: "异议回应不够具体。",
                recovery_rule: "先回应风险，再补证据。",
            },
            next_goal: {
                goal_type: "objection_response_drill",
                goal_text: "下一轮继续把异议回应说完整。",
                rule: "至少完成 1 次完整异议回应。",
            },
            stage_summary: [],
            evidence_completeness: {
                complete: true,
                missing_fields: [],
                message_count: 3,
            },
        },
    ],
    improvement_rate: -33.3,
    total_data_points: 2,
    completed_session_count: 4,
    evaluable_session_count: 3,
    not_evaluable_session_count: 1,
    non_completed_session_count: 1,
    repeated_main_issues: [
        {
            issue_type: "evidence_gap",
            issue_text: "证据支撑还不够具体。",
            count: 3,
        },
    ],
    repeated_next_goals: [
        {
            goal_type: "evidence_backing",
            goal_text: "下一轮继续补上 ROI 与客户案例证据。",
            count: 3,
        },
    ],
    should_switch_focus: true,
    recommendation: {
        reason: "stalled_repeated_focus",
        summary: "最近多次训练仍卡在同一重点且没有改善，建议切换训练重点或训练方法。",
    },
};

const baseInterventionsResponse = {
    items: [
        {
            intervention_id: "intervention-1",
            manager_user_id: "admin-1",
            user_id: "user-1",
            issue_family: "evidence_gap",
            note: "优先补 ROI 和客户案例证据。",
            due_state: "due",
            reminder_status: "sent",
            reminder_sent_at: "2026-03-23T10:00:00Z",
            resolving_session_id: null,
            created_at: "2026-03-23T09:30:00Z",
            updated_at: "2026-03-23T10:00:00Z",
        },
    ],
    total: 1,
};

describe("UserDetailPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        useSearchParamsMock.mockReset();
        getUserStatsMock.mockReset();
        getUserSessionsMock.mockReset();
        getUserProgressMock.mockReset();
        listManagerInterventionsMock.mockReset();
        createManagerInterventionMock.mockReset();
        remindManagerInterventionMock.mockReset();
        getSupportRuntimeFaultsMock.mockReset();

        useSearchParamsMock.mockReturnValue(new URLSearchParams());
        getUserStatsMock.mockResolvedValue(baseStatsResponse);
        getUserSessionsMock.mockResolvedValue(baseSessionsResponse as any);
        getUserProgressMock.mockResolvedValue(richProgressResponse as any);
        listManagerInterventionsMock.mockResolvedValue(baseInterventionsResponse as any);
        getSupportRuntimeFaultsMock.mockResolvedValue(supportRuntimeFaultsResponse);
        createManagerInterventionMock.mockResolvedValue({
            intervention_id: "intervention-2",
            manager_user_id: "admin-1",
            user_id: "user-1",
            issue_family: "evidence_gap",
            note: "先补 ROI 与客户案例证据。",
            due_state: "pending",
            reminder_status: "not_sent",
            reminder_sent_at: null,
            resolving_session_id: null,
            created_at: "2026-03-24T09:00:00Z",
            updated_at: "2026-03-24T09:00:00Z",
        });
        remindManagerInterventionMock.mockResolvedValue({
            sent: true,
            reminder_id: "reminder-1",
            user_id: "user-1",
            intervention_id: "intervention-1",
        });
    });

    it("renders supervisor-readable progress summary with repeated blockers, next goal, and switch-focus guidance", async () => {
        render(<UserDetailPage />);

        await waitFor(() => {
            expect(getUserSessionsMock).toHaveBeenCalledWith("user-1", { page: 1, page_size: 10 });
        });

        expect(await screen.findByText("连续变化判断")).toBeTruthy();
        expect(screen.getByText("统一训练证据 · 仅统计可评估的已完成训练")).toBeTruthy();
        expect(screen.getByText("纳入 3 次可评估训练，另有 1 次证据不足会话单独记账。")).toBeTruthy();
        expect(screen.getByText("统一训练证据预览")).toBeTruthy();
        expect(screen.getAllByText("建议切换训练重点").length).toBeGreaterThan(0);
        expect(screen.getByText("证据支撑还不够具体。")).toBeTruthy();
        expect(screen.getByText("下一轮继续补上 ROI 与客户案例证据。")).toBeTruthy();
        expect(screen.getByText("证据支撑")).toBeTruthy();
        expect(screen.getByText("证据补强")).toBeTruthy();
        expect(screen.getByText(/已完成训练里有 1 次仍证据不足/)).toBeTruthy();
        expect(screen.getByText("最近多次训练仍卡在同一重点且没有改善，建议切换训练重点或训练方法。"))
            .toBeTruthy();
        expect(screen.getByText("最近运行异常：知识库锁定模式下检索失败，最近 3 个会话被阻断。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "知识库 · 石犀产品知识库" }).getAttribute("href")).toBe("/admin/knowledge");
        expect(screen.getByRole("link", { name: "角色 · 预算压价角色" }).getAttribute("href")).toBe("/admin/personas");
        expect(screen.getByRole("link", { name: "运行时配置 · 销售默认 Realtime" }).getAttribute("href")).toBe("/admin/voice-runtime");
        expect(screen.getByText("最近文档：竞品对比 · 近 7 天 2 次变更")).toBeTruthy();
        expect(screen.getByText("最近策略：提高压价强度 · 近 7 天 1 次变更")).toBeTruthy();
        expect(screen.getByText("最近配置：切换 KB 锁模式 · 近 7 天 3 次变更")).toBeTruthy();

        const reportLink = screen.getByRole("link", { name: "查看统一报告" }) as HTMLAnchorElement;
        expect(reportLink.getAttribute("href")).toBe("/practice/session-1/report");
    });

    it("renders a local inline empty state when progress has no evaluable sessions", async () => {
        getUserProgressMock.mockResolvedValue({
            granularity: "week",
            trend_data: [],
            improvement_rate: 0,
            total_data_points: 0,
            completed_session_count: 2,
            evaluable_session_count: 0,
            not_evaluable_session_count: 2,
            non_completed_session_count: 0,
            repeated_main_issues: [],
            repeated_next_goals: [],
            should_switch_focus: false,
            recommendation: {
                reason: "insufficient_evaluable_history",
                summary: "最近完成的训练里仍有证据不足的会话，先补齐有效互动再判断是否切换重点。",
            },
        } as any);

        render(<UserDetailPage />);

        expect(await screen.findByText("暂无可评估训练数据")).toBeTruthy();
        expect(screen.getByText(/最近 2 次已完成训练仍证据不足/)).toBeTruthy();
        expect(screen.getByText("最近完成的训练里仍有证据不足的会话，先补齐有效互动再判断是否切换重点。"))
            .toBeTruthy();
        expect(screen.queryByText("用户不存在或加载失败")).toBeNull();
    });

    it("keeps the page shell visible and shows an inline progress error when only progress loading fails", async () => {
        getUserProgressMock.mockRejectedValue(
            new ApiRequestError({
                status: 0,
                errorCode: "[NETWORK_ERROR]",
                message: "network down",
            }),
        );

        render(<UserDetailPage />);

        expect(await screen.findByText("张三")).toBeTruthy();
        expect(screen.getAllByText(
            "连续变化视图加载失败：网络连接失败，请检查后端服务或网络设置后重试。",
        ).length).toBeGreaterThan(0);
        expect(screen.queryByText("用户不存在或加载失败")).toBeNull();

        const reportLink = screen.getByRole("link", { name: "查看统一报告" }) as HTMLAnchorElement;
        expect(reportLink.getAttribute("href")).toBe("/practice/session-1/report");
    });

    it("shows the weekly operating drill-in context when the detail page is opened from a current risk bucket", async () => {
        useSearchParamsMock.mockReturnValue(
            searchParamsFromDrillInHref(
                buildAdminUserDrillInHref({
                    kind: "not_passed",
                    userId: "user-1",
                    issueFamily: "objection_response",
                    note: "先把风险回应补全。",
                }),
            ),
        );

        render(<UserDetailPage />);

        expect(await screen.findByText("本周经营名单来源")).toBeTruthy();
        expect(screen.getByText("本周风险成员")).toBeTruthy();
        expect(screen.getByText("当前这条 drill-in 仍落在「异议回应」这个问题家族。"))
            .toBeTruthy();
        expect(screen.getByText("建议说明：先把风险回应补全。"))
            .toBeTruthy();

        const issueFamilySelect = screen.getByLabelText("主管重点") as HTMLSelectElement;
        expect(issueFamilySelect.value).toBe("objection_response");

        const noteInput = screen.getByLabelText("主管说明") as HTMLTextAreaElement;
        expect(noteInput.value).toBe("先把风险回应补全。");
    });

    it("derives the shared default note on the detail page when a not-passed drill-in omits focusNote", async () => {
        useSearchParamsMock.mockReturnValue(
            new URLSearchParams("focusBucket=not_passed&focusIssueFamily=objection_response"),
        );

        render(<UserDetailPage />);

        expect(await screen.findByText("本周经营名单来源")).toBeTruthy();
        expect(screen.getByText("当前这条 drill-in 仍落在「异议回应」这个问题家族。"))
            .toBeTruthy();
        expect(screen.getByText("建议说明：先对照最近统一报告把异议回应说完整。"))
            .toBeTruthy();

        const issueFamilySelect = screen.getByLabelText("主管重点") as HTMLSelectElement;
        expect(issueFamilySelect.value).toBe("objection_response");

        const noteInput = screen.getByLabelText("主管说明") as HTMLTextAreaElement;
        expect(noteInput.value).toBe("先对照最近统一报告把异议回应说完整。");
    });

    it("shows the inactive-streak drill-in context without overwriting the current intervention note", async () => {
        useSearchParamsMock.mockReturnValue(
            searchParamsFromDrillInHref(
                buildAdminUserDrillInHref({
                    kind: "inactive_streak",
                    userId: "user-1",
                }),
            ),
        );

        render(<UserDetailPage />);

        expect(await screen.findByText("本周经营名单来源")).toBeTruthy();
        expect(screen.getByText("本周连续未练")).toBeTruthy();
        expect(screen.getByText("当前这位成员来自本周连续未练名单，先确认节奏恢复，再决定是否补主管重点。"))
            .toBeTruthy();

        const noteInput = screen.getByLabelText("主管说明") as HTMLTextAreaElement;
        expect(noteInput.value).toBe("");
    });

    it("shows the improving drill-in context from the shared launcher contract", async () => {
        useSearchParamsMock.mockReturnValue(
            searchParamsFromDrillInHref(
                buildAdminUserDrillInHref({
                    kind: "improving",
                    userId: "user-1",
                }),
            ),
        );

        render(<UserDetailPage />);

        expect(await screen.findByText("本周经营名单来源")).toBeTruthy();
        expect(screen.getByText("本周显著回升")).toBeTruthy();
        expect(screen.getByText("当前这位成员来自本周显著回升名单，适合复盘最近有效动作并固化下一轮训练。"))
            .toBeTruthy();

        const noteInput = screen.getByLabelText("主管说明") as HTMLTextAreaElement;
        expect(noteInput.value).toBe("");
    });

    it("lets supervisors inspect persisted interventions and create a new focus on the current detail page", async () => {
        useSearchParamsMock.mockReturnValue(
            new URLSearchParams("focusIssueFamily=evidence_gap&focusNote=先补%20ROI%20与客户案例证据。"),
        );

        render(<UserDetailPage />);

        expect(await screen.findByText("主管重点与提醒")).toBeTruthy();
        expect(screen.getByText("优先补 ROI 和客户案例证据。")).toBeTruthy();
        expect(screen.getByText("提醒已发送")).toBeTruthy();

        const issueFamilySelect = await screen.findByLabelText("主管重点") as HTMLSelectElement;
        expect(issueFamilySelect.value).toBe("evidence_gap");

        const noteInput = screen.getByLabelText("主管说明") as HTMLTextAreaElement;
        expect(noteInput.value).toBe("先补 ROI 与客户案例证据。");

        fireEvent.click(screen.getByRole("button", { name: "设为主管重点" }));

        await waitFor(() => {
            expect(createManagerInterventionMock).toHaveBeenCalledWith({
                user_id: "user-1",
                issue_family: "evidence_gap",
                note: "先补 ROI 与客户案例证据。",
            });
        });

        expect(await screen.findByText("主管重点已记录，可继续发送提醒。")).toBeTruthy();
        expect(screen.getByText("先补 ROI 与客户案例证据。")).toBeTruthy();
    });

    it("shows the latest intervention result with a report drill-in on the current intervention card", async () => {
        render(<UserDetailPage />);

        expect(await screen.findByText("主管重点与提醒")).toBeTruthy();
        expect(screen.getByText("最近结果：已改善")).toBeTruthy();
        expect(screen.getByText("最近一次可评估训练的主问题已转向其他家族，说明这个主管重点已有改善。")).toBeTruthy();

        const linkedReport = screen.getByRole("link", { name: "查看对应统一报告" }) as HTMLAnchorElement;
        expect(linkedReport.getAttribute("href")).toBe("/practice/session-1/report");
    });

    it("keeps pending intervention results visible without a report drill-in before a follow-up session exists", async () => {
        getUserSessionsMock.mockResolvedValue({
            ...baseSessionsResponse,
            manager_intervention_results: [
                {
                    intervention_id: "intervention-1",
                    issue_family: "evidence_gap",
                    note: "优先补 ROI 和客户案例证据。",
                    created_at: "2026-03-23T09:30:00Z",
                    session_id: null,
                    session_start_time: null,
                    status: "pending",
                    reason: "no_completed_session_after_intervention",
                    summary: "主管重点建立后，还没有新的已完成训练可用于判断结果。",
                    overall_result: null,
                    evaluable: null,
                    not_evaluable_reason: null,
                    main_issue: null,
                    next_goal: null,
                },
            ],
        } as any);

        render(<UserDetailPage />);

        expect(await screen.findByText("主管重点与提醒")).toBeTruthy();
        expect(screen.getByText("最近结果：等待新训练")).toBeTruthy();
        expect(screen.getByText("主管重点建立后，还没有新的已完成训练可用于判断结果。")).toBeTruthy();
        expect(screen.queryByRole("link", { name: "查看对应统一报告" })).toBeNull();
    });

    it("lets supervisors send a reminder from an existing intervention card", async () => {
        render(<UserDetailPage />);

        expect(await screen.findByText("优先补 ROI 和客户案例证据。")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "记录提醒" }));

        await waitFor(() => {
            expect(remindManagerInterventionMock).toHaveBeenCalledWith({
                user_id: "user-1",
                intervention_id: "intervention-1",
                note: "优先补 ROI 和客户案例证据。",
            });
        });

        expect(await screen.findByText("已记录提醒，当前重点仍保持在主管视图中。")).toBeTruthy();
    });
});
