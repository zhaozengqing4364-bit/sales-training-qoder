import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SessionReplayPage from "./page";

const {
    pushMock,
    backMock,
    getReplayMock,
    getMessagesMock,
    getHighlightsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    backMock: vi.fn(),
    getReplayMock: vi.fn(),
    getMessagesMock: vi.fn(),
    getHighlightsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
        back: backMock,
    }),
    useParams: () => ({
        sessionId: "session-1",
    }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/components/highlights", () => ({
    HighlightList: ({ highlights }: { highlights: Array<any> }) => (
        <div data-testid="replay-highlight-list">
            <div>高光数:{highlights.length}</div>
            <div>高光学习证据:{highlights[0]?.learning_evidence?.reason ?? "none"}</div>
            <div>高光问题家族:{highlights[0]?.learning_evidence?.issue_family ?? "none"}</div>
        </div>
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
                getReplay: getReplayMock,
                getMessages: getMessagesMock,
                getHighlights: getHighlightsMock,
            },
        },
    };
});

describe("SessionReplayPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        backMock.mockReset();
        getReplayMock.mockReset();
        getMessagesMock.mockReset();
        getHighlightsMock.mockReset();
    });

    it("renders the unified replay evidence without stitching conflicting messages", async () => {
        getReplayMock.mockResolvedValue({
            session_id: "session-1",
            agent_name: "销售教练",
            persona_name: "采购经理",
            voice_policy_snapshot_ref: null,
            total_duration_ms: 185000,
            overall_score: 78,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "evidence_verified",
                    label: "证据已验证",
                    source: "objection_ledger",
                    reason: "evidence_provided",
                    evidence_score: 82,
                    closure_state: "evidence_provided",
                },
            },
            pass_flags: null,
            main_capability_passed: false,
            overall_result: "fail",
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "客户收益提到了，但还没有补上可信证据。",
                recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再继续推进下一步。",
                rule: "至少给出一条证据并确认客户是否认可。",
            },
            evaluable: false,
            not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
            evidence_completeness: {
                complete: false,
                missing_fields: ["closing_stage"],
                message_count: 2,
            },
            messages: [
                {
                    id: "turn-1",
                    session_id: "session-1",
                    turn_number: 1,
                    role: "assistant",
                    content: "客户刚问这个方案凭什么可信。",
                    timestamp: "2026-03-23T00:00:00Z",
                    audio_url: null,
                    duration_ms: 1200,
                    score_snapshot: {
                        overall_score: 78,
                    },
                    ai_feedback: null,
                    is_highlight: false,
                    highlight_type: null,
                    highlight_reason: null,
                },
                {
                    id: "turn-2",
                    session_id: "session-1",
                    turn_number: 2,
                    role: "user",
                    content: "我们这个方案能帮你省不少钱。",
                    timestamp: "2026-03-23T00:00:15Z",
                    audio_url: null,
                    duration_ms: 1500,
                    sales_stage: "objection",
                    stage_name: "异议处理",
                    score_snapshot: {
                        overall_score: 62,
                    },
                    ai_feedback: "需要补 ROI 或客户案例。",
                    is_highlight: true,
                    highlight_type: "bad",
                    highlight_reason: "只提了结果，没有给出证据。",
                    learning_evidence: {
                        reason: "客户已经追问可信度，这一轮决定能否继续推进。",
                        issue_family: "evidence_gap",
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
                            next_message: null,
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
                },
            ],
            timeline_markers: [],
            stage_summary: [
                {
                    stage: "opening",
                    duration_ms: 60000,
                    score: 78,
                },
            ],
        });
        getMessagesMock.mockResolvedValue({
            messages: [
                {
                    id: "legacy-1",
                    session_id: "session-1",
                    turn_number: 1,
                    role: "user",
                    content: "来自 /messages 的冲突消息",
                    timestamp: "2026-03-23T00:00:00Z",
                },
            ],
            total: 1,
        });
        getHighlightsMock.mockResolvedValue({
            highlights: [
                {
                    id: "turn-2",
                    turn_number: 2,
                    role: "user",
                    content: "我们这个方案能帮你省不少钱。",
                    timestamp: "2026-03-23T00:00:15Z",
                    highlight_type: "bad",
                    highlight_reason: "只提了结果，没有给出证据。",
                    ai_feedback: "需要补 ROI 或客户案例。",
                    suggested_response: "先补一条 ROI 证据，再确认客户是否认可。",
                    sales_stage: "objection",
                    stage_name: "异议处理",
                    context: {},
                    audio_url: null,
                    score: 62,
                    learning_evidence: {
                        reason: "客户已经追问可信度，这一轮决定能否继续推进。",
                        issue_family: "evidence_gap",
                    },
                },
            ],
            total_good: 0,
            total_bad: 1,
        });

        render(<SessionReplayPage />);

        await waitFor(() => {
            expect(getReplayMock).toHaveBeenCalledWith("session-1");
        });

        const overallScore = await screen.findByTestId("replay-overall-score");
        expect(overallScore.textContent).toContain("78");
        expect(screen.getByText("当前会话暂不可评估")).toBeTruthy();
        expect(screen.getByText("主张证据状态")).toBeTruthy();
        expect(screen.getByText("证据已验证")).toBeTruthy();
        expect(screen.getByText("当前主张已有足够证据支撑，可以继续沿着这条事实线推进下一步。")).toBeTruthy();
        expect(screen.getByText("证据强度：82 分。本轮补充的证据已达到可验证水平。")).toBeTruthy();
        expect(screen.getByText("本场教练结论")).toBeTruthy();
        expect(screen.getAllByText("证据支撑").length).toBeGreaterThanOrEqual(2);
        expect(screen.getAllByText("客户收益提到了，但还没有补上可信证据。").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("先补 ROI 证据，再继续推进下一步。").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("证据补强").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("客户刚问这个方案凭什么可信。").length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText("我们这个方案能帮你省不少钱。")).toBeTruthy();
        expect(screen.getByText("为什么这轮关键")).toBeTruthy();
        expect(screen.getByText("客户已经追问可信度，这一轮决定能否继续推进。")).toBeTruthy();
        expect(screen.getByText("更优回应")).toBeTruthy();
        expect(screen.getByText("先补一条 ROI 证据，再确认客户是否认可。")).toBeTruthy();
        expect(screen.getByText("高光学习证据:客户已经追问可信度，这一轮决定能否继续推进。"));
        expect(screen.getByText("高光问题家族:evidence_gap"));
        expect(screen.queryByText("来自 /messages 的冲突消息")).toBeNull();
        expect(getMessagesMock).not.toHaveBeenCalled();
    });
});
