import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RightPanelContent } from "./RightPanelContent";

const baseProps = {
    scenarioType: "sales" as const,
    presentationId: undefined,
    currentSlide: null,
    points: [],
    forbiddenWords: [],
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
