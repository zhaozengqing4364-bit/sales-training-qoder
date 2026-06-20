import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
    AiCoachUiEventPublicV1,
    BusinessEtiquetteAiCoachProgress,
    BusinessEtiquetteLearningUnit,
} from "@/lib/api/types";

const mockStartChat = vi.fn();
const mockSendChat = vi.fn();
const mockSubmitEvent = vi.fn();
const mockStartChatStream = vi.fn();
const mockSendChatStream = vi.fn();
const mockSubmitEventStream = vi.fn();
const mockGetBusinessEtiquetteLearningUnits = vi.fn();
const mockGetBusinessEtiquetteAiCoachProgress = vi.fn();

vi.mock("@/lib/api/client", () => ({
    api: {
        newcomerTraining: {
            startAiCoachChatSession: (...args: unknown[]) => mockStartChat(...args),
            startAiCoachChatSessionStream: (...args: unknown[]) => mockStartChatStream(...args),
            sendAiCoachChatMessage: (...args: unknown[]) => mockSendChat(...args),
            sendAiCoachChatMessageStream: (...args: unknown[]) => mockSendChatStream(...args),
            submitAiCoachChatEventAnswer: (...args: unknown[]) => mockSubmitEvent(...args),
            submitAiCoachChatEventAnswerStream: (...args: unknown[]) => mockSubmitEventStream(...args),
            getBusinessEtiquetteLearningUnits: (...args: unknown[]) =>
                mockGetBusinessEtiquetteLearningUnits(...args),
            getBusinessEtiquetteAiCoachProgress: (...args: unknown[]) =>
                mockGetBusinessEtiquetteAiCoachProgress(...args),
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

function createDeferred() {
    let resolve!: () => void;
    const promise = new Promise<void>((promiseResolve) => {
        resolve = promiseResolve;
    });
    return { promise, resolve };
}

async function* streamSessionWithGeneratedCardPending(
    shellSession: ChatSession,
    completedSession: ChatSession,
    gate: { readonly promise: Promise<void> },
) {
    yield {
        type: "status" as const,
        phase: "resolving_session" as const,
        message: "正在检查是否有可继续的训练局。",
        session_id: shellSession.session_id,
    };
    yield {
        type: "session_snapshot" as const,
        phase: "session_ready" as const,
        session: shellSession,
    };
    yield {
        type: "status" as const,
        phase: "generating_first_card" as const,
        message: "正在生成本轮训练计划和第一张题卡。",
        session_id: shellSession.session_id,
    };
    yield {
        type: "ui_event_delta" as const,
        phase: "generating_first_card" as const,
        session_id: shellSession.session_id,
        delta_id: `${shellSession.session_id}:quiz_card`,
        event_type: "quiz_card" as const,
        status: "streaming" as const,
        payload: {
            interaction: {
                schema_version: "ai_coach_interaction_public_draft_v1" as const,
                interaction_id: `stream-${shellSession.session_id}`,
                session_id: shellSession.session_id,
                turn_number: null,
                training_card_type: "scenario_judgment" as const,
                interaction_type: "single_choice" as const,
                stem: "第 1 题：客户到访前应该先确认什么？",
                options: [
                    { option_id: "A", text: "到访时间、人数和接待安排" },
                    { option_id: "B", text: "直接发送宣传册" },
                ],
                answer_constraints: { min_selected: 1, max_selected: 1 },
                capability_keys: ["reception_visit_execution"],
                source_chapter_orders: [5],
                is_complete: false,
            },
            explanation: null,
        },
    };
    await gate.promise;
    yield {
        type: "session_snapshot" as const,
        phase: "completed" as const,
        session: completedSession,
    };
}

async function* streamSessionWithAssistantMarkdownDelta(
    sessionId: string,
    completedSession: ChatSession,
    gate: { readonly promise: Promise<void> },
) {
    yield {
        type: "status" as const,
        phase: "generating_next_card" as const,
        message: "正在组织教练回复。",
        session_id: sessionId,
    };
    yield {
        type: "reasoning_text_delta" as const,
        phase: "generating_next_card" as const,
        session_id: sessionId,
        delta_id: `${sessionId}:reasoning_text`,
        status: "streaming" as const,
        text: "先判断接待目标。",
    };
    yield {
        type: "assistant_text_delta" as const,
        phase: "generating_next_card" as const,
        session_id: sessionId,
        delta_id: `${sessionId}:assistant_text`,
        status: "streaming" as const,
        text: "**建议**\n- 先确认客户到访目标\n- 再安排接待动作",
    };
    await gate.promise;
    yield {
        type: "session_snapshot" as const,
        phase: "completed" as const,
        session: completedSession,
    };
}

async function* streamSessionWithTwoReasoningDeltas(
    sessionId: string,
    completedSession: ChatSession,
    gate: { readonly promise: Promise<void> },
    snapshotGate: { readonly promise: Promise<void> },
) {
    yield {
        type: "status" as const,
        phase: "generating_next_card" as const,
        message: "正在组织教练回复。",
        session_id: sessionId,
    };
    yield {
        type: "reasoning_text_delta" as const,
        phase: "generating_next_card" as const,
        session_id: sessionId,
        delta_id: `${sessionId}:reasoning_text`,
        status: "streaming" as const,
        text: "先判断接待目标。",
    };
    await gate.promise;
    yield {
        type: "reasoning_text_delta" as const,
        phase: "generating_next_card" as const,
        session_id: sessionId,
        delta_id: `${sessionId}:reasoning_text`,
        status: "streaming" as const,
        text: "再判断称呼边界。",
    };
    await snapshotGate.promise;
    yield {
        type: "session_snapshot" as const,
        phase: "completed" as const,
        session: completedSession,
    };
}

async function* streamSubmitAnswerWithNextStepDelta(
    sessionId: string,
    answerScoredSession: ChatSession,
    completedSession: ChatSession,
    gate: { readonly promise: Promise<void> },
) {
    yield {
        type: "status" as const,
        phase: "scoring_answer" as const,
        message: "正在批改当前题卡。",
        session_id: sessionId,
    };
    yield {
        type: "session_snapshot" as const,
        phase: "answer_scored" as const,
        session: answerScoredSession,
    };
    yield {
        type: "status" as const,
        phase: "deciding_next_action" as const,
        message: "正在判断下一步训练动作。",
        session_id: sessionId,
    };
    yield {
        type: "status" as const,
        phase: "generating_next_card" as const,
        message: "正在生成下一步教练回复。",
        session_id: sessionId,
    };
    yield {
        type: "assistant_text_delta" as const,
        phase: "generating_next_card" as const,
        session_id: sessionId,
        delta_id: `${sessionId}:assistant_text`,
        status: "streaming" as const,
        text: "**下一步**：继续练现场引导，我会给你一个表达改写卡。",
    };
    await gate.promise;
    yield {
        type: "session_snapshot" as const,
        phase: "completed" as const,
        session: completedSession,
    };
}

async function* streamBusinessEtiquetteUnitMissingError(sessionId = "s1") {
    yield {
        type: "status" as const,
        phase: "scoring_answer" as const,
        message: "正在批改当前题卡。",
        session_id: sessionId,
    };
    yield {
        type: "error" as const,
        phase: "failed" as const,
        error_code: "[BUSINESS_ETIQUETTE_AI_COACH_UNIT_NOT_FOUND]",
        message: "商务礼仪 AI 教练会话缺少训练小单元快照。",
        recoverable: true,
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

const learningUnit = {
    unit_key: "reception_visit_execution",
    title: "接待与拜访执行",
    description: "信息准备、引导、座次、茶水、送别、拜访跟进。",
    order_index: 4,
    enabled: true,
    source_chapter_orders: [5],
    capability_keys: ["reception_visit_execution"],
    unlock_after_unit_keys: ["business_communication"],
    require_reading: true,
    require_quiz: true,
    require_ai_coach: true,
    quiz_question_count: 5,
    quiz_pass_threshold: null,
    quiz_allow_retake: true,
    quiz_max_attempts: null,
    quiz_question_type_weights: {},
    allow_skip_reading: false,
    block_next_until_complete: true,
    empty_state_message: null,
    capabilities: [
        {
            capability_key: "reception_visit_execution",
            display_name: "接待拜访准备与执行",
            description: "能按商务拜访流程做好准备、接待和跟进。",
            mastery_levels: [
                {
                    level_key: "basic",
                    display_name: "基本掌握",
                    min_score: 80,
                    description: "能处理常见接待拜访场景。",
                },
            ],
            default_threshold: 80,
            evidence_rules: [
                {
                    evidence_type: "ai_coach_card",
                    weight: 1,
                    required: true,
                    description: "AI 教练训练卡达标。",
                },
            ],
            owner_scope: "business_etiquette_training_pack",
            status: "published",
        },
    ],
    chapters: [
        {
            chapter_id: "chapter-5",
            title: "接待与拜访礼仪",
            order_index: 5,
            completed: true,
        },
    ],
    progress: {
        completed_chapter_ids: ["chapter-5"],
        total_chapters: 1,
        completed_chapters: 1,
        is_completed: true,
    },
} satisfies BusinessEtiquetteLearningUnit;

const learningUnitsResponse = {
    module_key: "business_skills",
    learning_content_id: "content-1",
    path_revision_id: "revision-1",
    path_revision_no: 1,
    units: [learningUnit],
};

const defaultCoachProgress = {
    session_id: "s1",
    module_key: "business_skills",
    learning_unit_key: "reception_visit_execution",
    learning_unit_title: "接待与拜访执行",
    status: "not_started",
    passed: false,
    ready_for_field: false,
    manual_review_required: false,
    block_next: true,
    answered_card_count: 0,
    scored_card_count: 0,
    remediation_attempt_count: 0,
    max_remediation_attempts: 3,
    pass_mastery_level_key: "basic_mastery",
    ready_mastery_level_key: "field_ready",
    weak_capability_keys: ["reception_visit_execution"],
    recommended_chapter_orders: [5],
    recommended_training_card_types: ["scenario_judgment"],
    next_step_code: "start_training",
    next_step: "先完成一张 AI 教练训练卡，系统会按能力点记录掌握证据。",
    capability_scores: [
        {
            capability_key: "reception_visit_execution",
            display_name: "接待拜访准备与执行",
            score: null,
            max_score: 0,
            normalized_score: null,
            threshold: 70,
            mastered: null,
            mastery_level_key: null,
            mastery_level_name: null,
        },
    ],
} satisfies BusinessEtiquetteAiCoachProgress;

const manualReviewCoachProgress = {
    ...defaultCoachProgress,
    status: "manual_review",
    manual_review_required: true,
    answered_card_count: 3,
    scored_card_count: 3,
    remediation_attempt_count: 3,
    next_step_code: "manual_review",
    next_step: "已达到补救次数上限，建议提交给带教人复盘后再继续。",
    recommended_training_card_types: ["scenario_judgment", "role_response"],
    capability_scores: [
        {
            capability_key: "reception_visit_execution",
            display_name: "接待拜访准备与执行",
            score: 150,
            max_score: 300,
            normalized_score: 50,
            threshold: 70,
            mastered: false,
            mastery_level_key: "not_mastered",
            mastery_level_name: "未掌握",
        },
    ],
} satisfies BusinessEtiquetteAiCoachProgress;

const masteredCoachProgress = {
    ...defaultCoachProgress,
    status: "mastered",
    passed: true,
    block_next: false,
    answered_card_count: 1,
    scored_card_count: 1,
    remediation_attempt_count: 0,
    weak_capability_keys: [],
    next_step_code: "mastered",
    next_step: "继续做一题新场景。",
    capability_scores: [
        {
            capability_key: "reception_visit_execution",
            display_name: "接待拜访准备与执行",
            score: 90,
            max_score: 100,
            normalized_score: 90,
            threshold: 70,
            mastered: true,
            mastery_level_key: "basic_mastery",
            mastery_level_name: "基本掌握",
        },
    ],
} satisfies BusinessEtiquetteAiCoachProgress;

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

function quizEvent(
    eventId: string,
    index: number,
    overrides: Partial<Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }>> = {},
): Extract<AiCoachUiEventPublicV1, { type: "quiz_card" }> {
    const shortAnswer = index > 0;
    const trainingCardTypes = [
        "scenario_judgment",
        "expression_rewrite",
        "role_response",
    ] as const;
    return {
        event_id: eventId,
        message_id: "m3",
        type: "quiz_card",
        status: "pending",
        payload: {
            interaction: {
                schema_version: "ai_coach_interaction_public_v1",
                interaction_id: eventId,
                session_id: "s1",
                turn_number: index + 1,
                training_card_type: trainingCardTypes[index] ?? "scenario_judgment",
                interaction_type: shortAnswer ? "short_answer" : "single_choice",
                stem: `第 ${index + 1} 题：客户到访前应该先确认什么？`,
                options: shortAnswer
                    ? null
                    : [
                        { option_id: "A", text: "到访时间、人数和接待安排" },
                        { option_id: "B", text: "直接发送宣传册" },
                    ],
                answer_constraints: shortAnswer
                    ? { min_length: 2, max_length: 200 }
                    : { min_selected: 1, max_selected: 1 },
                capability_keys: ["reception_visit_execution"],
                source_chapter_orders: [5],
            },
            explanation: "拜访前先确认接待条件。",
        },
        answer_payload: null,
        score_result: null,
        order_index: index + 1,
        created_at: "2026-06-12T00:01:02Z",
        ...overrides,
    };
}

const cardSession = {
    ...welcomeSession,
    coach_state: activeCoachState,
    messages: [
        ...welcomeSession.messages,
        {
            message_id: "m2",
            role: "user" as const,
            content: "我想练一下客户接待。",
            order_index: 2,
            created_at: "2026-06-12T00:01:00Z",
        },
        {
            message_id: "m3",
            role: "assistant" as const,
            content: "可以，我们先聊接待准备；需要验证时我会给你一张练习卡。",
            order_index: 3,
            created_at: "2026-06-12T00:01:02Z",
        },
    ],
    ui_events: [quizEvent("e1", 0)],
};

const markdownReplySession = {
    ...welcomeSession,
    messages: [
        ...welcomeSession.messages,
        {
            message_id: "m2",
            role: "user" as const,
            content: "讲一下接待准备。",
            order_index: 2,
            created_at: "2026-06-12T00:01:00Z",
        },
        {
            message_id: "m3",
            role: "assistant" as const,
            content: "**建议**\n- 先确认客户到访目标\n- 再安排接待动作",
            order_index: 3,
            created_at: "2026-06-12T00:01:02Z",
        },
    ],
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
                structured_feedback: {
                    did_well: ["先确认关键接待条件"],
                    main_issue: "无明显问题",
                    why_inappropriate: "当前回答符合拜访前准备要求。",
                    suggested_response: "我会先确认到访时间、人数、身份和接待安排。",
                    next_step: "继续练习现场引导和送别动作。",
                },
                missed_points: [],
                next_turn_available: true,
                finished: false,
            },
        },
        quizEvent("e2", 1),
    ],
};

const answerScoredOnlySession = {
    ...cardSession,
    coach_state: {
        ...activeCoachState,
        session_phase: "reviewing" as const,
        active_event_id: null,
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
                structured_feedback: null,
                missed_points: [],
                next_turn_available: true,
                finished: false,
            },
        },
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

async function startCurrentTraining(user: ReturnType<typeof userEvent.setup>) {
    expect(await screen.findByText("准备开始 AI 教练训练")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "继续当前局" }));
}

describe("AiCoachPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockGetBusinessEtiquetteLearningUnits.mockResolvedValue(learningUnitsResponse);
        mockGetBusinessEtiquetteAiCoachProgress.mockResolvedValue(defaultCoachProgress);
    });

    afterEach(() => {
        cleanup();
    });

    it("resumes a training session and renders the active card first", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));

        render(<AiCoachPage />);

        expect(await screen.findByText("准备开始 AI 教练训练")).toBeTruthy();
        expect(await screen.findByText("接待与拜访执行")).toBeTruthy();
        expect(screen.queryByText("第 1 题：客户到访前应该先确认什么？")).toBeNull();
        expect(mockStartChatStream).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "继续当前局" }));

        await waitFor(() => {
            expect(mockStartChatStream).toHaveBeenCalledWith(
                {
                    module_key: "business_skills",
                    resume_strategy: "latest_in_progress",
                },
                expect.any(AbortSignal),
            );
        });
        expect(await screen.findByText("商务技巧 AI 教练")).toBeTruthy();
        expect(screen.queryByText("训练卡工作台")).toBeNull();
        expect(screen.getByText("接待与拜访执行")).toBeTruthy();
        expect(screen.getAllByText(/接待拜访准备与执行/).length).toBeGreaterThan(0);
        await waitFor(() => {
            expect(screen.getAllByText("AI 教练达标").length).toBeGreaterThan(0);
        });
        expect(screen.getAllByText("未开始").length).toBeGreaterThan(0);
        expect(screen.getByText(/作答中/)).toBeTruthy();
        expect(screen.getByText("我想练一下客户接待。")).toBeTruthy();
        expect(screen.getByText("可以，我们先聊接待准备；需要验证时我会给你一张练习卡。")).toBeTruthy();
        expect(screen.getAllByText("场景判断卡").length).toBeGreaterThan(0);
        expect(screen.getByText("第 1 题：客户到访前应该先确认什么？")).toBeTruthy();
        expect(screen.queryByText("第 2 题：客户到访前应该先确认什么？")).toBeNull();
        expect(screen.queryByText("拜访前先确认接待条件。")).toBeNull();
        expect(screen.getByPlaceholderText("可以问教练，也可以先提交当前练习卡")).toBeTruthy();
    });

    it("renders disabled streamed card deltas before the generated card snapshot arrives", async () => {
        const user = userEvent.setup();
        const gate = createDeferred();
        mockStartChatStream.mockImplementation(() =>
            streamSessionWithGeneratedCardPending(welcomeSession, cardSession, gate),
        );

        render(<AiCoachPage />);
        await startCurrentTraining(user);

        expect(await screen.findByText("训练卡生成中")).toBeTruthy();
        expect(
            screen.getByText(
                "题干、选项和评分规则还在生成；你可以先看到卡片结构，生成完成前不能作答。",
            ),
        ).toBeTruthy();
        expect(screen.getByText("到访时间、人数和接待安排")).toBeTruthy();
        expect(screen.getByText("直接发送宣传册")).toBeTruthy();
        expect(
            screen.getByRole("button", { name: "生成完成后可提交" }).hasAttribute("disabled"),
        ).toBe(true);
        expect(screen.getByText("第 1 题：客户到访前应该先确认什么？")).toBeTruthy();
        expect(screen.queryByText("拜访前先确认接待条件。")).toBeNull();

        gate.resolve();

        expect(await screen.findByText("第 1 题：客户到访前应该先确认什么？")).toBeTruthy();
        await waitFor(() => {
            expect(screen.queryByText("训练卡生成中")).toBeNull();
        });
    });

    it("shows learner-facing copy when the resumed coach session misses a unit snapshot", async () => {
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockGetBusinessEtiquetteAiCoachProgress.mockRejectedValue({
            status: 409,
            errorCode: "BUSINESS_ETIQUETTE_AI_COACH_PROGRESS_SNAPSHOT_MISSING",
            rawMessage: "商务礼仪 AI 教练会话缺少训练小单元快照。",
            message: "商务礼仪 AI 教练会话缺少训练小单元快照。 (trace_id: trace-progress-1)",
        });

        render(<AiCoachPage />);
        await startCurrentTraining(userEvent.setup());

        await waitFor(() => {
            expect(
                screen.getAllByText(
                    "当前训练局缺少小单元信息，请点击「新开一局」重新开始。",
                ).length,
            ).toBeGreaterThan(0);
        });
        expect(screen.queryByText(/trace-progress-1/)).toBeNull();
        expect(screen.queryByText(/小单元快照/)).toBeNull();
    });

    it("keeps the draft and shows a visible error when submit stream fails", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockSubmitEventStream.mockImplementation(() =>
            streamBusinessEtiquetteUnitMissingError(),
        );

        render(<AiCoachPage />);
        await startCurrentTraining(user);

        const firstCard = await screen.findByText("第 1 题：客户到访前应该先确认什么？");
        const cardRoot = firstCard.closest("section");
        if (cardRoot === null) {
            throw new Error("expected first quiz card section");
        }
        const card = within(cardRoot);
        await user.click(card.getByText("到访时间、人数和接待安排"));
        await user.click(card.getByRole("button", { name: "提交" }));

        expect(await screen.findByText("训练请求未完成")).toBeTruthy();
        expect(
            screen.getAllByText("当前训练局缺少小单元信息，请点击「新开一局」重新开始。")
                .length,
        ).toBeGreaterThan(0);
        const submitButton = card.getByRole("button", { name: "提交" });
        expect(submitButton.hasAttribute("disabled")).toBe(false);
        expect(mockSubmitEventStream).toHaveBeenCalledWith(
            "s1",
            "e1",
            { answer_payload: { variant: "choice", option_ids: ["A"] } },
            expect.any(AbortSignal),
        );
    });

    it("renders expression rewrite and role response training cards in the chat timeline", async () => {
        const rewriteSession = {
            ...cardSession,
            coach_state: {
                ...activeCoachState,
                active_event_id: "e2",
            },
            ui_events: [quizEvent("e2", 1)],
        };
        const roleResponseSession = {
            ...cardSession,
            coach_state: {
                ...activeCoachState,
                active_event_id: "e3",
            },
            ui_events: [quizEvent("e3", 2)],
        };
        mockStartChatStream
            .mockImplementationOnce(() => streamSession(rewriteSession))
            .mockImplementationOnce(() => streamSession(roleResponseSession));

        const { unmount } = render(<AiCoachPage />);
        await startCurrentTraining(userEvent.setup());

        expect(await screen.findByText("表达改写卡")).toBeTruthy();
        expect(screen.getByText("第 2 题：客户到访前应该先确认什么？")).toBeTruthy();
        unmount();

        render(<AiCoachPage />);
        await startCurrentTraining(userEvent.setup());

        expect(await screen.findByText("角色回应卡")).toBeTruthy();
        expect(screen.getByText("第 3 题：客户到访前应该先确认什么？")).toBeTruthy();
    });

    it("keeps free text as an auxiliary coach question", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(welcomeSession));
        mockSendChatStream.mockImplementation(() => streamSession(cardSession));

        render(<AiCoachPage />);
        await startCurrentTraining(user);

        const input = await screen.findByPlaceholderText("直接和教练聊，或使用上方操作");
        await user.type(input, "这个场景有什么注意点？");
        await user.click(screen.getByRole("button", { name: "发送" }));

        await waitFor(() => {
            expect(mockSendChatStream).toHaveBeenCalledWith(
                "s1",
                { content: "这个场景有什么注意点？" },
                expect.any(AbortSignal),
            );
        });
        expect(await screen.findByText("可以，我们先聊接待准备；需要验证时我会给你一张练习卡。")).toBeTruthy();
        expect(screen.getAllByText("单选")).toHaveLength(1);
    });

    it("streams reasoning text before the final snapshot", async () => {
        const user = userEvent.setup();
        const gate = createDeferred();
        mockStartChatStream.mockImplementation(() => streamSession(welcomeSession));
        mockSendChatStream.mockImplementation(() =>
            streamSessionWithAssistantMarkdownDelta("s1", markdownReplySession, gate),
        );

        render(<AiCoachPage />);
        await startCurrentTraining(user);

        const input = await screen.findByPlaceholderText("直接和教练聊，或使用上方操作");
        await user.type(input, "讲一下接待准备。");
        await user.click(screen.getByRole("button", { name: "发送" }));

        expect((await screen.findAllByText("正在组织教练回复。")).length).toBeGreaterThan(0);
        expect(screen.queryByText("思考中")).toBeNull();
        expect(screen.queryByText("正在理解你的回答")).toBeNull();
        expect(screen.getByText("思考过程")).toBeTruthy();
        expect(screen.getByText("先判断接待目标。")).toBeTruthy();
        expect(screen.queryByText("生成中")).toBeNull();
        expect(screen.queryByText("建议")).toBeNull();
        expect(screen.queryByText("先确认客户到访目标")).toBeNull();
        expect(screen.queryByText(/\*\*建议\*\*/)).toBeNull();

        gate.resolve();

        await waitFor(() => {
            expect(screen.getByText("建议")).toBeTruthy();
        });
        expect(screen.getByText("再安排接待动作")).toBeTruthy();
    });

    it("keeps the conversation pinned while reasoning text grows", async () => {
        const user = userEvent.setup();
        const gate = createDeferred();
        const snapshotGate = createDeferred();
        const originalScrollTo = HTMLElement.prototype.scrollTo;
        const originalClientHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
        const originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollHeight");
        const originalOffsetTop = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetTop");
        const scrollTo = vi.fn();
        Object.defineProperty(HTMLElement.prototype, "scrollTo", {
            configurable: true,
            value: scrollTo,
        });
        Object.defineProperty(HTMLElement.prototype, "clientHeight", {
            configurable: true,
            get: () => 600,
        });
        Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
            configurable: true,
            get: () => 2200,
        });
        Object.defineProperty(HTMLElement.prototype, "offsetTop", {
            configurable: true,
            get() {
                return this.getAttribute("data-latest-turn-anchor") === "true" ? 900 : 0;
            },
        });
        mockStartChatStream.mockImplementation(() => streamSession(welcomeSession));
        mockSendChatStream.mockImplementation(() =>
            streamSessionWithTwoReasoningDeltas("s1", markdownReplySession, gate, snapshotGate),
        );

        try {
            render(<AiCoachPage />);
            await startCurrentTraining(user);

            const input = await screen.findByPlaceholderText("直接和教练聊，或使用上方操作");
            await user.type(input, "讲一下接待准备。");
            await user.click(screen.getByRole("button", { name: "发送" }));

            expect(await screen.findByText(/先判断接待目标/)).toBeTruthy();
            scrollTo.mockClear();

            gate.resolve();

            expect(await screen.findByText(/先判断接待目标。再判断称呼边界。/)).toBeTruthy();
            await waitFor(() => {
                expect(scrollTo).toHaveBeenCalled();
            });
            const lastScroll = scrollTo.mock.calls.at(-1)?.[0] as ScrollToOptions | undefined;
            expect(lastScroll?.top).toBeGreaterThan(700);
            expect(lastScroll?.top).toBeLessThan(1100);
            expect(lastScroll?.top).not.toBe(2200);
            snapshotGate.resolve();
        } finally {
            Object.defineProperty(HTMLElement.prototype, "scrollTo", {
                configurable: true,
                value: originalScrollTo,
            });
            if (originalClientHeight) {
                Object.defineProperty(HTMLElement.prototype, "clientHeight", originalClientHeight);
            } else {
                Reflect.deleteProperty(HTMLElement.prototype, "clientHeight");
            }
            if (originalScrollHeight) {
                Object.defineProperty(HTMLElement.prototype, "scrollHeight", originalScrollHeight);
            } else {
                Reflect.deleteProperty(HTMLElement.prototype, "scrollHeight");
            }
            if (originalOffsetTop) {
                Object.defineProperty(HTMLElement.prototype, "offsetTop", originalOffsetTop);
            } else {
                Reflect.deleteProperty(HTMLElement.prototype, "offsetTop");
            }
        }
    });

    it("does not render streamed assistant text as thinking after submitting an option", async () => {
        const user = userEvent.setup();
        const gate = createDeferred();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockSubmitEventStream.mockImplementation(() =>
            streamSubmitAnswerWithNextStepDelta(
                "s1",
                answerScoredOnlySession,
                scoredSession,
                gate,
            ),
        );

        render(<AiCoachPage />);
        await startCurrentTraining(user);

        const firstCard = await screen.findByText("第 1 题：客户到访前应该先确认什么？");
        const cardRoot = firstCard.closest("section");
        if (cardRoot === null) {
            throw new Error("expected first quiz card section");
        }
        const card = within(cardRoot);
        await user.click(card.getByText("到访时间、人数和接待安排"));
        await user.click(card.getByRole("button", { name: "提交" }));

        expect((await screen.findAllByText("正在生成下一步教练回复。")).length)
            .toBeGreaterThan(0);
        expect(screen.queryByText("生成中")).toBeNull();
        expect(screen.queryByText("下一步")).toBeNull();
        expect(screen.queryByText(/继续练现场引导/)).toBeNull();

        gate.resolve();

        expect(await screen.findByText("已提交")).toBeTruthy();
        expect(screen.getByText("第 2 题：客户到访前应该先确认什么？")).toBeTruthy();
    });

    it("submits a quiz card answer and shows scored feedback", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockSubmitEventStream.mockImplementation(() => streamSession(scoredSession));
        mockGetBusinessEtiquetteAiCoachProgress
            .mockResolvedValueOnce(defaultCoachProgress)
            .mockResolvedValue(manualReviewCoachProgress);

        render(<AiCoachPage />);
        await startCurrentTraining(user);

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
        expect(screen.getAllByText("处理得当。").length).toBeGreaterThan(0);
        expect(screen.getByText("答对")).toBeTruthy();
        expect(screen.getByText("已达到本轮掌握标准：80%")).toBeTruthy();
        expect(screen.getAllByText("做得好").length).toBeGreaterThan(0);
        expect(screen.getAllByText("先确认关键接待条件").length).toBeGreaterThan(0);
        expect(screen.getAllByText("可以这样说").length).toBeGreaterThan(0);
        expect(
            screen.getAllByText("我会先确认到访时间、人数、身份和接待安排。").length,
        ).toBeGreaterThan(0);
        expect(screen.queryByText("100 / 100")).toBeNull();
        expect(screen.getByText("拜访前先确认接待条件。")).toBeTruthy();
        expect(screen.getAllByText("第 5 章").length).toBeGreaterThan(0);
        expect(screen.getAllByText("表达改写卡").length).toBeGreaterThan(0);
        expect(screen.queryByText("教练判断")).toBeNull();
    });

    it("shows a clear unavailable state when chat config is disabled", async () => {
        mockStartChatStream.mockImplementation(() => {
            throw new Error("该模块未启用对话式 AI 教练。");
        });

        render(<AiCoachPage />);
        await startCurrentTraining(userEvent.setup());

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
        await startCurrentTraining(user);

        expect((await screen.findAllByText(/等你选择/)).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/客户异议/).length).toBeGreaterThan(0);
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
        mockGetBusinessEtiquetteAiCoachProgress.mockResolvedValue(masteredCoachProgress);

        render(<AiCoachPage />);
        await startCurrentTraining(userEvent.setup());

        expect(await screen.findByText(/本轮总结/)).toBeTruthy();
        expect(screen.getByText("本轮训练总结")).toBeTruthy();
        expect(screen.getByText("结束面板")).toBeTruthy();
        expect(screen.getByText("本轮已达标")).toBeTruthy();
        expect(screen.getAllByText("继续做一题新场景。").length).toBeGreaterThan(0);
        expect(screen.queryByText("第 1 题：客户到访前应该先确认什么？")).toBeNull();
        expect(screen.getByPlaceholderText("直接和教练聊，或使用上方操作")).toBeTruthy();
    });

    it("sends fixed coach commands with the active event id", async () => {
        const user = userEvent.setup();
        mockStartChatStream.mockImplementation(() => streamSession(cardSession));
        mockSendChatStream.mockImplementation(() => streamSession(cardSession));

        render(<AiCoachPage />);
        await startCurrentTraining(user);

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
        mockStartChatStream.mockImplementation(() => streamSession({
            ...cardSession,
            session_id: "s2",
        }));

        render(<AiCoachPage />);

        expect(await screen.findByText("准备开始 AI 教练训练")).toBeTruthy();
        expect(mockStartChatStream).not.toHaveBeenCalled();
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
