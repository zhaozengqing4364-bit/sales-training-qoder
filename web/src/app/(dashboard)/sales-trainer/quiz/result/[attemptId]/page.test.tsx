import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuizResultPage from "./page";

const { getJourneyMock, getQuizAttemptMock, listPathsMock } = vi.hoisted(() => ({
    getJourneyMock: vi.fn(),
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
                getJourney: getJourneyMock,
                getQuizAttempt: getQuizAttemptMock,
                listPaths: listPathsMock,
            },
        },
    };
});

describe("SalesTrainerQuizResultPage", () => {
    beforeEach(() => {
        getJourneyMock.mockResolvedValue({
            journey_id: "journey-user-1",
            learner_id: "user-1",
            learner_name: "新人",
            department: "销售一部",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "revision-1",
            path_revision_no: 1,
            source: "active_revision",
            legacy_snapshot_only: false,
            role_capabilities: [],
            learner_level: {
                level_key: "unassigned",
                label: "未分配",
                source: "training_projection",
                rank: 0,
            },
            role_level: {
                level_key: "learner",
                label: "学员",
                source: "training_projection",
                rank: 0,
            },
            training_stage: "in_progress",
            modules: [{
                module_key: "audio-unit",
                title: "下一关：第二关：录音表达",
                kind: "audio_submission",
                module_type: "audio_scoring",
                display_name: "下一关：第二关：录音表达",
                order_index: 2,
                enabled: true,
                status: "not_started",
                stage: "not_started",
                passed: null,
                score: null,
                max_score: null,
                required: true,
                completion_satisfied: false,
                locked: false,
                block_reason: null,
                completion_rule: "passed",
                source: {
                    path_revision_id: "revision-1",
                    path_revision_no: 1,
                },
                learner_level_required: null,
                unmet_reasons: [],
                diagnostics: [],
                next_action: {
                    action_key: "start_audio",
                    label: "上传录音",
                    target_path: "/sales-trainer/audio/audio-unit",
                    disabled: false,
                    disabled_reason: null,
                },
                latest_outcome: null,
                outcome_history: [],
            }],
            overall_progress: {
                total_modules: 1,
                completed_modules: 0,
                passed_modules: 0,
                failed_modules: 0,
                needs_remediation_modules: 0,
            },
            diagnostics: [],
        });
        listPathsMock.mockReset();
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
        expect(listPathsMock).not.toHaveBeenCalled();
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

    it("shows AI coach entry for failed business skills attempts when available", async () => {
        getQuizAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            unit_id: "unit-1",
            user_id: "user-1",
            total_score: 60,
            max_score: 100,
            passed: false,
            status: "scored",
            submitted_at: "2026-05-28T00:00:00Z",
            answers: [
                {
                    answer_id: "answer-1",
                    question_id: "question-1",
                    question_type: "single_choice",
                    answer_payload: "B",
                    question_title: "商务礼仪",
                    question_stem: "见客户前应先确认什么？",
                    options: [],
                    correct_answer: "A",
                    reference_answer: "A. 客户背景",
                    explanation: null,
                    scoring_feedback: null,
                    scoring_reason: null,
                    normalized_score: null,
                    is_correct: false,
                    score: 0,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
        });
        getJourneyMock.mockResolvedValueOnce({
            journey_id: "journey-user-1",
            learner_id: "user-1",
            learner_name: "新人",
            department: "销售一部",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "revision-1",
            path_revision_no: 1,
            source: "active_revision",
            legacy_snapshot_only: false,
            role_capabilities: [],
            learner_level: {
                level_key: "unassigned",
                label: "未分配",
                source: "training_projection",
                rank: 0,
            },
            role_level: {
                level_key: "learner",
                label: "学员",
                source: "training_projection",
                rank: 0,
            },
            training_stage: "needs_remediation",
            modules: [{
                module_key: "business_skills",
                title: "商务技巧",
                kind: "quiz_attempt",
                module_type: "article_exam",
                display_name: "商务技巧 AI 教练",
                order_index: 2,
                enabled: true,
                status: "needs_remediation",
                stage: "needs_remediation",
                passed: false,
                score: 60,
                max_score: 100,
                required: true,
                completion_satisfied: false,
                locked: false,
                block_reason: null,
                completion_rule: "passed",
                source: {
                    path_revision_id: "revision-1",
                    path_revision_no: 1,
                },
                learner_level_required: null,
                unmet_reasons: [],
                diagnostics: [],
                next_action: {
                    action_key: "start_ai_coach",
                    label: "进入 AI 教练",
                    target_path: "/sales-trainer/business-skills/coach",
                    disabled: false,
                    disabled_reason: null,
                },
                latest_outcome: null,
                outcome_history: [],
            }],
            overall_progress: {
                total_modules: 1,
                completed_modules: 0,
                passed_modules: 0,
                failed_modules: 1,
                needs_remediation_modules: 1,
            },
            diagnostics: [],
        });

        render(<SalesTrainerQuizResultPage />);

        expect(await screen.findByText("未通过")).toBeTruthy();
        expect(screen.getByRole("link", { name: "重新考试" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills/exam?unitId=unit-1",
        );
        expect(screen.getAllByRole("link", { name: /进入 AI 教练/ })[0].getAttribute("href")).toBe(
            "/sales-trainer/business-skills/coach",
        );
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("shows a diagnostic instead of silently hiding AI coach entry when path config lookup fails", async () => {
        getQuizAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            unit_id: "unit-1",
            user_id: "user-1",
            total_score: 60,
            max_score: 100,
            passed: false,
            status: "scored",
            submitted_at: "2026-05-28T00:00:00Z",
            answers: [
                {
                    answer_id: "answer-1",
                    question_id: "question-1",
                    question_type: "single_choice",
                    answer_payload: "B",
                    question_title: "商务礼仪",
                    question_stem: "见客户前应先确认什么？",
                    options: [],
                    correct_answer: "A",
                    reference_answer: "A. 客户背景",
                    explanation: null,
                    scoring_feedback: null,
                    scoring_reason: null,
                    normalized_score: null,
                    is_correct: false,
                    score: 0,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
        });
        getJourneyMock.mockRejectedValueOnce(new Error("journey config unavailable"));

        render(<SalesTrainerQuizResultPage />);

        expect(await screen.findByText("做题结果")).toBeTruthy();
        expect(screen.getByText("AI 教练入口配置诊断")).toBeTruthy();
        expect(screen.getByText(/journey config unavailable/)).toBeTruthy();
        expect(screen.queryByRole("link", { name: /进入 AI 教练/ })).toBeNull();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("keeps attempt load failures recoverable instead of rendering a missing result", async () => {
        getQuizAttemptMock
            .mockRejectedValueOnce(new Error("attempt service unavailable"))
            .mockResolvedValueOnce({
                attempt_id: "attempt-1",
                unit_id: "unit-1",
                user_id: "user-1",
                total_score: 10,
                max_score: 10,
                passed: true,
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

        expect(await screen.findByText("做题结果加载失败")).toBeTruthy();
        expect(screen.getByText(/attempt service unavailable/)).toBeTruthy();
        expect(screen.queryByText("做题结果不存在。")).toBeNull();

        const callsBeforeRetry = getQuizAttemptMock.mock.calls.length;
        fireEvent.click(screen.getByRole("button", { name: "重新加载结果" }));

        expect(await screen.findByText("做题结果")).toBeTruthy();
        expect(screen.getByText("已通过")).toBeTruthy();
        await waitFor(() => {
            expect(getQuizAttemptMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry);
        });
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
