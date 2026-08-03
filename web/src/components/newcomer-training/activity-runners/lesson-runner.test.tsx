import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import { toActivityViewModel } from "@/lib/newcomer-training/view-models";
import { LessonRunner } from "./lesson-runner";

const { executeCommandMock } = vi.hoisted(() => ({ executeCommandMock: vi.fn() }));

vi.mock("@/lib/api/client", () => ({
    api: { newcomerTraining: { executeCommand: executeCommandMock } },
    getApiErrorMessage: (cause: unknown) => cause instanceof Error ? cause.message : "操作失败",
}));
vi.mock("@/lib/newcomer-training/ux-events", () => ({ trackFoundationUxEvent: vi.fn() }));

function lessonWorkspace(status: "not_started" | "in_progress" | "completed" = "in_progress", version = 1): FoundationActivityWorkspace {
    const started = status !== "not_started";
    return {
        contract_version: "activity_workspace_v1",
        generated_at: "2026-07-16T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_activity", "execute_activity"],
        enrollment_version: 4,
        activity: { id: "lesson-1", type: "lesson", title: "产品知识", objective: "理解产品价值", why_it_matters: "建立准确表达", steps: [], success_criteria: [], estimated_minutes: 15 },
        attempt: started ? { attempt_id: "attempt-1", organization_id: "org", enrollment_id: "enrollment-1", path_revision_id: "path-r1", activity_id: "lesson-1", activity_type: "lesson", attempt_no: 1, status: status === "completed" ? "completed" : "in_progress", version: 1, task_id: null, outcome_id: null } : null,
        runner: {
            kind: "lesson", detail_id: started ? "detail-1" : "not-started", status, version,
            title: "产品知识", objectives: ["理解产品价值"],
            key_concepts: [{ concept_id: "concept-1", title: "核心价值", content: "帮助客户更快完成关键任务。", sources: ["产品手册第 2 页"] }],
            examples: [], checkpoints: [{ checkpoint_id: "cp-1", prompt: "我能复述核心价值", required: true }], practice_hints: [],
            progress: started ? { completed_checkpoint_ids: [], reading_position: {}, last_saved_at: "2026-07-16T00:00:00Z" } : null,
        },
        task: null,
        outcome: null,
        available_commands: status === "not_started" ? ["start"] : status === "in_progress" ? ["save_progress", "complete"] : ["review"],
        recovery: { input_preserved: true, refresh_on_version_conflict: true, retry_from_current_activity: true },
    };
}

describe("LessonRunner", () => {
    beforeEach(() => executeCommandMock.mockReset());

    it("starts against the frozen enrollment version", async () => {
        const current = lessonWorkspace("not_started", 0);
        executeCommandMock.mockResolvedValue(lessonWorkspace());
        render(<LessonRunner detail={toActivityViewModel(current)} />);

        fireEvent.click(screen.getByRole("button", { name: "开始学习" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(1));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "start",
            expected_enrollment_version: 4,
            payload: { relearn_of_detail_id: null },
        });
    });

    it("preserves checkpoint progress before completing with the returned detail version", async () => {
        const current = lessonWorkspace();
        const saved = lessonWorkspace("in_progress", 2);
        const completed = lessonWorkspace("completed", 3);
        executeCommandMock.mockResolvedValueOnce(saved).mockResolvedValueOnce(completed);
        const onRefresh = vi.fn();
        render(<LessonRunner detail={toActivityViewModel(current)} onRefresh={onRefresh} />);

        fireEvent.click(screen.getByRole("checkbox", { name: /我能复述核心价值/ }));
        fireEvent.click(screen.getByRole("button", { name: "完成学习" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(2));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "save_progress",
            expected_attempt_version: 1,
            payload: { completed_checkpoint_ids: ["cp-1"] },
        });
        expect(executeCommandMock.mock.calls[1][1]).toMatchObject({
            command_type: "complete",
            expected_attempt_version: 2,
        });
        expect(onRefresh).toHaveBeenLastCalledWith(completed);
    });
});
