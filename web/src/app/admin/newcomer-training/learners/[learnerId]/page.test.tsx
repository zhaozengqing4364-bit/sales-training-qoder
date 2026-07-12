import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

const { getLearnerJourney } = vi.hoisted(() => ({ getLearnerJourney: vi.fn() }));
vi.mock("next/navigation", () => ({ useParams: () => ({ learnerId: "learner-1" }) }));
vi.mock("@/lib/api/client", () => ({ api: { admin: { newcomerTraining: { getLearnerJourney } } }, getApiErrorMessage: (error: Error) => error.message }));

describe("newcomer learner journey detail", () => {
    beforeEach(() => getLearnerJourney.mockReset());

    it("shows phase, module and activity status with existing evidence links", async () => {
        getLearnerJourney.mockResolvedValue({ enrollment_id: "e1", path_revision_id: "r1", path_title: "新人训练", progress: { completed: false, completed_count: 1, total_required: 2, percent: 50 }, primary_next_action: null, phases: [{ phase_id: "p1", title: "产品能力", description: null, required: true, status: "in_progress", completed: false, completed_count: 1, total_required: 2, percent: 50, locked: false, lock_reason: null, modules: [{ module_id: "m1", title: "产品 A", description: null, required: true, status: "in_progress", completed: false, completed_count: 1, total_required: 2, percent: 50, locked: false, lock_reason: null, activities: [{ activity_id: "a1", activity_type: "audio_assessment", title: "讲解录音", description: null, required: true, status: "in_progress", completed: false, passed: null, score: null, max_score: null, locked: false, lock_reason: null, action_key: null, is_primary_next_action: false }] }] }] });
        render(<Page />);
        await waitFor(() => expect(screen.getByText("产品能力")).toBeTruthy());
        expect(screen.getByText("讲解录音")).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看训练记录" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看录音" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "达标验收" })).toBeTruthy();
    });
});
