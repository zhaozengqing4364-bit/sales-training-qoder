import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerScoreResultsPage from "./page";

const {
    pushMock,
    listQuizAttemptsMock,
    listScoreResultsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    listQuizAttemptsMock: vi.fn(),
    listScoreResultsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/score-results",
    useRouter: () => ({ push: pushMock }),
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
                    listQuizAttempts: listQuizAttemptsMock,
                    listScoreResults: listScoreResultsMock,
                },
            },
        },
    };
});

describe("SalesTrainerScoreResultsPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        listQuizAttemptsMock.mockReset();
        listScoreResultsMock.mockReset();
        listQuizAttemptsMock.mockResolvedValue({
            items: [
                {
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
                    answers: [],
                },
            ],
            total: 1,
        });
        listScoreResultsMock.mockResolvedValue({
            items: [
                {
                    score_id: "score-1",
                    submission_id: "submission-1",
                    prompt_id: "prompt-1",
                    prompt_version: 2,
                    prompt_hash: "hash",
                    deucate_model: "deucate-v1",
                    transcript_snapshot: "转写文本",
                    total_score: 88,
                    passed: true,
                    summary: "表达清楚",
                    strengths: [],
                    improvements: [],
                    dimension_scores: {},
                    raw_response: {},
                    error_code: null,
                    error_message: null,
                    latency_ms: 20,
                    created_at: "2026-05-28T00:00:00Z",
                },
            ],
            total: 1,
        });
    });

    it("loads score results and supports filtering by user and submission", async () => {
        render(<SalesTrainerScoreResultsPage />);

        await waitFor(() => {
            expect(listQuizAttemptsMock).toHaveBeenCalledWith({ limit: 100 });
            expect(listScoreResultsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        expect(screen.getByText("张三 · 销售一部")).toBeTruthy();
        expect(screen.getByText("训练任务")).toBeTruthy();
        expect(screen.getByText("编号：unit-1")).toBeTruthy();
        expect(screen.queryByText("训练单元 unit-1")).toBeNull();
        expect(screen.getByLabelText("训练任务编号")).toBeTruthy();
        expect(screen.queryByText("训练单元 ID")).toBeNull();
        expect(screen.queryByPlaceholderText("按 unit_id 查询")).toBeNull();
        expect(screen.getByText("18")).toBeTruthy();
        expect(screen.getByText("submission-1")).toBeTruthy();
        expect(screen.getByText("deucate-v1")).toBeTruthy();

        fireEvent.change(screen.getAllByLabelText("学员编号")[0], {
            target: { value: "user-1" },
        });
        fireEvent.change(screen.getByLabelText("训练任务编号"), {
            target: { value: "unit-1" },
        });
        fireEvent.click(screen.getAllByRole("button", { name: "查询" })[0]);

        await waitFor(() => {
            expect(listQuizAttemptsMock).toHaveBeenLastCalledWith({
                user_id: "user-1",
                unit_id: "unit-1",
                limit: 100,
            });
        });

        fireEvent.change(screen.getAllByLabelText("学员编号")[1], {
            target: { value: "user-1" },
        });
        fireEvent.change(screen.getByLabelText("录音提交编号"), {
            target: { value: "submission-1" },
        });
        fireEvent.click(screen.getAllByRole("button", { name: "查询" })[1]);

        await waitFor(() => {
            expect(listScoreResultsMock).toHaveBeenLastCalledWith({
                user_id: "user-1",
                submission_id: "submission-1",
                limit: 100,
            });
        });

        fireEvent.click(screen.getByRole("button", { name: "查看详情" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/quiz-attempts/attempt-1");

        fireEvent.click(screen.getByRole("button", { name: "查看录音" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/audio-submissions/submission-1");
    });
});
