import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    scenario_type: "sales" as const,
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

const basePresentationReview = {
    overall_score: 88,
    dimension_scores: [
        { name: "流畅连贯性", score: 90, weight: 0.22, description: "讲解节奏、重复情况与口头语控制。" },
        { name: "准确性", score: 86, weight: 0.2, description: "内容与资料一致性、错误信息控制。" },
        { name: "专业性", score: 84, weight: 0.18, description: "术语使用、结构组织与专业说服力。" },
        { name: "生动性", score: 82, weight: 0.14, description: "表达感染力、案例化与记忆点设计。" },
        { name: "互动问答", score: 80, weight: 0.14, description: "对提问的回应质量与现场互动承接。" },
        { name: "其他表现", score: 78, weight: 0.12, description: "时间控制、状态管理与其他综合表现。" },
    ],
    page_summaries: [
        {
            page_number: 1,
            stage_number: 1,
            start_turn: 1,
            end_turn: 2,
            average_score: 88,
            key_points: ["业务目标", "客户问题"],
            matched_required_points: ["业务目标", "客户问题"],
            missing_required_points: [],
            summary: "第一页完整讲清业务目标与客户问题。",
        },
        {
            page_number: 2,
            stage_number: 2,
            start_turn: 3,
            end_turn: 4,
            average_score: 84,
            key_points: ["ROI结果", "客户案例"],
            matched_required_points: ["ROI结果"],
            missing_required_points: ["客户案例"],
            summary: "第二页补充了 ROI 结果，但客户案例展开不够具体。",
        },
    ],
    required_talking_points: {
        status: "complete" as const,
        total: 3,
        covered: 2,
        missing: 1,
        coverage_ratio: 2 / 3,
    },
    issue_counts: {
        forbidden_word: 1,
        missing_point: 1,
        vague_response: 1,
    },
    strengths: ["表达流畅", "页间衔接自然"],
    improvements: ["补足客户案例细节"],
    recommendations: ["下一轮按页准备必须讲到的案例与 ROI 证据。"],
    detailed_feedback: "整体讲解稳定，但第二页的案例支撑仍不够扎实。",
    has_page_metadata: true,
    coverage_status: "complete" as const,
    diagnostics: {
        has_page_metadata: true,
        pages_with_messages: 2,
        total_pages: 2,
        page_coverage_ratio: 1,
        required_points_total: 3,
        required_points_covered: 2,
        required_points_missing: 1,
        required_coverage_ratio: 2 / 3,
        degraded_reasons: [],
    },
};

const basePresentationReport = {
    session_id: "session-1",
    scenario_type: "presentation" as const,
    logic_score: 90,
    accuracy_score: 86,
    completeness_score: 81,
    overall_score: 88,
    suggestions: ["下一轮继续补强第二页案例细节。"],
    audio_url: null,
    transcript_url: null,
    voice_policy_snapshot_ref: null,
    effectiveness_snapshot: null,
    pass_flags: null,
    main_capability_passed: null,
    overall_result: null,
    main_issue: null,
    next_goal: null,
    stage_summary: [],
    evaluable: null,
    not_evaluable_reason: null,
    evidence_completeness: {
        complete: true,
        scenario_type: "presentation",
        presentation_review_available: true,
        page_metadata_complete: true,
        page_summary_count: 2,
        required_talking_points_status: "complete",
        required_points_total: 3,
        required_points_covered: 2,
        required_points_missing: 1,
        required_coverage_ratio: 2 / 3,
        degraded_reasons: [],
    },
    presentation_review: basePresentationReview,
    retry_entry: {
        scenario_type: "presentation" as const,
        presentation_id: "presentation-1",
        agent_id: null,
        persona_id: null,
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

    it("renders canonical presentation review, skips knowledge-check noise, and keeps retry linked to the same presentation", async () => {
        getReportMock.mockResolvedValue(basePresentationReport);
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("88");
        expect(screen.getByText("PPT 复盘报告")).toBeTruthy();
        expect(screen.getByText("PPT 表达能力总览")).toBeTruthy();
        expect(screen.getByText("流畅连贯性")).toBeTruthy();
        expect(screen.getByText("互动问答")).toBeTruthy();
        expect(screen.getByText("逐页总结")).toBeTruthy();
        expect(screen.getByText("第一页完整讲清业务目标与客户问题。")).toBeTruthy();
        expect(screen.getByText("第二页补充了 ROI 结果，但客户案例展开不够具体。")).toBeTruthy();
        expect(screen.getByText("要点覆盖与表达诊断")).toBeTruthy();
        expect(screen.getByText("2 / 3 已覆盖")).toBeTruthy();
        expect(screen.getByText("禁用词提醒")).toBeTruthy();
        expect(screen.getByText("遗漏要点")).toBeTruthy();
        expect(await screen.findByText("综合洞察暂不可用，当前页面仍展示基于课件证据的 PPT 复盘。")).toBeTruthy();
        expect(screen.queryByText("销售推进结果")).toBeNull();
        expect(screen.queryByText("销售推进基线")).toBeNull();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
        expect(getKnowledgeCheckMock).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "按目标再练一轮" }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledWith({
                scenario_type: "presentation",
                agent_id: undefined,
                persona_id: undefined,
                presentation_id: "presentation-1",
            });
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/retry-1?scenario_type=presentation&presentation_id=presentation-1",
        );
    });

    it("shows presentation-specific degraded copy instead of falling back to sales UI when page metadata is missing", async () => {
        getReportMock.mockResolvedValue({
            ...basePresentationReport,
            overall_score: 79,
            evidence_completeness: {
                complete: false,
                scenario_type: "presentation",
                presentation_review_available: true,
                page_metadata_complete: false,
                page_summary_count: 0,
                required_talking_points_status: "degraded",
                required_points_total: 3,
                required_points_covered: 2,
                required_points_missing: 1,
                required_coverage_ratio: 2 / 3,
                degraded_reasons: ["missing_page_metadata"],
            },
            presentation_review: {
                ...basePresentationReview,
                page_summaries: [],
                required_talking_points: {
                    status: "degraded",
                    total: 3,
                    covered: 2,
                    missing: 1,
                    coverage_ratio: 2 / 3,
                },
                coverage_status: "degraded",
                has_page_metadata: false,
                diagnostics: {
                    ...basePresentationReview.diagnostics,
                    has_page_metadata: false,
                    pages_with_messages: 0,
                    page_coverage_ratio: 0,
                    degraded_reasons: ["missing_page_metadata"],
                },
            },
        });
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("79");
        expect(screen.getByText("当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。")).toBeTruthy();
        expect(screen.getByText("逐页总结暂不可用")).toBeTruthy();
        expect(screen.getByRole("button", { name: "按目标再练一轮" })).toBeTruthy();
        expect(screen.queryByText("销售推进结果")).toBeNull();
        expect(screen.queryByText("销售推进基线")).toBeNull();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
        expect(getKnowledgeCheckMock).not.toHaveBeenCalled();
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
