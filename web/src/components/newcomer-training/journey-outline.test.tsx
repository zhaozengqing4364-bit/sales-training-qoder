import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FoundationJourneyProjection, FoundationJourneyStage } from "@/lib/api/types/newcomer-training";
import { toJourneyPageViewModel } from "@/lib/newcomer-training/view-models";
import { JourneyOutline } from "./journey-outline";

function journeyStage(id: string, title: string, status: FoundationJourneyStage["status"]): FoundationJourneyStage {
    return {
        stage_id: id,
        sequence: id === "past" ? 1 : 2,
        title,
        objective: `${title}目标`,
        status,
        activities: [{
            activity_id: `${id}-activity`,
            type: "lesson",
            title: `${title}学习`,
            objective: `${title}活动目标`,
            status: status === "completed" ? "completed" : status === "locked" ? "locked" : "available",
            status_label: status === "completed" ? "已完成" : status === "locked" ? "未解锁" : "可开始",
            estimated_minutes: 10,
            required: true,
            blocked_reason: status === "locked" ? "等待解锁" : null,
            latest_attempt_id: null,
            latest_outcome_id: null,
        }],
    };
}

function viewStages(stages: FoundationJourneyStage[]) {
    const current = stages.find((stage) => stage.status === "current")?.activities[0] ?? null;
    const projection: FoundationJourneyProjection = {
        contract_version: "journey_projection_v1",
        generated_at: "2026-07-17T00:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_journey"],
        status: "active",
        status_label: "训练进行中",
        status_reason: null,
        enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "revision-1", version: 1 },
        path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" },
        progress: { completed_required: 0, total_required: stages.length, percentage: 0 },
        stages,
        current_activity: current,
        background_tasks: [],
        recent_outcomes: [],
        primary_action: current ? { command_type: "start", activity_id: current.activity_id, label: "开始训练", href: `/newcomer-training/activities/${current.activity_id}` } : null,
        projection_version: 1,
    };
    return toJourneyPageViewModel(projection).stages;
}

function installMotionPreference(matches: boolean) {
    Object.defineProperty(window, "matchMedia", {
        configurable: true,
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
            matches,
            media: query,
            onchange: null,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
            addListener: vi.fn(),
            removeListener: vi.fn(),
            dispatchEvent: vi.fn(),
        })),
    });
}

describe("JourneyOutline disclosure motion", () => {
    beforeEach(() => installMotionPreference(false));

    it("keeps the current stage open and links directly to available activities", async () => {
        render(<JourneyOutline stages={viewStages([
            journeyStage("past", "入门认知", "completed"),
            journeyStage("current", "产品能力", "current"),
        ])} currentStageId="current" />);

        const pastButton = screen.getByRole("button", { name: /入门认知.*已完成/ });
        const currentButton = screen.getByRole("button", { name: /产品能力.*当前/ });
        expect(pastButton.getAttribute("aria-expanded")).toBe("false");
        expect(currentButton.getAttribute("aria-expanded")).toBe("true");
        expect(screen.getByRole("link", { name: /产品能力学习/ }).getAttribute("href")).toBe("/newcomer-training/activities/current-activity");

        fireEvent.click(currentButton);
        await waitFor(() => expect(screen.queryByRole("link", { name: /产品能力学习/ })).toBeNull());

        fireEvent.click(pastButton);
        const pastLink = await screen.findByRole("link", { name: /入门认知学习/ });
        expect(pastLink.closest<HTMLElement>('[data-motion-kind="spatial"]')).not.toBeNull();
    });

    it("does not make a locked activity navigable", () => {
        render(<JourneyOutline stages={viewStages([journeyStage("future", "实战演练", "locked")])} currentStageId="future" />);
        fireEvent.click(screen.getByRole("button", { name: /实战演练.*未解锁/ }));
        expect(screen.queryByRole("link", { name: /实战演练学习/ })).toBeNull();
        expect(screen.getByLabelText("实战演练学习 未解锁")).toBeTruthy();
    });

    it("uses full transform strings and avoids layout animation", () => {
        const source = readFileSync(path.join(process.cwd(), "src/components/newcomer-training/journey-outline.tsx"), "utf8");
        expect(source).toContain("AnimatePresence initial={false}");
        expect(source).toContain("useReducedMotion");
        expect(source).toContain('translate3d(0,-8px,0)');
        expect(source).toContain('translate3d(0,0,0)');
        expect(source).not.toMatch(/\b(?:height|maxHeight|gridTemplateRows):/);
    });

    it("drops spatial movement when reduced motion is requested", async () => {
        installMotionPreference(true);
        render(<JourneyOutline stages={viewStages([journeyStage("current", "产品能力", "current")])} currentStageId="missing" />);

        fireEvent.click(screen.getByRole("button", { name: /产品能力.*当前/ }));
        const link = await screen.findByRole("link", { name: /产品能力学习/ });
        const content = link.closest<HTMLElement>('[data-motion-kind="spatial"]');
        await waitFor(() => expect(content?.style.transform ?? "").not.toContain("-8px"));
    });
});
