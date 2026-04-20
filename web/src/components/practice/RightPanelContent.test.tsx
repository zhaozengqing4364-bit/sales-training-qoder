import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RightPanelContent } from "./RightPanelContent";

const baseProps = {
    scenarioType: "sales" as const,
    presentationId: undefined,
    currentSlide: null,
    points: [],
    forbiddenWords: [],
    liveSessionSummary: null,
    salesStage: {
        current_stage: "objection",
        stage_name: "异议处理",
        key_actions: ["先回应风险", "再补证据"],
        guidance: "保持问题澄清后再推进下一步",
        progress: 0.72,
    },
    coachHealth: {
        status: "healthy" as const,
        reason: null,
        message: "实时辅导正常。",
    },
    sendMessage: vi.fn(),
};

describe("RightPanelContent", () => {
    it("shows coach degraded state without hiding the active practice guidance", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                    },
                }}
                actionCard={null}
                fuzzyDetections={[]}
                coachHealth={{
                    status: "degraded",
                    reason: "capability_pipeline_failed",
                    message: "实时辅导暂不可用，训练仍可继续。",
                }}
            />,
        );

        expect(screen.getByText("辅导状态")).toBeTruthy();
        expect(screen.getByText("实时辅导暂不可用，训练仍可继续。")).toBeTruthy();
        expect(screen.getByText("当前阶段")).toBeTruthy();
        expect(screen.getByText("销售维度得分")).toBeTruthy();
    });

    it("shows resumed coach state on the same learner panel", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 86,
                    turn_count: 5,
                    stage_name: "异议处理",
                    suggestions: ["继续补 ROI 证据"],
                    dimension_scores: {
                        价值表达: 86,
                    },
                }}
                actionCard={null}
                fuzzyDetections={[]}
                coachHealth={{
                    status: "resumed",
                    reason: "capability_pipeline_resumed",
                    message: "实时辅导已恢复，后续建议会继续更新。",
                }}
            />,
        );

        expect(screen.getByText("辅导状态")).toBeTruthy();
        expect(screen.getByText("实时辅导已恢复，后续建议会继续更新。")).toBeTruthy();
    });

    it("renders the stable same-session cue from backend summary while keeping stage and score context visible", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                        客户收益连接: 84,
                        证据使用: 79,
                    },
                }}
                liveSessionSummary={{
                    alignment_used: true,
                    stage_key: "objection",
                    focus_type: "evidence_gap",
                    fallback_reason: null,
                    main_issue: {
                        issue_type: "evidence_gap",
                        issue_text: "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
                        recovery_rule: "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
                    },
                    next_goal: {
                        goal_type: "evidence_backing",
                        goal_text: "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                        rule: "至少补上一条证据和一个明确的下一步动作。",
                    },
                    claim_truth: {
                        status: "evidence_pending",
                        label: "证据待补齐",
                        source: "objection_ledger",
                        reason: "open_objection_ledger",
                        closure_state: "open",
                    },
                }}
                actionCard={null}
                fuzzyDetections={[]}
            />,
        );

        expect(screen.getByText("当前同 session 结论")).toBeTruthy();
        expect(screen.getByText("主问题 · 证据支撑")).toBeTruthy();
        expect(screen.getByText("价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。")).toBeTruthy();
        expect(screen.getByText("修正动作：下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。")).toBeTruthy();
        expect(screen.getByText("下一轮目标 · 证据补强")).toBeTruthy();
        expect(screen.getByText("先用案例、数据或ROI证据支撑主张，再推进下一步。")).toBeTruthy();
        expect(screen.getByText("判定条件：至少补上一条证据和一个明确的下一步动作。")).toBeTruthy();
        expect(screen.getByText("主张证据状态 · 证据待补齐")).toBeTruthy();
        expect(screen.getByText("当前仍在补证据或有效互动不足，暂时不能判定这条主张已经成立。")).toBeTruthy();
        expect(screen.getByText("当前异议仍未闭环。")).toBeTruthy();
        expect(screen.getByText("当前阶段")).toBeTruthy();
        expect(screen.getByText("销售维度得分")).toBeTruthy();
    });

    it("keeps the stable same-session cue visible while transient action-card coaching is shown", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                        客户收益连接: 84,
                        证据使用: 79,
                    },
                }}
                liveSessionSummary={{
                    alignment_used: true,
                    stage_key: "objection",
                    focus_type: "evidence_gap",
                    fallback_reason: null,
                    main_issue: {
                        issue_type: "evidence_gap",
                        issue_text: "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
                        recovery_rule: "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
                    },
                    next_goal: {
                        goal_type: "evidence_backing",
                        goal_text: "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                        rule: "至少补上一条证据和一个明确的下一步动作。",
                    },
                    claim_truth: {
                        status: "weak_evidence",
                        label: "证据偏弱",
                        source: "score_snapshot",
                        reason: "low_evidence_score",
                        evidence_score: 61,
                    },
                }}
                actionCard={{
                    issue: "直接跳到报价",
                    replacement: "我先确认预算审批链路，再给你报价区间。",
                    next_turn_rule: "下一轮先确认预算与决策人。",
                }}
                fuzzyDetections={[]}
            />,
        );

        expect(screen.getByText("当前同 session 结论")).toBeTruthy();
        expect(screen.getByText("本轮唯一动作")).toBeTruthy();
        expect(screen.getByText("先补一个 ROI 证据，再回应价格异议")).toBeTruthy();
    });

    it("stays quiet when there is no live same-session summary", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={null}
                actionCard={null}
                fuzzyDetections={[]}
            />,
        );

        expect(screen.queryByText("当前同 session 结论")).toBeNull();
    });

    it("stays quiet when coach health is healthy or missing a non-healthy message", () => {
        const { rerender } = render(
            <RightPanelContent
                {...baseProps}
                scores={null}
                actionCard={null}
                fuzzyDetections={[]}
                coachHealth={{
                    status: "healthy",
                    reason: null,
                    message: "实时辅导正常。",
                }}
            />,
        );

        expect(screen.queryByText("辅导状态")).toBeNull();

        rerender(
            <RightPanelContent
                {...baseProps}
                scores={null}
                actionCard={null}
                fuzzyDetections={[]}
                coachHealth={{
                    status: "degraded",
                    reason: "capability_pipeline_failed",
                } as never}
            />,
        );

        expect(screen.queryByText("辅导状态")).toBeNull();
    });

    it("treats action_card as the only primary textual coach surface while keeping stage and score context visible", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                        客户收益连接: 84,
                        证据使用: 79,
                    },
                }}
                actionCard={{
                    issue: "直接跳到报价",
                    replacement: "我先确认预算审批链路，再给你报价区间。",
                    next_turn_rule: "下一轮先确认预算与决策人。",
                }}
                fuzzyDetections={[
                    {
                        category: "feedback",
                        matched: [],
                        suggestion: "先别急着报价。",
                        severity: "medium",
                    },
                ]}
            />,
        );

        expect(screen.getByText("本轮唯一动作")).toBeTruthy();
        expect(screen.getByText("直接跳到报价")).toBeTruthy();
        expect(screen.getByText("我先确认预算审批链路，再给你报价区间。")).toBeTruthy();
        expect(screen.getByText("下一轮先确认预算与决策人。")).toBeTruthy();
        expect(screen.getByText("先补一个 ROI 证据，再回应价格异议")).toBeTruthy();

        expect(screen.getByText("当前阶段")).toBeTruthy();
        expect(screen.getByText("异议处理")).toBeTruthy();
        expect(screen.getByText("销售维度得分")).toBeTruthy();
        expect(screen.getByText("价值表达")).toBeTruthy();
        expect(screen.getByText("客户收益连接")).toBeTruthy();
        expect(screen.getByText("证据使用")).toBeTruthy();

        expect(screen.queryByText("实时提示")).toBeNull();
        expect(screen.queryByText("改进建议")).toBeNull();
        expect(screen.queryByText("先别急着报价。")).toBeNull();
    });

    it("shows waiting completion status for the active action card", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                    },
                }}
                actionCard={{
                    issue: "直接跳到报价",
                    replacement: "我先确认预算审批链路，再给你报价区间。",
                    next_turn_rule: "下一轮先确认预算与决策人。",
                }}
                actionCompletionStatus={{
                    state: "waiting",
                    label: "等待你在下一轮尝试",
                    detail: "先按替换句完成下一次回应，系统会继续观察后续分数和建议变化。",
                }}
                fuzzyDetections={[]}
            />,
        );

        expect(screen.getByText("动作完成状态")).toBeTruthy();
        expect(screen.getByText("等待你在下一轮尝试")).toBeTruthy();
    });

    it("shows conservative improved and missed action completion states", () => {
        const { rerender } = render(
            <RightPanelContent
                {...baseProps}
                scores={null}
                actionCard={{
                    issue: "直接跳到报价",
                    replacement: "我先确认预算审批链路，再给你报价区间。",
                    next_turn_rule: "下一轮先确认预算与决策人。",
                }}
                actionCompletionStatus={{
                    state: "improved",
                    label: "本轮已尝试，继续巩固",
                    detail: "后续建议减少或分数上升，说明这次回应已经出现积极信号。",
                }}
                fuzzyDetections={[]}
            />,
        );

        expect(screen.getByText("本轮已尝试，继续巩固")).toBeTruthy();

        rerender(
            <RightPanelContent
                {...baseProps}
                scores={null}
                actionCard={{
                    issue: "直接跳到报价",
                    replacement: "我先确认预算审批链路，再给你报价区间。",
                    next_turn_rule: "下一轮先确认预算与决策人。",
                }}
                actionCompletionStatus={{
                    state: "missed",
                    label: "还未命中判定条件",
                    detail: "已经检测到新的用户回应，但还没有看到建议减少或分数改善，请下一轮继续按判定条件尝试。",
                }}
                fuzzyDetections={[]}
            />,
        );

        expect(screen.getByText("还未命中判定条件")).toBeTruthy();
    });

    it("shows realtime hints and score suggestions when there is no active action card", () => {
        render(
            <RightPanelContent
                {...baseProps}
                scores={{
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                    },
                }}
                actionCard={null}
                fuzzyDetections={[
                    {
                        category: "feedback",
                        matched: [],
                        suggestion: "先别急着报价。",
                        severity: "medium",
                    },
                ]}
            />,
        );

        expect(screen.getByText("实时提示")).toBeTruthy();
        expect(screen.getByText("先别急着报价。")).toBeTruthy();
        expect(screen.getByText("改进建议")).toBeTruthy();
        expect(screen.getByText("先补一个 ROI 证据，再回应价格异议")).toBeTruthy();
    });
});
