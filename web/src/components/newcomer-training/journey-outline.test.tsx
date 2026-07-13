import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JourneyPhaseProgress } from "@/lib/api/types/newcomer-training";
import { JourneyOutline } from "./journey-outline";

function journeyPhase(id: string, title: string, status: string, completed = false): JourneyPhaseProgress {
    return {
        phase_id: id,
        title,
        description: null,
        outcome: `${title}目标`,
        required: true,
        status,
        completed,
        completed_count: completed ? 1 : 0,
        total_required: 1,
        percent: completed ? 100 : 0,
        locked: status === "locked",
        lock_reason: status === "locked" ? "完成上一阶段后解锁" : null,
        modules: [{
            module_id: `${id}-module`,
            title: `${title}模块`,
            description: null,
            outcome: `${title}模块目标`,
            required: true,
            estimated_minutes: 20,
            status,
            completed,
            completed_count: completed ? 1 : 0,
            total_required: 1,
            percent: completed ? 100 : 0,
            locked: status === "locked",
            lock_reason: status === "locked" ? "等待解锁" : null,
            activities: [{
                activity_id: `${id}-activity`,
                activity_type: "lesson",
                title: `${title}学习`,
                description: null,
                objective: null,
                why_it_matters: null,
                steps: [],
                success_criteria: [],
                primary_action_label: null,
                required: true,
                estimated_minutes: 10,
                status,
                completed,
                passed: null,
                score: null,
                max_score: null,
                locked: status === "locked",
                lock_reason: null,
                action_key: completed ? null : "continue_lesson",
                is_primary_next_action: status === "in_progress",
            }],
        }],
    };
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

    it("keeps the current phase open and animates later disclosure changes", async () => {
        render(<JourneyOutline phases={[
            journeyPhase("past", "入门认知", "completed", true),
            journeyPhase("current", "产品能力", "in_progress"),
        ]} currentPhaseId="current" />);

        const pastButton = screen.getByRole("button", { name: /入门认知.*已完成/ });
        const currentButton = screen.getByRole("button", { name: /产品能力.*当前/ });
        expect(pastButton.getAttribute("aria-expanded")).toBe("false");
        expect(currentButton.getAttribute("aria-expanded")).toBe("true");
        expect(screen.getByRole("link", { name: /产品能力模块目标/ })).toBeTruthy();
        const chevronMotion = currentButton.querySelector<HTMLElement>("[data-chevron-motion]");
        expect(chevronMotion).not.toBeNull();
        expect(chevronMotion?.className).toContain("transition-transform");
        expect(chevronMotion?.querySelector("svg")?.getAttribute("class") ?? "").not.toContain("transition-transform");

        fireEvent.click(currentButton);
        expect(currentButton.getAttribute("aria-expanded")).toBe("false");
        await waitFor(() => expect(screen.queryByRole("link", { name: /产品能力模块目标/ })).toBeNull());

        fireEvent.click(pastButton);
        const pastLink = await screen.findByRole("link", { name: /入门认知模块目标/ });
        expect(pastButton.getAttribute("aria-expanded")).toBe("true");
        expect(pastLink.closest<HTMLElement>('[data-motion-kind="spatial"]')).not.toBeNull();
    });

    it("uses full transform strings and avoids layout animation", () => {
        const source = readFileSync(path.join(process.cwd(), "src/components/newcomer-training/journey-outline.tsx"), "utf8");
        expect(source).toContain("AnimatePresence initial={false}");
        expect(source).toContain("useReducedMotion");
        expect(source).toContain('translate3d(0,-8px,0)');
        expect(source).toContain('translate3d(0,0,0)');
        expect(source).not.toMatch(/\b(?:height|maxHeight|gridTemplateRows):/);
        expect(source).not.toMatch(/\n\s+[xy]:/);
    });

    it("drops spatial movement when reduced motion is requested", async () => {
        installMotionPreference(true);
        render(<JourneyOutline phases={[journeyPhase("current", "产品能力", "in_progress")]} currentPhaseId="missing" />);

        fireEvent.click(screen.getByRole("button", { name: /产品能力.*待开始/ }));
        const link = await screen.findByRole("link", { name: /产品能力模块目标/ });
        const content = link.closest<HTMLElement>('[data-motion-kind="spatial"]');
        expect(content).not.toBeNull();
        await waitFor(() => expect(content?.style.transform ?? "").not.toContain("-8px"));
    });
});
