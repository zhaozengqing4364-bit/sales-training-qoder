import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { JourneyPhaseProgress, JourneyResponse } from "@/lib/api/types/newcomer-training";
import { JourneyHome } from "./journey-home";

function phase(id: string, title: string, status: string, completed: boolean): JourneyPhaseProgress {
    return {
        phase_id: id, title, description: null, required: true, status, completed,
        completed_count: completed ? 1 : 0, total_required: 1, percent: completed ? 100 : 0,
        locked: status === "locked", lock_reason: status === "locked" ? "完成当前阶段后解锁" : null,
        modules: [{
            module_id: `${id}-module`, title: `${title}模块`, description: null, required: true,
            estimated_minutes: 35,
            status, completed, completed_count: completed ? 1 : 0, total_required: 1,
            percent: completed ? 100 : 0, locked: status === "locked", lock_reason: null,
            activities: [{
                activity_id: `${id}-activity`, activity_type: "lesson", title: `${title}学习`,
                description: null, required: true, estimated_minutes: 15, status, completed, passed: null, score: null,
                max_score: null, locked: status === "locked", lock_reason: null,
                action_key: completed ? null : "continue_lesson",
                is_primary_next_action: status === "in_progress",
            }],
        }],
    };
}

function journey(): JourneyResponse {
    return { enrollment_id: "enrollment-1", path_revision_id: "revision-1", path_title: "新人训练", phases: [phase("past", "入门认知", "completed", true), phase("current", "产品能力", "in_progress", false), phase("future", "实战演练", "locked", false)], progress: { completed: false, completed_count: 1, total_required: 3, percent: 33 }, primary_next_action: { activity_id: "current-activity", activity_type: "lesson", action_key: "continue_lesson", label: "继续学习" } };
}

describe("JourneyHome", () => {
    it("shows exactly one primary continue action", () => {
        render(<JourneyHome journey={journey()} />);
        expect(screen.getAllByRole("link", { name: "开始内容学习" })).toHaveLength(1);
        expect(screen.getByText("当前阶段：产品能力")).toBeTruthy();
        expect(screen.queryByText("我的全部录音")).toBeNull();
    });

    it("collapses completed and future phases", () => {
        render(<JourneyHome journey={journey()} />);
        expect(screen.getByRole("button", { name: /入门认知.*已完成/ }).getAttribute("aria-expanded")).toBe("false");
        expect(screen.getByRole("button", { name: /产品能力.*当前/ }).getAttribute("aria-expanded")).toBe("true");
        expect(screen.getByRole("button", { name: /实战演练.*未解锁/ }).getAttribute("aria-expanded")).toBe("false");
    });

    it("uses the activity-specific action and shows estimated time", () => {
        const audioJourney = journey();
        const activity = audioJourney.phases[1].modules[0].activities[0];
        activity.activity_type = "audio_assessment";
        audioJourney.primary_next_action = {
            activity_id: activity.activity_id,
            activity_type: "audio_assessment",
            action_key: "submit_audio",
            label: activity.title,
        };

        render(<JourneyHome journey={audioJourney} />);

        expect(screen.getByRole("link", { name: "开始录音讲解" })).toBeTruthy();
        expect(screen.getByText("预计 15 分钟")).toBeTruthy();
        expect(screen.getAllByText("当前")).toHaveLength(1);
    });
});
