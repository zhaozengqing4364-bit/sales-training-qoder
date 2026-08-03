import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { FoundationJourneyProjection, FoundationJourneyStage } from "@/lib/api/types/newcomer-training";
import { toJourneyPageViewModel } from "@/lib/newcomer-training/view-models";
import { JourneyHome } from "./journey-home";

vi.mock("./foundation-ux-signal", () => ({ FoundationUxSignal: () => null }));

function stage(id: string, title: string, status: FoundationJourneyStage["status"]): FoundationJourneyStage {
    return {
        stage_id: id,
        sequence: id === "past" ? 1 : id === "current" ? 2 : 3,
        title,
        objective: `${title}完成目标`,
        status,
        activities: [{
            activity_id: `${id}-activity`,
            type: "lesson",
            title: `${title}学习`,
            objective: status === "current" ? "能向客户讲清核心产品价值" : `${title}学习目标`,
            status: status === "completed" ? "completed" : status === "locked" ? "locked" : "available",
            status_label: status === "completed" ? "已完成" : status === "locked" ? "未解锁" : "可开始",
            estimated_minutes: 15,
            required: true,
            blocked_reason: status === "locked" ? "完成当前阶段后解锁" : null,
            latest_attempt_id: null,
            latest_outcome_id: null,
        }],
    };
}

function journey(): FoundationJourneyProjection {
    const stages = [stage("past", "入门认知", "completed"), stage("current", "产品能力", "current"), stage("future", "实战演练", "locked")];
    return {
        contract_version: "journey_projection_v1",
        generated_at: "2026-07-16T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_journey"],
        status: "active",
        status_label: "训练进行中",
        status_reason: null,
        enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "revision-1", version: 1 },
        path: { path_id: "path-1", title: "新人训练", revision_label: "v1" },
        progress: { completed_required: 1, total_required: 3, percentage: 33 },
        stages,
        current_activity: stages[1].activities[0],
        background_tasks: [],
        recent_outcomes: [],
        primary_action: { command_type: "start", activity_id: "current-activity", label: "继续学习", href: "/newcomer-training/activities/current-activity" },
        projection_version: 1,
    };
}

describe("JourneyHome", () => {
    it("shows exactly one backend-projected primary action", () => {
        render(<JourneyHome journey={toJourneyPageViewModel(journey())} />);

        expect(screen.getAllByRole("link", { name: "继续学习" })).toHaveLength(1);
        expect(screen.getByRole("heading", { name: "产品能力学习" })).toBeTruthy();
        expect(screen.getByText("能向客户讲清核心产品价值")).toBeTruthy();
        expect(screen.queryByText("我的全部录音")).toBeNull();
    });

    it("announces the all-training-complete milestone", () => {
        const completed = journey();
        completed.status = "completed";
        completed.status_label = "训练已完成";
        completed.stages = completed.stages.map((item) => ({
            ...item,
            status: "completed",
            activities: item.activities.map((activity) => ({ ...activity, status: "completed", status_label: "已完成" })),
        }));
        completed.progress = { completed_required: 3, total_required: 3, percentage: 100 };
        completed.current_activity = null;
        completed.primary_action = null;

        render(<JourneyHome journey={toJourneyPageViewModel(completed)} />);

        const card = screen.getByText("当前训练已全部完成").closest("section");
        expect(card?.className).toContain("motion-completion-reveal");
        expect(card?.getAttribute("aria-live")).toBe("polite");
    });

    it("does not pretend an unassigned learner has completed training", () => {
        const unassigned = journey();
        unassigned.status = "not_enrolled";
        unassigned.status_label = "尚未分配训练";
        unassigned.status_reason = "请联系培训负责人分配训练路径。";
        unassigned.enrollment = null;
        unassigned.path = null;
        unassigned.stages = [];
        unassigned.current_activity = null;
        unassigned.primary_action = null;

        render(<JourneyHome journey={toJourneyPageViewModel(unassigned)} />);

        expect(screen.getByText("尚未分配训练")).toBeTruthy();
        expect(screen.queryByText("当前训练已全部完成")).toBeNull();
    });

    it("keeps only the current stage expanded", () => {
        render(<JourneyHome journey={toJourneyPageViewModel(journey())} />);
        expect(screen.getByRole("button", { name: /入门认知.*已完成/ }).getAttribute("aria-expanded")).toBe("false");
        expect(screen.getByRole("button", { name: /产品能力.*当前/ }).getAttribute("aria-expanded")).toBe("true");
        expect(screen.getByRole("button", { name: /实战演练.*未解锁/ }).getAttribute("aria-expanded")).toBe("false");
    });
});
