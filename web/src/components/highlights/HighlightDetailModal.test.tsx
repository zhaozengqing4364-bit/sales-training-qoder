import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HighlightDetailModal } from "./HighlightDetailModal";

const highlight = {
    id: "turn-2",
    turn_number: 2,
    role: "user",
    content: "我们这个方案能帮你省不少钱。",
    timestamp: "2026-03-23T00:00:00Z",
    highlight_type: "bad",
    highlight_reason: "只提了结果，没有给出证据。",
    ai_feedback: "需要补 ROI 或客户案例。",
    suggested_response: "建议改进: 先补一个 30% 降本案例，再确认客户是否认可。",
    sales_stage: "objection",
    stage_name: "异议处理",
    context: {
        prev_message: {
            id: "turn-1",
            role: "assistant",
            content: "客户刚问这个方案凭什么可信。",
            timestamp: "2026-03-23T00:00:00Z",
        },
        next_message: {
            id: "turn-3",
            role: "user",
            content: "如果真有案例我愿意继续听。",
            timestamp: "2026-03-23T00:00:30Z",
        },
    },
    learning_evidence: {
        reason: "客户已经追问可信度，这一轮决定能否继续推进。",
        issue_family: "evidence_gap",
        objection_family: "roi",
        stage: {
            key: "objection",
            name: "异议处理",
        },
        nearby_context: {
            prev_message: {
                id: "turn-1",
                role: "assistant",
                content: "客户刚问这个方案凭什么可信。",
                timestamp: "2026-03-23T00:00:00Z",
            },
            next_message: {
                id: "turn-3",
                role: "user",
                content: "如果真有案例我愿意继续听。",
                timestamp: "2026-03-23T00:00:30Z",
            },
        },
        suggested_response: "先补一条 ROI 证据，再确认客户是否认可。",
        linked_issue: {
            issue_type: "evidence_gap",
            issue_text: "客户收益提到了，但还没有补上可信证据。",
            recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
        },
        linked_goal: {
            goal_type: "evidence_backing",
            goal_text: "先补 ROI 证据，再继续推进下一步。",
            rule: "至少给出一条证据并确认客户是否认可。",
        },
    },
} as const;

describe("HighlightDetailModal", () => {
    it("renders the richer learning evidence, linked issue, goal, and better response", async () => {
        render(
            <HighlightDetailModal
                isOpen
                onClose={vi.fn()}
                highlight={highlight as never}
            />,
        );

        expect(await screen.findByText("高光片段详情")).toBeTruthy();
        expect(screen.getByText("证据支撑")).toBeTruthy();
        expect(screen.getByText("为什么值得复盘")).toBeTruthy();
        expect(screen.getByText("客户已经追问可信度，这一轮决定能否继续推进。")).toBeTruthy();
        expect(screen.getByText("关联问题")).toBeTruthy();
        expect(screen.getByText("客户收益提到了，但还没有补上可信证据。")).toBeTruthy();
        expect(screen.getByText("下一轮目标")).toBeTruthy();
        expect(screen.getByText("先补 ROI 证据，再继续推进下一步。")).toBeTruthy();
        expect(screen.getByText("更好的回应")).toBeTruthy();
        expect(screen.getByText("先补一条 ROI 证据，再确认客户是否认可。")).toBeTruthy();
        expect(screen.getByText("上一轮")).toBeTruthy();
        expect(screen.getByText("下一轮")).toBeTruthy();
    });

    it("stays empty when no highlight is selected", () => {
        const { container } = render(
            <HighlightDetailModal isOpen={false} onClose={vi.fn()} highlight={null} />,
        );

        expect(container.firstChild).toBeNull();
    });
});
