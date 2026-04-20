import { render, screen, waitFor, within } from "@testing-library/react";
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

    it("falls back to compatibility reader rollups when canonical history scores are absent", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-compat-1",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 180,
                    overall_score: 12,
                    report_status: "pending",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: { complete: true },
                    compatibility_readers: {
                        practice_session_rollup_fields_v1: {
                            logic_score: 90,
                            accuracy_score: 86,
                            completeness_score: 81,
                            overall_score: 88,
                        },
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
            evaluable_sessions: 1,
            not_evaluable_sessions: 0,
            average_score: 88,
            best_score: 88,
            total_practice_time_seconds: 180,
            total_practice_time_minutes: 3,
        });
        getHistoryTrendsMock.mockResolvedValue([]);

        render(<HistoryPage />);

        const score = await screen.findByTestId("history-score-session-compat-1");
        expect(score.textContent).toContain("88");
        expect(score.getAttribute("data-contract-source")).toBe("compatibility_reader");
    });

    it("keeps presentation history entries on the shared replay/report route family", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "ppt-session-1",
                    scenario_name: "标准路演复盘",
                    scenario_type: "presentation",
                    persona_name: null,
                    agent_name: null,
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 420,
                    overall_score: 88,
                    report_status: "failed",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: {
                        complete: true,
                        scenario_type: "presentation",
                        presentation_review_available: true,
                    },
                    effectiveness_snapshot: null,
                    feedback_summary: "第二页还缺一个客户案例，继续按页补齐。",
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
            average_score: 88,
            best_score: 88,
            total_practice_time_seconds: 420,
            total_practice_time_minutes: 7,
        });
        getHistoryTrendsMock.mockResolvedValue([
            {
                session_id: "ppt-session-1",
                date: "2026-03-23T00:00:00Z",
                overall_score: 88,
                evaluable: true,
                not_evaluable_reason: null,
                evidence_completeness: {
                    complete: true,
                    scenario_type: "presentation",
                    presentation_review_available: true,
                },
                stage_summary: [],
                main_issue: null,
                next_goal: null,
            },
        ]);

        render(<HistoryPage />);

        expect(await screen.findByText("第二页还缺一个客户案例，继续按页补齐。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "回放" }).getAttribute("href")).toBe(
            "/practice/ppt-session-1/replay",
        );
        expect(screen.getByRole("link", { name: "报告" }).getAttribute("href")).toBe(
            "/practice/ppt-session-1/report",
        );
    });

    it("keeps learning cues visible when analytics snapshots degrade", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-3",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 240,
                    overall_score: 76,
                    report_status: "failed",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: { complete: true },
                    effectiveness_snapshot: null,
                    feedback_summary: "最近一次报告提示：别只说结果，要补可信证据。",
                    stage_summary: [
                        {
                            stage: "objection",
                            duration_ms: 80000,
                            score: 76,
                        },
                    ],
                    main_issue: {
                        issue_type: "evidence_gap",
                        issue_text: "客户还没听到可信证据。",
                        recovery_rule: "下一轮先补 ROI 或客户案例。",
                    },
                    next_goal: {
                        goal_type: "evidence_backing",
                        goal_text: "先补 ROI 证据，再确认下一步。",
                        rule: "至少补一条证据并确认客户是否认可。",
                    },
                },
            ],
            total: 1,
            page: 1,
            page_size: 50,
            total_pages: 1,
        });
        getHistoryStatisticsMock.mockRejectedValue(new Error("stats unavailable"));
        getHistoryTrendsMock.mockRejectedValue(new Error("trends unavailable"));

        render(<HistoryPage />);

        expect(await screen.findByText("统计看板、趋势快照暂不可用，训练列表仍基于统一训练证据展示。")).toBeTruthy();
        expect(screen.getByText("证据支撑")).toBeTruthy();
        expect(screen.getAllByText("客户还没听到可信证据。").length).toBeGreaterThan(0);
        expect(screen.getByText("证据补强")).toBeTruthy();
        expect(screen.getByText("先补 ROI 证据，再确认下一步。")).toBeTruthy();
        expect(screen.getByText("最近一次报告提示：别只说结果，要补可信证据。")).toBeTruthy();
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

    it("keeps incomplete sessions explicit by disabling the shared report CTA until completion", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-in-progress",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 120,
                    overall_score: null,
                    report_status: "processing",
                    report_generated_at: null,
                    status: "in_progress",
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
            average_score: 0,
            best_score: 0,
            total_practice_time_seconds: 120,
            total_practice_time_minutes: 2,
        });
        getHistoryTrendsMock.mockResolvedValue([]);

        render(<HistoryPage />);

        const reportButton = await screen.findByRole("button", { name: "报告" }) as HTMLButtonElement;
        expect(reportButton.disabled).toBe(true);
        expect(screen.getByText("进行中")).toBeTruthy();
    });

    it("shows the shared learner help card with truthful role guidance", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "history-help-session",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 180,
                    overall_score: 84,
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
            average_score: 84,
            best_score: 84,
            total_practice_time_seconds: 180,
            total_practice_time_minutes: 3,
        });
        getHistoryTrendsMock.mockResolvedValue([]);

        render(<HistoryPage />);

        expect(await screen.findByText("需要帮助或反馈？")).toBeTruthy();
        expect(screen.getByText(/统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。/)).toBeTruthy();
        expect(screen.getByText(/当前 learner 默认只看到训练、历史、个人中心；运行状态和管理后台只对管理员或支持角色开放。/)).toBeTruthy();
        expect(screen.queryByText(/7 x 24/)).toBeNull();
    });

    it("aggregates the top retry-eligible main issues and links to the latest report", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-evidence-latest",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-25T00:00:00Z",
                    duration_seconds: 180,
                    overall_score: 78,
                    report_status: "completed",
                    report_generated_at: "2026-03-25T00:05:00Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: { complete: true },
                    effectiveness_snapshot: null,
                    feedback_summary: null,
                    stage_summary: [],
                    main_issue: {
                        issue_type: "evidence_gap",
                        issue_text: "客户仍然没有听到量化证据。",
                        recovery_rule: "先补一个 ROI 数字，再确认客户是否认可。",
                    },
                    next_goal: {
                        goal_type: "evidence_backing",
                        goal_text: "下一轮必须补一条案例证据。",
                        rule: "至少补一条证据。",
                    },
                },
                {
                    session_id: "session-evidence-old",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 180,
                    overall_score: 74,
                    report_status: "completed",
                    report_generated_at: "2026-03-23T00:05:00Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: { complete: true },
                    effectiveness_snapshot: null,
                    feedback_summary: null,
                    stage_summary: [],
                    main_issue: {
                        issue_type: "evidence_gap",
                        issue_text: "旧报告的证据不足。",
                        recovery_rule: "旧动作不应成为最近卡点。",
                    },
                    next_goal: null,
                },
                {
                    session_id: "session-value",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-22T00:00:00Z",
                    duration_seconds: 180,
                    overall_score: 75,
                    report_status: "completed",
                    report_generated_at: "2026-03-22T00:05:00Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    evidence_completeness: { complete: true },
                    effectiveness_snapshot: null,
                    feedback_summary: null,
                    stage_summary: [],
                    main_issue: {
                        issue_type: "value_gap",
                        issue_text: "价值表达还停留在功能层。",
                        recovery_rule: "把功能翻译成业务收益。",
                    },
                    next_goal: null,
                },
                {
                    session_id: "session-explanation-only",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-26T00:00:00Z",
                    duration_seconds: 60,
                    overall_score: null,
                    report_status: "pending",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: false,
                    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
                    evidence_completeness: { complete: false },
                    effectiveness_snapshot: null,
                    feedback_summary: null,
                    stage_summary: [],
                    main_issue: {
                        issue_type: "insufficient_turn_data",
                        issue_text: "这条记录只能解释证据不足。",
                        recovery_rule: "完成一次可评估训练。",
                    },
                    next_goal: null,
                },
            ],
            total: 4,
            page: 1,
            page_size: 50,
            total_pages: 1,
        });
        getHistoryStatisticsMock.mockResolvedValue({
            total_sessions: 4,
            evaluable_sessions: 3,
            not_evaluable_sessions: 1,
            average_score: 76,
            best_score: 78,
            total_practice_time_seconds: 600,
            total_practice_time_minutes: 10,
        });
        getHistoryTrendsMock.mockResolvedValue([]);

        render(<HistoryPage />);

        const evidenceCard = await screen.findByTestId("history-issue-review-evidence_gap");
        expect(within(evidenceCard).getByText("证据支撑复练")).toBeTruthy();
        expect(within(evidenceCard).getByText("出现 2 次")).toBeTruthy();
        expect(within(evidenceCard).getByText(/客户仍然没有听到量化证据。/)).toBeTruthy();
        expect((within(evidenceCard).getByRole("link", { name: "最近报告" }) as HTMLAnchorElement).href).toContain(
            "/practice/session-evidence-latest/report",
        );

        const retryHref = (within(evidenceCard).getByRole("link", { name: /按问题再练/ }) as HTMLAnchorElement)
            .getAttribute("href") || "";
        expect(retryHref).toContain("/training/sales?focus_intent=");
        const focusIntent = JSON.parse(
            decodeURIComponent(new URL(`http://localhost${retryHref}`).searchParams.get("focus_intent") || "{}"),
        ) as { source_session_id?: string; main_issue?: { issue_type?: string } };
        expect(focusIntent.source_session_id).toBe("session-evidence-latest");
        expect(focusIntent.main_issue?.issue_type).toBe("evidence_gap");
        expect(screen.queryByText("证据不足复练")).toBeNull();
    });

    it("shows an issue aggregation fallback when history has no retry-eligible evidence", async () => {
        getMyHistoryMock.mockResolvedValue({
            sessions: [
                {
                    session_id: "session-not-ready",
                    scenario_name: "销售演练",
                    scenario_type: "sales",
                    persona_name: "采购经理",
                    agent_name: "销售教练",
                    start_time: "2026-03-23T00:00:00Z",
                    duration_seconds: 60,
                    overall_score: null,
                    report_status: "pending",
                    report_generated_at: null,
                    status: "completed",
                    evaluable: false,
                    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
                    evidence_completeness: { complete: false },
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
            total_practice_time_seconds: 60,
            total_practice_time_minutes: 1,
        });
        getHistoryTrendsMock.mockResolvedValue([]);

        render(<HistoryPage />);

        expect(await screen.findByText(/暂无可用于按问题复练的记录/)).toBeTruthy();
        expect(screen.queryByText(/按问题再练/)).toBeNull();
    });
});
