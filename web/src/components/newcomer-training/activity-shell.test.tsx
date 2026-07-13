import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ActivityDetailResponse, ActivityType } from "@/lib/api/types/newcomer-training";
import { ActivityShell } from "./activity-shell";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function detail(type: ActivityType): ActivityDetailResponse {
    const runner = type === "lesson" ? { type, learning_content_id: "content-1", completion_mode: "all_chapters" as const } : type === "quiz" ? { type, exam_paper_id: "paper-1", pass_score: 80, max_attempts: null } : type === "audio_assessment" ? { type, material_id: null, material_version_id: null, material_title: null, pass_score: 80, max_attempts: null } : type === "assignment" ? { type, submission_type: "text" as const, review_mode: "manual_review" as const, max_file_size_bytes: 10485760 } : { type };
    return { enrollment_id: "enrollment-1", path_revision_id: "revision-1", phase_id: "phase-1", module_id: "module-1", activity: { activity_id: "activity-1", activity_type: type, title: "训练活动", description: null, objective: "能完整讲清本次内容", why_it_matters: "这是进入客户实战前的必要准备", steps: ["阅读材料", "完成练习", "提交结果"], success_criteria: ["覆盖全部关键要点"], primary_action_label: null, required: true, estimated_minutes: 15, status: "not_started", completed: false, passed: null, score: null, max_score: null, locked: false, lock_reason: null, action_key: "start", is_primary_next_action: true }, runner };
}

describe("ActivityShell", () => {
    it.each([
        ["lesson", "学习内容"],
        ["quiz", "开始答题"],
        ["audio_assessment", "开始录音"],
        ["realtime_roleplay", "开始实时对练"],
        ["ai_coach", "进入 AI 辅导"],
        ["assignment", "提交作业"],
    ] as const)("dispatches %s to its trusted runner", (type, label) => {
        render(<ActivityShell detail={detail(type)} />);
        expect(screen.getByRole("button", { name: label })).toBeTruthy();
    });

    it("shows the activity result instead of restarting a completed activity", () => {
        const completed = detail("audio_assessment");
        completed.activity.status = "completed";
        completed.activity.completed = true;
        completed.activity.score = 86;
        completed.activity.max_score = 100;

        render(<ActivityShell detail={completed} />);

        expect(screen.getByText("活动已完成")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "开始录音" })).toBeNull();
    });

    it("explains the goal, steps and success criteria before execution", () => {
        render(<ActivityShell detail={detail("lesson")} />);

        expect(screen.getByText("能完整讲清本次内容")).toBeTruthy();
        expect(screen.getByText("这是进入客户实战前的必要准备")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "怎么完成" })).toBeTruthy();
        expect(screen.getByText("阅读材料")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "完成标准" })).toBeTruthy();
        expect(screen.getByText("覆盖全部关键要点")).toBeTruthy();
    });

    it("uses learner language for material confirmation", () => {
        const audioDetail = detail("audio_assessment");
        if (audioDetail.runner.type !== "audio_assessment") throw new Error("runner mismatch");
        audioDetail.runner.material_id = "material-1";
        audioDetail.runner.material_version_id = "version-1";
        audioDetail.runner.material_title = "公司介绍材料";

        render(<ActivityShell detail={audioDetail} />);

        expect(screen.getByText("我已看过材料、评分重点和讲解示例")).toBeTruthy();
        expect(screen.queryByText(/已发布版本/)).toBeNull();
    });
});
