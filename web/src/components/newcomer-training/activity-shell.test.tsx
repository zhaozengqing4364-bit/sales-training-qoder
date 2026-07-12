import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ActivityDetailResponse, ActivityType } from "@/lib/api/types/newcomer-training";
import { ActivityShell } from "./activity-shell";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function detail(type: ActivityType): ActivityDetailResponse {
    const runner = type === "lesson" ? { type, learning_content_id: "content-1", completion_mode: "all_chapters" as const } : type === "quiz" ? { type, exam_paper_id: "paper-1", pass_score: 80, max_attempts: null } : type === "audio_assessment" ? { type, material_id: null, material_version_id: null, material_title: null, pass_score: 80, max_attempts: null } : type === "assignment" ? { type, submission_type: "text" as const, review_mode: "manual_review" as const, max_file_size_bytes: 10485760 } : { type };
    return { enrollment_id: "enrollment-1", path_revision_id: "revision-1", phase_id: "phase-1", module_id: "module-1", activity: { activity_id: "activity-1", activity_type: type, title: "训练活动", description: null, required: true, status: "not_started", completed: false, passed: null, score: null, max_score: null, locked: false, lock_reason: null, action_key: "start", is_primary_next_action: true }, runner };
}

describe("ActivityShell", () => {
    it.each([
        ["lesson", "学习内容"],
        ["quiz", "开始答题"],
        ["audio_assessment", "上传讲解录音"],
        ["realtime_roleplay", "开始实时对练"],
        ["ai_coach", "进入 AI 辅导"],
        ["assignment", "提交作业"],
    ] as const)("dispatches %s to its trusted runner", (type, label) => {
        render(<ActivityShell detail={detail(type)} />);
        expect(screen.getByRole("button", { name: label })).toBeTruthy();
    });
});
