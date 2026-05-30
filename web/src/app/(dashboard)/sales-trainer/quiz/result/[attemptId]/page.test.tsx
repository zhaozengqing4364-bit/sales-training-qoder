import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuizResultPage from "./page";

const { getQuizAttemptMock, listPathsMock } = vi.hoisted(() => ({
    getQuizAttemptMock: vi.fn(),
    listPathsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ attemptId: "attempt-1" }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                getQuizAttempt: getQuizAttemptMock,
                listPaths: listPathsMock,
            },
        },
    };
});

describe("SalesTrainerQuizResultPage", () => {
    beforeEach(() => {
        listPathsMock.mockResolvedValue({
            items: [
                {
                    path_key: "new_seller",
                    title: "新人销售闯关",
                    goal_title: "掌握首次客户沟通",
                    total_levels: 2,
                    completed_levels: 1,
                    current_level_id: "audio-unit",
                    next_level_id: "audio-unit",
                    levels: [
                        {
                            unit_id: "unit-1",
                            name: "做题单元",
                            description: "题目训练",
                            unit_type: "quiz",
                            order_index: 1,
                            level_title: "第一关：产品定位",
                            level_description: "先确认产品定位。",
                            locked: false,
                            lock_reason: null,
                            status: "completed",
                            completion_rule: "passed",
                            primary_action_label: "开始做题",
                            retry_action_label: "重练本关",
                            review_action_label: "查看结果",
                            target_path: "/sales-trainer/quiz/unit-1",
                            latest_result: null,
                        },
                    ],
                    goal_context: {
                        goal_title: "掌握首次客户沟通",
                        score_basis: "sales_trainer_path_projection_v1",
                        evidence_items: [],
                        weak_points: [],
                        next_recommendation: {
                            title: "下一关：第二关：录音表达",
                            reason: "继续补齐录音表达证据。",
                            action_label: "上传录音",
                            target_path: "/sales-trainer/audio/audio-unit",
                            unit_id: "audio-unit",
                            level_title: "第二关：录音表达",
                            recommendation_kind: "start_level",
                        },
                    },
                },
            ],
            total: 1,
        });
        getQuizAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            unit_id: "unit-1",
            user_id: "user-1",
            total_score: 10,
            max_score: 10,
            passed: null,
            status: "scored",
            submitted_at: "2026-05-28T00:00:00Z",
            answers: [
                {
                    answer_id: "answer-1",
                    question_id: "question-1",
                    question_type: "single_choice",
                    answer_payload: "A",
                    question_title: "产品定位",
                    question_stem: "石犀核心定位是什么？",
                    options: [
                        { value: "A", label: "数据流动治理" },
                        { value: "B", label: "招聘管理" },
                    ],
                    correct_answer: "A",
                    reference_answer: "A. 数据流动治理",
                    explanation: "石犀聚焦数据流动治理。",
                    scoring_feedback: null,
                    scoring_reason: null,
                    normalized_score: null,
                    is_correct: true,
                    score: 10,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
        });
    });

    it("does not render an unconfigured pass threshold as failed", async () => {
        render(<SalesTrainerQuizResultPage />);

        expect(await screen.findByText("做题结果")).toBeTruthy();
        expect(screen.getByText("仅计分")).toBeTruthy();
        expect(screen.queryByText("未通过")).toBeNull();
        expect(screen.getAllByText("10").length).toBeGreaterThanOrEqual(2);
        expect(screen.getByText("产品定位")).toBeTruthy();
        expect(screen.getByText("石犀核心定位是什么？")).toBeTruthy();
        expect(screen.getByText("石犀聚焦数据流动治理。")).toBeTruthy();
        expect(await screen.findByText("练完下一步")).toBeTruthy();
        expect(screen.getByText("下一关：第二关：录音表达")).toBeTruthy();
        expect(screen.getByRole("link", { name: /上传录音/ }).getAttribute("href")).toBe("/sales-trainer/audio/audio-unit");
    });

    it("renders pending score when any answer still needs judging", async () => {
        getQuizAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            unit_id: "unit-1",
            user_id: "user-1",
            total_score: null,
            max_score: null,
            passed: null,
            status: "submitted",
            submitted_at: "2026-05-28T00:00:00Z",
            answers: [
                {
                    answer_id: "answer-1",
                    question_id: "question-1",
                    question_type: "short_answer",
                    answer_payload: "说明客户场景、痛点和下一步行动。",
                    question_title: "客户价值理解",
                    question_stem: "请说明客户价值。",
                    options: [],
                    correct_answer: null,
                    reference_answer: "应说明客户场景、痛点和下一步行动。",
                    explanation: "简答题需要覆盖场景、价值和推进动作。",
                    scoring_feedback: null,
                    scoring_reason: null,
                    normalized_score: null,
                    is_correct: null,
                    score: null,
                    created_at: "2026-05-28T00:00:00Z",
                },
                {
                    answer_id: "answer-2",
                    question_id: "question-2",
                    question_type: "single_choice",
                    answer_payload: "A",
                    question_title: "产品定位",
                    question_stem: "石犀核心定位是什么？",
                    options: [],
                    correct_answer: "A",
                    reference_answer: "A. 数据流动治理",
                    explanation: null,
                    scoring_feedback: null,
                    scoring_reason: null,
                    normalized_score: null,
                    is_correct: true,
                    score: 10,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
        });

        render(<SalesTrainerQuizResultPage />);

        expect(await screen.findByText("做题结果")).toBeTruthy();
        expect(screen.getByText("待判分")).toBeTruthy();
        expect(screen.getByText("待人工判定")).toBeTruthy();
        expect(screen.queryByText("仅计分")).toBeNull();
    });

    it("renders AI short-answer feedback when scoring succeeds", async () => {
        getQuizAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            unit_id: "unit-1",
            user_id: "user-1",
            total_score: 8,
            max_score: 10,
            passed: true,
            status: "scored",
            submitted_at: "2026-05-28T00:00:00Z",
            answers: [
                {
                    answer_id: "answer-1",
                    question_id: "question-1",
                    question_type: "short_answer",
                    answer_payload: "围绕数据流动治理帮助客户形成闭环。",
                    question_title: "客户价值理解",
                    question_stem: "请说明石犀如何帮助客户。",
                    options: [],
                    correct_answer: null,
                    reference_answer: "石犀帮助客户建立可审计的数据流动治理体系。",
                    explanation: "优秀答案应说明客户场景和治理价值。",
                    scoring_feedback: "回答覆盖核心价值，但可以补充客户场景。",
                    scoring_reason: "命中数据流动治理和客户价值。",
                    normalized_score: 80,
                    is_correct: true,
                    score: 8,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
        });

        render(<SalesTrainerQuizResultPage />);

        expect(await screen.findByText("客户价值理解")).toBeTruthy();
        expect(screen.getByText("回答覆盖核心价值，但可以补充客户场景。")).toBeTruthy();
        expect(screen.getByText(/AI 80/)).toBeTruthy();
        expect(screen.getByText(/评分依据：命中数据流动治理和客户价值。/)).toBeTruthy();
    });
});
