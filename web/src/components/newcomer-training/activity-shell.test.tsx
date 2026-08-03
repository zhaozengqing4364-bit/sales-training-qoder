import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FoundationActivityWorkspace } from "@/lib/api/types/newcomer-training";
import { toActivityViewModel } from "@/lib/newcomer-training/view-models";
import { ACTIVITY_RUNNERS, ActivityShell } from "./activity-shell";

function detail(type: "lesson" | "quiz"): FoundationActivityWorkspace {
    const common = {
        contract_version: "activity_workspace_v1" as const,
        generated_at: "2026-07-16T00:00:00Z",
        data_freshness: "fresh" as const,
        capabilities: ["view_activity", "execute_activity"],
        enrollment_version: 1,
        activity: {
            id: "activity-1",
            type,
            title: "训练活动",
            objective: "能完整讲清本次内容",
            why_it_matters: "这是进入客户实战前的必要准备",
            steps: ["阅读材料", "完成练习", "提交结果"],
            success_criteria: ["覆盖全部关键要点"],
            estimated_minutes: 15,
        },
        attempt: null,
        task: null,
        outcome: null,
        recovery: { input_preserved: true, refresh_on_version_conflict: true, retry_from_current_activity: true },
    };
    if (type === "lesson") {
        return {
            ...common,
            runner: {
                kind: "lesson", detail_id: "not-started", status: "not_started", version: 0,
                title: "产品知识入门", objectives: ["理解产品价值"], key_concepts: [], examples: [],
                checkpoints: [{ checkpoint_id: "cp-1", prompt: "我能复述核心价值", required: true }],
                practice_hints: [], progress: null,
            },
            available_commands: ["start"],
        };
    }
    return {
        ...common,
        runner: {
            kind: "quiz", detail_id: "not-started", status: "not_started", version: 0,
            title: "产品知识测验", question_count: 2,
            rules: { pass_threshold: 80, max_attempts: 3, retry_interval_seconds: 0, feedback_policy: "after_submit", time_limit_minutes: null },
            questions: [], answers: [], result: null,
        },
        available_commands: ["start"],
    };
}

describe("ActivityShell", () => {
    it.each([
        ["lesson", "开始学习"],
        ["quiz", "开始答题"],
    ] as const)("dispatches %s to its governed runner", (type, label) => {
        render(<ActivityShell detail={toActivityViewModel(detail(type))} />);
        expect(screen.getByRole("button", { name: label })).toBeTruthy();
    });

    it("contains no realtime launch renderer", () => {
        expect(Object.keys(ACTIVITY_RUNNERS)).toEqual([
            "lesson",
            "quiz",
            "audio_assessment",
            "ai_coach",
            "assignment",
        ]);
        expect(Object.keys(ACTIVITY_RUNNERS)).not.toContain("realtime_roleplay");
    });

    it("shows the persisted outcome instead of restarting a completed activity", () => {
        const completed = detail("lesson");
        if (completed.runner.kind !== "lesson") throw new Error("runner mismatch");
        completed.runner.status = "completed";
        completed.runner.version = 3;
        completed.available_commands = ["review"];
        completed.outcome = {
            lifecycle_result: "completed", assessment_result: "not_applicable", score: null,
            max_score: null, passed: null, next_action: null, produced_at: "2026-07-16T00:05:00Z",
        };

        render(<ActivityShell detail={toActivityViewModel(completed)} />);

        expect(screen.getByText("活动已完成")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "开始学习" })).toBeNull();
    });

    it("explains the goal, steps and success criteria before execution", () => {
        render(<ActivityShell detail={toActivityViewModel(detail("lesson"))} />);

        expect(screen.getByText("能完整讲清本次内容")).toBeTruthy();
        expect(screen.getByText("这是进入客户实战前的必要准备")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "怎么完成" })).toBeTruthy();
        expect(screen.getByText("阅读材料")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "完成标准" })).toBeTruthy();
        expect(screen.getByText("覆盖全部关键要点")).toBeTruthy();
        expect(screen.getByRole("link", { name: "← 返回训练路径" })).toBeTruthy();
    });
});
