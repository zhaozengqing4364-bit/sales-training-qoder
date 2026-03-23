import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReportPage from "./page";
import { ApiRequestError } from "@/lib/api/client";

const {
    pushMock,
    getReportMock,
    getKnowledgeCheckMock,
    getHighlightsMock,
    createSessionMock,
    getComprehensiveReportMock,
    generateComprehensiveReportMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    getReportMock: vi.fn(),
    getKnowledgeCheckMock: vi.fn(),
    getHighlightsMock: vi.fn(),
    createSessionMock: vi.fn(),
    getComprehensiveReportMock: vi.fn(),
    generateComprehensiveReportMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useParams: () => ({
        sessionId: "session-1",
    }),
}));

vi.mock("@/components/highlights", () => ({
    HighlightList: ({ highlights }: { highlights: Array<{ id: string }> }) => (
        <div data-testid="highlight-list">高光数:{highlights.length}</div>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            sessions: {
                ...actual.api.sessions,
                getReport: getReportMock,
                getKnowledgeCheck: getKnowledgeCheckMock,
                getHighlights: getHighlightsMock,
            },
            practice: {
                ...actual.api.practice,
                createSession: createSessionMock,
            },
            admin: {
                ...actual.api.admin,
                getComprehensiveReport: getComprehensiveReportMock,
                generateComprehensiveReport: generateComprehensiveReportMock,
            },
        },
    };
});

const baseReport = {
    session_id: "session-1",
    logic_score: 68,
    accuracy_score: 74,
    completeness_score: 70,
    overall_score: 72,
    suggestions: ["先补足轮次后再复盘"],
    audio_url: null,
    transcript_url: null,
    voice_policy_snapshot_ref: null,
    effectiveness_snapshot: null,
    pass_flags: null,
    main_capability_passed: false,
    overall_result: "fail" as const,
    main_issue: {
        issue_type: "insufficient_turns",
        issue_text: "有效回合不足，无法判断完整销售闭环。",
        recovery_rule: "至少完成 3 轮有效问答。",
    },
    next_goal: null,
    stage_summary: [
        {
            stage: "opening",
            duration_ms: 90000,
            score: 72,
        },
    ],
    evaluable: false,
    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
    evidence_completeness: {
        complete: false,
        missing_fields: ["closing_stage"],
        message_count: 2,
    },
    retry_entry: {
        scenario_type: "sales" as const,
        agent_id: "agent-1",
        persona_id: "persona-1",
    },
};

describe("ReportPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        getReportMock.mockReset();
        getKnowledgeCheckMock.mockReset();
        getHighlightsMock.mockReset();
        createSessionMock.mockReset();
        getComprehensiveReportMock.mockReset();
        generateComprehensiveReportMock.mockReset();

        getKnowledgeCheckMock.mockRejectedValue(new Error("knowledge check unavailable"));
        getHighlightsMock.mockResolvedValue({
            highlights: [],
            total_good: 0,
            total_bad: 0,
        });
        createSessionMock.mockResolvedValue({ session_id: "retry-1" });
    });

    it("renders sales rollup cards and sales-specific issue/goal copy from the unified report contract", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            logic_score: 84,
            accuracy_score: 73,
            completeness_score: 69,
            overall_score: 76,
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: {
                issue_type: "value_gap",
                issue_text: "功能点说得多，但还没有把产品价值翻译成客户收益。",
                recovery_rule: "下一轮先用客户收益语言重述价值，再回应价格顾虑。",
            },
            next_goal: {
                goal_type: "objection_progress",
                goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                rule: "至少给出一条证据并确认下一步。",
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 91,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("76");
        expect(screen.getByText("销售能力总览")).toBeTruthy();
        expect(screen.getByText("价值表达")).toBeTruthy();
        expect(screen.getByText("证据与收益")).toBeTruthy();
        expect(screen.getByText("异议推进")).toBeTruthy();
        expect(screen.getByText("功能点说得多，但还没有把产品价值翻译成客户收益。")).toBeTruthy();
        expect(screen.getByText("先补 ROI 证据，再推进一个明确的下一步动作。")).toBeTruthy();
        expect(screen.getByText("综合评分反映价值翻译、证据支撑和异议推进的完成度。"))
            .toBeTruthy();
    });

    it("trusts the unified evidence contract for overall score and evaluability even when comprehensive data conflicts", async () => {
        getReportMock.mockResolvedValue(baseReport);
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 95,
            dimension_scores: [
                { name: "逻辑性", score: 95, weight: 0.34, description: "冲突分数" },
            ],
            stage_summaries: [
                { stage_number: 1, start_turn: 1, end_turn: 2, average_score: 95, key_points: [], summary: "冲突阶段" },
            ],
            key_strengths: ["增强洞察"],
            key_improvements: ["增强建议"],
            detailed_feedback: "增强内容",
            recommendations: ["增强练习建议"],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        await waitFor(() => {
            expect(getReportMock).toHaveBeenCalledWith("session-1");
        });

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("72");
        expect(screen.queryByText("导出报告")).toBeNull();
        expect(screen.getByText("当前会话暂不可评估")).toBeTruthy();
        expect(screen.getByText("开场破冰")).toBeTruthy();
        expect(screen.queryByText("95")).toBeNull();
    });

    it("keeps the evidence view stable when enhanced report and highlights are unavailable", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            overall_score: 61,
            logic_score: 60,
            accuracy_score: 62,
            completeness_score: 61,
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: null,
        });
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));
        getHighlightsMock.mockRejectedValue(new Error("highlights unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("61");
        expect(screen.getByText("综合洞察暂不可用，当前页面仅展示统一训练证据。"))
            .toBeTruthy();
        expect(screen.getByText("高光片段暂不可用，基础评估结果不受影响。"))
            .toBeTruthy();
    });
});
