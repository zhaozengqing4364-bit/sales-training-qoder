import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockStartChat = vi.fn();
const mockSendChat = vi.fn();
const mockSubmitEvent = vi.fn();
const mockStartChatStream = vi.fn();
const mockSendChatStream = vi.fn();
const mockSubmitEventStream = vi.fn();

vi.mock("@/lib/api/client", () => ({
    api: {
        newcomerTraining: {
            startAiCoachChatSession: (...args: unknown[]) => mockStartChat(...args),
            startAiCoachChatSessionStream: (...args: unknown[]) => mockStartChatStream(...args),
            sendAiCoachChatMessage: (...args: unknown[]) => mockSendChat(...args),
            sendAiCoachChatMessageStream: (...args: unknown[]) => mockSendChatStream(...args),
            submitAiCoachChatEventAnswer: (...args: unknown[]) => mockSubmitEvent(...args),
            submitAiCoachChatEventAnswerStream: (...args: unknown[]) => mockSubmitEventStream(...args),
        },
    },
    getApiErrorMessage: (err: unknown) =>
        err instanceof Error ? err.message : String(err),
}));

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}));

import AiCoachPage from "./page";

type ChatSession = { readonly session_id: string };

async function* streamSession<T extends ChatSession>(session: T) {
    yield {
        type: "status" as const,
        phase: "generating_next_card" as const,
        message: "正在生成训练内容。",
        session_id: session.session_id,
    };
    yield {
        type: "session_snapshot" as const,
        phase: "completed" as const,
        session,
    };
}

const welcomeSession = {
    session_id: "s1",
    module_key: "business_skills",
    status: "in_progress" as const,
    created_at: "2026-06-12T00:00:00Z",
    updated_at: "2026-06-12T00:00:00Z",
    messages: [
        {
            message_id: "m1",
            role: "assistant" as const,
            content: "你好，我是商务技巧 AI 教练。",
            order_index: 1,
            created_at: "2026-06-12T00:00:00Z",
        },
    ],
    ui_events: [],
    coach_state: null,
};

const activeCoachState = {
    session_phase: "answering" as const,
    active_event_id: "e1",
    auto_step_count: 1,
    answered_card_count: 0,
    correct_streak: 0,
    incorrect_streak: 0,
    current_focus: "商务礼仪",
    difficulty: "warmup" as const,
    last_action: "continue_drill" as const,
    can_auto_advance: true,
    stopped_reason: null,
};

const cardSession = {
    ...welcomeSession,
    coach_state: activeCoachState,
    messages: [
        ...welcomeSession.messages,
        {
            message_id: "m2",
            role: "user" as const,
            content: "出 3 道商务礼仪单选题",
            order_index: 2,
            created_at: "2026-06-12T00:01:00Z",
        },
        {
            message_id: "m3",
            role: "assistant" as const,
            content: "可以，我们先做三张商务礼仪情境卡。",
            order_index: 3,
            created_at: "2026-06-12T00:01:02Z",
        },
    ],
    ui_events: ["e1", "e2", "e3"].map((eventId, index) => ({
        event_id: eventId,
        message_id: "m3",
        type: "quiz_card" as const,
        status: "pending" as const,
        payload: {
            interaction: {
                schema_version: "ai_coach_interaction_public_v1" as const,
                interaction_id: eventId,
                session_id: "s1",
                turn_number: index + 1,
                interaction_type: "single_choice" as const,
                stem: `第 ${index + 1} 题：客户到访前应该先确认什么？`,
                options: [
                    { option_id: "A", text: "到访时间、人数和接待安排" },
                    { option_id: "B", text: "直接发送宣传册" },
                ],
                answer_constraints: { min_selected: 1, max_selected: 1 },
            },
            explanation: "拜访前先确认接待条件。",
        },
        answer_payload: null,
        score_result: null,
        order_index: index + 1,
        created_at: "2026-06-12T00:01:02Z",
    })),
};

const scoredSession = {
    ...cardSession,
    coach_state: {
        ...activeCoachState,
        session_phase: "answering" as const,
        active_event_id: "e2",
        answered_card_count: 1,
    },
    ui_events: [
        {
            ...cardSession.ui_events[0],
            status: "scored" as const,
            answer_payload: { variant: "choice" as const, option_ids: ["A"] },
            score_result: {
                score: 100,
                max_score: 100,
                mastery_threshold: 80,
                mastered: true,
                feedback: "处理得当。",
                missed_points: [],
                next_turn_available: true,
                finished: false,
            },
        },
        ...cardSession.ui_events.slice(1),
    ],
};

const promptedSession = {
    ...welcomeSession,
    coach_state: {
        session_phase: "choosing" as const,
        active_event_id: null,
        auto_step_count: 1,
        answered_card_count: 1,
        correct_streak: 0,
        incorrect_streak: 1,
        current_focus: "客户异议",
        difficulty: "warmup" as const,
        last_action: "ask_user_choice" as const,
        can_auto_advance: false,
        stopped_reason: null,
    },
    messages: [
        ...welcomeSession.messages,
        {
            message_id: "m4",
            role: "assistant" as const,
            content: "这一步先让你选方向。",
            order_index: 2,
            created_at: "2026-06-12T00:02:00Z",
        },
    ],
    ui_events: [
        {
            event_id: "e4",
            message_id: "m4",
            type: "followup_prompt" as const,
            status: "pending" as const,
            payload: {
                prompts: ["换成客户异议", "总结一下"],
            },
            answer_payload: null,
            score_result: null,
            order_index: 1,
            created_at: "2026-06-12T00:02:00Z",
        },
    ],
};

const summarizedSession = {
    ...cardSession,
    coach_state: {
        ...activeCoachState,
        session_phase: "summarizing" as const,
        active_event_id: null,
        answered_card_count: 1,
        last_action: "summarize" as const,
    },
    messages: [
        ...cardSession.messages,
        {
            message_id: "m4",
            role: "assistant" as const,
            content: "这是本轮训练的阶段复盘。",
            order_index: 4,
            created_at: "2026-06-12T00:03:00Z",
        },
    ],
    ui_events: [
        ...cardSession.ui_events,
        {
            event_id: "summary-1",
            message_id: "m4",
            type: "summary_card" as const,
            status: "shown" as const,
            payload: {
                title: "本轮训练总结",
                items: ["本轮已完成 1 道训练题。"],
                score_percent: 100,
                mastered: true,
                strengths: ["关键动作判断准确。"],
                weaknesses: [],
                next_steps: ["继续做一题新场景。"],
            },
            answer_payload: null,
            score_result: null,
            order_index: 4,
            created_at: "2026-06-12T00:03:00Z",
        },
    ],
};

describe("AiCoachPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        cleanup();
    });

    it("resumes a training session and renders the active card first", async () => {
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));

        render(<AiCoachPage />);

        await waitFor(() => {
            expect(mockStartChatStream).toHaveBeenCalledWith(
                {
                    module_key: "business_skills",
                    resume_strategy: "latest_active_or_new",
                },
                expect.any(AbortSignal),
            );
        });
        expect(await screen.findByText("商务技巧 AI 教练")).toBeTruthy();
        expect(screen.getByText("当前阶段")).toBeTruthy();
        expect(screen.getByText("作答中")).toBeTruthy();
        expect(screen.getByText("第 1 题：客户到访前应该先确认什么？")).toBeTruthy();
        expect(screen.queryByText("第 2 题：客户到访前应该先确认什么？")).toBeNull();
        expect(screen.queryByText("拜访前先确认接待条件。")).toBeNull();
        expect(screen.getByPlaceholderText("作答卡片是主流程；这里可以问教练一句")).toBeTruthy();
    });

    it("keeps free text as an auxiliary coach question", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(welcomeSession));
        mockSendChatStream.mockImplementation(() => streamSession(cardSession));

        render(<AiCoachPage />);

        const input = await screen.findByPlaceholderText("问教练一句，或使用上方操作");
        await user.type(input, "这个场景有什么注意点？");
        await user.click(screen.getByRole("button", { name: "发送" }));

        await waitFor(() => {
            expect(mockSendChatStream).toHaveBeenCalledWith(
                "s1",
                { content: "这个场景有什么注意点？" },
                expect.any(AbortSignal),
            );
        });
        expect(await screen.findByText("可以，我们先做三张商务礼仪情境卡。")).toBeTruthy();
        expect(screen.getAllByText("单选")).toHaveLength(1);
    });

    it("submits a quiz card answer and shows scored feedback", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockSubmitEventStream.mockImplementation(() => streamSession(scoredSession));

        render(<AiCoachPage />);

        const firstCard = await screen.findByText("第 1 题：客户到访前应该先确认什么？");
        const cardRoot = firstCard.closest("section");
        if (cardRoot === null) {
            throw new Error("expected first quiz card section");
        }
        const card = within(cardRoot);
        await user.click(card.getByText("到访时间、人数和接待安排"));
        await user.click(card.getByRole("button", { name: "提交" }));

        await waitFor(() => {
            expect(mockSubmitEventStream).toHaveBeenCalledWith(
                "s1",
                "e1",
                { answer_payload: { variant: "choice", option_ids: ["A"] } },
                expect.any(AbortSignal),
            );
        });
        expect(await screen.findByText("已提交")).toBeTruthy();
        expect(screen.getByText("处理得当。")).toBeTruthy();
        expect(screen.getByText("答对")).toBeTruthy();
        expect(screen.getByText("已达到本轮掌握标准：80%")).toBeTruthy();
        expect(screen.queryByText("100 / 100")).toBeNull();
        expect(screen.getByText("拜访前先确认接待条件。")).toBeTruthy();
    });

    it("shows a clear unavailable state when chat config is disabled", async () => {
        mockStartChatStream.mockImplementation(() => {
            throw new Error("该模块未启用对话式 AI 教练。");
        });

        render(<AiCoachPage />);

        expect(await screen.findByText("商务技巧 AI 教练暂不可用")).toBeTruthy();
        expect(screen.getByText("该模块未启用对话式 AI 教练。")).toBeTruthy();
    });

    it("renders learner-facing coach state and sends followup prompt through chat", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(promptedSession));
        mockSendChatStream.mockImplementation(() => streamSession({
            ...promptedSession,
            messages: [
                ...promptedSession.messages,
                {
                    message_id: "m5",
                    role: "user" as const,
                    content: "换成客户异议",
                    order_index: 3,
                    created_at: "2026-06-12T00:02:05Z",
                },
            ],
        }));

        render(<AiCoachPage />);

        expect(await screen.findByText("等你选择")).toBeTruthy();
        expect(screen.getByText("客户异议")).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "换成客户异议" }));

        await waitFor(() => {
            expect(mockSendChatStream).toHaveBeenCalledWith(
                "s1",
                { content: "换成客户异议" },
                expect.any(AbortSignal),
            );
        });
    });

    it("does not activate pending quiz cards when backend clears active event id", async () => {
        mockStartChatStream.mockImplementation(() => streamSession(summarizedSession));

        render(<AiCoachPage />);

        expect(await screen.findByText("本轮总结")).toBeTruthy();
        expect(screen.getByText("本轮训练总结")).toBeTruthy();
        expect(screen.queryByText("第 1 题：客户到访前应该先确认什么？")).toBeNull();
        expect(screen.getByPlaceholderText("问教练一句，或使用上方操作")).toBeTruthy();
    });

    it("sends fixed coach commands with the active event id", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockSendChatStream.mockImplementation(() => streamSession(cardSession));

        render(<AiCoachPage />);

        await screen.findByText("第 1 题：客户到访前应该先确认什么？");
        await user.click(screen.getByRole("button", { name: "讲解一下" }));

        await waitFor(() => {
            expect(mockSendChatStream).toHaveBeenCalledWith(
                "s1",
                { command: "explain", event_id: "e1" },
                expect.any(AbortSignal),
            );
        });
    });

    it("requires an explicit action before creating a new session", async () => {
        const user = userEvent.setup();
        mockStartChatStream
            .mockImplementationOnce(() => streamSession(cardSession))
            .mockImplementationOnce(() => streamSession({
                ...cardSession,
                session_id: "s2",
            }));

        render(<AiCoachPage />);

        await screen.findByText("第 1 题：客户到访前应该先确认什么？");
        await user.click(screen.getByRole("button", { name: "新开一局" }));

        await waitFor(() => {
            expect(mockStartChatStream).toHaveBeenLastCalledWith(
                {
                    module_key: "business_skills",
                    resume_strategy: "new",
                },
                expect.any(AbortSignal),
            );
        });
    });
});
