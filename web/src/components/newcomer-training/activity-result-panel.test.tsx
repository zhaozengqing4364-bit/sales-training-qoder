import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import { toActivityViewModel } from "@/lib/newcomer-training/view-models";
import { ActivityResultPanel } from "./activity-result-panel";

function workspace(kind: "processing" | "failed" | "completed"): FoundationActivityWorkspace {
    const failed = kind === "failed";
    const completed = kind !== "processing";
    return {
        contract_version: "activity_workspace_v1",
        generated_at: "2026-07-16T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_activity"],
        enrollment_version: 1,
        activity: { id: "quiz-1", type: "quiz", title: "知识测验", objective: "检验掌握程度", why_it_matters: "发现盲区", steps: [], success_criteria: [], estimated_minutes: 10 },
        attempt: null,
        runner: {
            kind: "quiz", detail_id: "detail-1", status: kind === "processing" ? "scoring_pending" : "scored", version: 3,
            title: "知识测验", question_count: 1,
            rules: { pass_threshold: 80, max_attempts: 3, retry_interval_seconds: 0, feedback_policy: "after_submit", time_limit_minutes: null },
            questions: [], answers: [], result: completed ? { score: failed ? 60 : 88, max_score: 100, passed: !failed } : null,
        },
        task: kind === "processing" ? { task_id: "task-1", state: "processing" } : null,
        outcome: completed ? { lifecycle_result: "completed", assessment_result: failed ? "not_passed" : "passed", score: failed ? 60 : 88, max_score: 100, passed: !failed, next_action: null, produced_at: "2026-07-16T00:05:00Z" } : null,
        available_commands: [],
        recovery: { input_preserved: true, refresh_on_version_conflict: true, retry_from_current_activity: true },
    };
}

describe("ActivityResultPanel", () => {
    it.each([
        ["processing", "已提交，正在处理"],
        ["failed", "这次还未通过"],
        ["completed", "活动已完成"],
    ] as const)("reveals the %s result without changing its semantics", (kind, title) => {
        render(<ActivityResultPanel detail={toActivityViewModel(workspace(kind))} />);
        const panel = screen.getByText(title).closest("section");
        expect(panel?.className).toContain("motion-result-reveal");
        expect(panel?.getAttribute("aria-live")).toBe("polite");
    });

    it("explains processing without pretending the activity is complete", () => {
        render(<ActivityResultPanel detail={toActivityViewModel(workspace("processing"))} />);
        expect(screen.getByText("当前答案已经保留。", { exact: false })).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回训练路径" })).toBeTruthy();
    });

    it("shows the persisted score", () => {
        render(<ActivityResultPanel detail={toActivityViewModel(workspace("completed"))} />);
        expect(screen.getByText("88 / 100")).toBeTruthy();
    });
});
