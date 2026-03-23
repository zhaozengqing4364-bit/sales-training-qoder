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
    HighlightList: ({ highlights }: { highlights: Array<{ id: string }> }) => (
        <div data-testid="replay-highlight-list">高光数:{highlights.length}</div>
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
            effectiveness_snapshot: null,
            pass_flags: null,
            main_capability_passed: false,
            overall_result: "fail",
            main_issue: null,
            next_goal: null,
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
                    role: "user",
                    content: "来自 replay 的统一消息",
                    timestamp: "2026-03-23T00:00:00Z",
                    audio_url: null,
                    duration_ms: 1200,
                    score_snapshot: {
                        overall_score: 78,
                    },
                    ai_feedback: "继续补充需求确认",
                    is_highlight: false,
                    highlight_type: null,
                    highlight_reason: null,
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
                    id: "turn-1",
                    turn_number: 1,
                    role: "user",
                    content: "高光片段",
                    timestamp: "2026-03-23T00:00:00Z",
                    highlight_type: "good",
                    highlight_reason: "开场清晰",
                    ai_feedback: null,
                    suggested_response: null,
                    sales_stage: "opening",
                    stage_name: "开场破冰",
                    context: {},
                    audio_url: null,
                    score: 78,
                },
            ],
            total_good: 1,
            total_bad: 0,
        });

        render(<SessionReplayPage />);

        await waitFor(() => {
            expect(getReplayMock).toHaveBeenCalledWith("session-1");
        });

        const overallScore = await screen.findByTestId("replay-overall-score");
        expect(overallScore.textContent).toContain("78");
        expect(screen.getByText("当前会话暂不可评估")).toBeTruthy();
        expect(screen.getByText("来自 replay 的统一消息")).toBeTruthy();
        expect(screen.queryByText("来自 /messages 的冲突消息")).toBeNull();
        expect(getMessagesMock).not.toHaveBeenCalled();
    });
});
