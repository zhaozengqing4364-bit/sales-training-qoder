import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import { toActivityViewModel } from "@/lib/newcomer-training/view-models";
import { QuizRunner } from "./quiz-runner";

const { executeCommandMock } = vi.hoisted(() => ({ executeCommandMock: vi.fn() }));

vi.mock("@/lib/api/client", () => ({
    api: { newcomerTraining: { executeCommand: executeCommandMock } },
    getApiErrorMessage: (cause: unknown) => cause instanceof Error ? cause.message : "操作失败",
}));
vi.mock("@/lib/newcomer-training/ux-events", () => ({ trackFoundationUxEvent: vi.fn() }));

function quizWorkspace(status: "not_started" | "in_progress" | "scoring_pending" = "in_progress", version = 1): FoundationActivityWorkspace {
    const started = status !== "not_started";
    return {
        contract_version: "activity_workspace_v1",
        generated_at: "2026-07-16T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_activity", "execute_activity"],
        enrollment_version: 2,
        activity: { id: "quiz-1", type: "quiz", title: "产品知识测验", objective: "检验产品理解", why_it_matters: "发现知识盲区", steps: [], success_criteria: [], estimated_minutes: 10 },
        attempt: started ? { attempt_id: "attempt-1", organization_id: "org", enrollment_id: "enrollment-1", path_revision_id: "path-r1", activity_id: "quiz-1", activity_type: "quiz", attempt_no: 1, status: status === "scoring_pending" ? "submitted" : "in_progress", version: 1, task_id: status === "scoring_pending" ? "task-1" : null, outcome_id: null } : null,
        runner: {
            kind: "quiz", detail_id: started ? "detail-1" : "not-started", status, version,
            title: "产品知识测验", question_count: 2,
            rules: { pass_threshold: 80, max_attempts: 3, retry_interval_seconds: 300, feedback_policy: "after_submit", time_limit_minutes: 10 },
            questions: started ? [
                { question_revision_id: "question-r1", question_type: "single_choice", stem: "客户最关心什么？", options: [{ option_id: "value", text: "业务价值" }, { option_id: "feature", text: "功能数量" }], points: 50 },
                { question_revision_id: "question-r2", question_type: "short_answer", stem: "请说明价值表达方式。", options: [], points: 50 },
            ] : [],
            answers: [], result: null,
        },
        task: status === "scoring_pending" ? { task_id: "task-1", state: "processing" } : null,
        outcome: null,
        available_commands: status === "not_started" ? ["start"] : status === "in_progress" ? ["save_answers", "submit"] : [],
        recovery: { input_preserved: true, refresh_on_version_conflict: true, retry_from_current_activity: true },
    };
}

describe("QuizRunner", () => {
    beforeEach(() => executeCommandMock.mockReset());

    it("shows frozen rules before start and starts against the enrollment version", async () => {
        executeCommandMock.mockResolvedValue(quizWorkspace());
        render(<QuizRunner detail={toActivityViewModel(quizWorkspace("not_started", 0))} />);

        expect(screen.getByText(/共 2 题，通过分数为 80 分/)).toBeTruthy();
        expect(screen.getByText(/最多可作答 3 次，未通过后需等待 5 分钟后再试/)).toBeTruthy();
        expect(screen.getByText(/预计 10 分钟完成，开始后限时 10 分钟/)).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "开始答题" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(1));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "start",
            expected_enrollment_version: 2,
        });
    });

    it("saves frozen question revision answers before submitting the returned version", async () => {
        const saved = quizWorkspace("in_progress", 2);
        const processing = quizWorkspace("scoring_pending", 3);
        executeCommandMock.mockResolvedValueOnce(saved).mockResolvedValueOnce(processing);
        const onRefresh = vi.fn();
        render(<QuizRunner detail={toActivityViewModel(quizWorkspace())} onRefresh={onRefresh} />);

        fireEvent.click(screen.getByRole("radio", { name: "业务价值" }));
        fireEvent.change(screen.getByRole("textbox", { name: "第 2 题答案" }), { target: { value: "先说明客户问题，再连接可量化价值。" } });
        fireEvent.click(screen.getByRole("button", { name: "提交答案" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(2));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "save_answers",
            expected_attempt_version: 1,
            payload: { answers: [
                { question_revision_id: "question-r1", selected_option_ids: ["value"], text_answer: null },
                { question_revision_id: "question-r2", selected_option_ids: [], text_answer: "先说明客户问题，再连接可量化价值。" },
            ] },
        });
        expect(executeCommandMock.mock.calls[1][1]).toMatchObject({
            command_type: "submit",
            expected_attempt_version: 2,
        });
        expect(onRefresh).toHaveBeenLastCalledWith(processing);
    });
});
