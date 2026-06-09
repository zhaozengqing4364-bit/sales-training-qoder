import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerQuizAttemptDetailPage from "./page";

const { getQuizAttemptMock, previewQuizAttemptRegradeMock, runQuizAttemptRegradeMock } = vi.hoisted(() => ({
    getQuizAttemptMock: vi.fn(),
    previewQuizAttemptRegradeMock: vi.fn(),
    runQuizAttemptRegradeMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ attemptId: "attempt-1" }),
    usePathname: () => "/admin/sales-trainer/quiz-attempts/attempt-1",
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getQuizAttempt: getQuizAttemptMock,
                    previewQuizAttemptRegrade: previewQuizAttemptRegradeMock,
                    runQuizAttemptRegrade: runQuizAttemptRegradeMock,
                },
            },
        },
    };
});

describe("SalesTrainerQuizAttemptDetailPage", () => {
    beforeEach(() => {
        getQuizAttemptMock.mockReset();
        previewQuizAttemptRegradeMock.mockReset();
        runQuizAttemptRegradeMock.mockReset();
        getQuizAttemptMock.mockResolvedValue({
            attempt_id: "attempt-1",
            unit_id: "unit-1",
            user_id: "user-1",
            user_name: "张三",
            user_email: "zhangsan@example.com",
            user_department: "销售一部",
            total_score: 18,
            max_score: 20,
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
                {
                    answer_id: "answer-2",
                    question_id: "question-2",
                    question_type: "short_answer",
                    answer_payload: "围绕客户数据流动治理做价值解释。",
                    question_title: "客户价值理解",
                    question_stem: "请说明如何向客户解释价值。",
                    options: [],
                    correct_answer: null,
                    reference_answer: "应说明客户场景、痛点和下一步行动。",
                    explanation: "简答题需要覆盖场景、价值和推进动作。",
                    scoring_feedback: "回答覆盖核心价值，但可以补充客户场景。",
                    scoring_reason: "命中数据流动治理和客户价值。",
                    normalized_score: 80,
                    is_correct: true,
                    score: 8,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
        });
        previewQuizAttemptRegradeMock.mockResolvedValue({
            target_type: "quiz_attempt",
            target_id: "attempt-1",
            target_revision_id: "revision-2",
            impact_scope: {
                record_count: 1,
                affected_attempt_ids: ["attempt-1"],
                future_records_changed: false,
                history_overwrite: false,
                requires_reason: true,
            },
            before_snapshot: {
                total_score: 18,
                max_score: 20,
                passed: true,
            },
            after_snapshot: {
                total_score: 12,
                max_score: 20,
                passed: false,
            },
        });
        runQuizAttemptRegradeMock.mockResolvedValue({
            target_type: "quiz_attempt",
            target_id: "attempt-1",
            target_revision_id: "revision-2",
            impact_scope: {
                record_count: 1,
                affected_attempt_ids: ["attempt-1"],
                future_records_changed: false,
                history_overwrite: false,
                requires_reason: true,
            },
            before_snapshot: {
                total_score: 18,
                max_score: 20,
                passed: true,
            },
            after_snapshot: {
                total_score: 12,
                max_score: 20,
                passed: false,
            },
            regrade_run_id: "regrade-run-1",
            status: "completed",
            reason: "正确答案修订后追加历史重评记录",
            trace_id: "trace-regrade-1",
            created_at: "2026-06-04T00:00:00Z",
        });
    });

    it("renders answer snapshots and AI short-answer scoring feedback for admins", async () => {
        render(<SalesTrainerQuizAttemptDetailPage />);

        expect(await screen.findByText("做题结果详情")).toBeTruthy();
        expect(getQuizAttemptMock).toHaveBeenCalledWith("attempt-1");
        expect(screen.getByText("张三 · 销售一部")).toBeTruthy();
        expect(screen.getByText("已评分")).toBeTruthy();
        expect(screen.getByText("训练任务")).toBeTruthy();
        expect(screen.getByText("编号：unit-1")).toBeTruthy();
        expect(screen.queryByText("scored")).toBeNull();
        expect(screen.getByText("产品定位")).toBeTruthy();
        expect(screen.getByText("石犀核心定位是什么？")).toBeTruthy();
        expect(screen.getByText(/A\./)).toBeTruthy();
        expect(screen.getByText("数据流动治理")).toBeTruthy();
        expect(screen.getAllByText("A").length).toBeGreaterThanOrEqual(2);
        expect(screen.getByText("石犀聚焦数据流动治理。")).toBeTruthy();

        expect(screen.getByText("客户价值理解")).toBeTruthy();
        expect(screen.getByText("围绕客户数据流动治理做价值解释。")).toBeTruthy();
        expect(screen.getByText("应说明客户场景、痛点和下一步行动。")).toBeTruthy();
        expect(screen.getByText("回答覆盖核心价值，但可以补充客户场景。")).toBeTruthy();
        expect(screen.getByText(/AI 80/)).toBeTruthy();
        expect(screen.getByText(/评分依据：命中数据流动治理和客户价值。/)).toBeTruthy();
    });

    it("previews impact and requires a reason before running historical regrade", async () => {
        render(<SalesTrainerQuizAttemptDetailPage />);

        fireEvent.click(await screen.findByRole("button", { name: "预览重评影响" }));

        await waitFor(() => {
            expect(previewQuizAttemptRegradeMock).toHaveBeenCalledWith("attempt-1", {});
        });
        expect(screen.getByText("1 条历史记录")).toBeTruthy();
        expect(screen.getByText("18 / 20")).toBeTruthy();
        expect(screen.getByText("12 / 20")).toBeTruthy();

        fireEvent.change(screen.getByLabelText("重评原因"), {
            target: { value: "正确答案修订后追加历史重评记录" },
        });
        fireEvent.click(screen.getByRole("button", { name: "确认重评" }));

        await waitFor(() => {
            expect(runQuizAttemptRegradeMock).toHaveBeenCalledWith("attempt-1", {
                target_revision_id: "revision-2",
                reason: "正确答案修订后追加历史重评记录",
            });
        });
        expect(await screen.findByText(/已生成重评记录，追踪号 trace-regrade-1/)).toBeTruthy();
    });
});
