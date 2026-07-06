import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerScoreResultsPage from "./page";

const {
    getCapabilitiesMock,
    pushMock,
    listQuizAttemptsMock,
    listScoreResultsMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
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
                    getCapabilities: getCapabilitiesMock,
                    listQuizAttempts: listQuizAttemptsMock,
                    listScoreResults: listScoreResultsMock,
                },
            },
        },
    };
});

describe("SalesTrainerScoreResultsPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        pushMock.mockReset();
        listQuizAttemptsMock.mockReset();
        listScoreResultsMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "ops",
            role_label: "运维人员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_global_records: true,
                retry_jobs: true,
                regrade_history: true,
                view_settings: true,
                view_logs: true,
            },
        });
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

    it("does not request result lists before view_records capability is confirmed", async () => {
        getCapabilitiesMock.mockResolvedValue({
            role: "content_admin",
            role_label: "内容管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<SalesTrainerScoreResultsPage />);

        expect(await screen.findByText("学员结果权限不足")).toBeTruthy();
        expect(screen.queryByText("暂无做题结果")).toBeNull();
        expect(screen.queryByText("暂无评分结果")).toBeNull();
        expect(listQuizAttemptsMock).not.toHaveBeenCalled();
        expect(listScoreResultsMock).not.toHaveBeenCalled();
    });

    it("keeps list load failures visible instead of rendering empty result states", async () => {
        listQuizAttemptsMock.mockRejectedValueOnce(new Error("quiz results unavailable"));
        listScoreResultsMock.mockRejectedValueOnce(new Error("score results unavailable"));

        render(<SalesTrainerScoreResultsPage />);

        expect(await screen.findByText("quiz results unavailable")).toBeTruthy();
        expect(await screen.findByText("score results unavailable")).toBeTruthy();
        expect(screen.getByText("做题结果加载失败，请检查权限、筛选条件或后端接口后重试。")).toBeTruthy();
        expect(screen.getByText("评分结果加载失败，请检查权限、筛选条件或后端接口后重试。")).toBeTruthy();
        expect(screen.queryByText("暂无做题结果")).toBeNull();
        expect(screen.queryByText("暂无评分结果")).toBeNull();
    });
});
