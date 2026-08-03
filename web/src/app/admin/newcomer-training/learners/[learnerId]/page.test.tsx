import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

const { getLearner } = vi.hoisted(() => ({ getLearner: vi.fn() }));
vi.mock("next/navigation", () => ({ useParams: () => ({ learnerId: "learner-1" }) }));
vi.mock("@/lib/api/client", () => ({ api: { admin: { newcomerTraining: { getLearner } } }, getApiErrorMessage: (error: Error) => error.message }));

describe("newcomer learner journey detail", () => {
    beforeEach(() => getLearner.mockReset());

    it("shows stage and activity status from the v2 Journey projection", async () => {
        getLearner.mockResolvedValue({ learner: { learner_id: "learner-1", name: "张三" }, cohort: { cohort_id: "cohort-1", name: "七月新人班" }, journey: { contract_version: "journey_projection_v1", generated_at: "2026-07-18T00:00:00Z", data_freshness: "fresh", capabilities: ["view_journey"], status: "active", status_label: "训练进行中", status_reason: null, enrollment: { enrollment_id: "e1", status: "active", revision_id: "r1", version: 1 }, path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" }, progress: { completed_required: 1, total_required: 2, percentage: 50 }, stages: [{ stage_id: "stage-1", sequence: 1, title: "产品能力", objective: "建立产品知识", status: "current", activities: [{ activity_id: "a1", type: "audio_assessment", title: "讲解录音", objective: "准确讲解", status: "in_progress", status_label: "继续完成", estimated_minutes: 10, required: true, blocked_reason: null, latest_attempt_id: "attempt-1", latest_outcome_id: null }] }], current_activity: null, background_tasks: [], recent_outcomes: [], primary_action: null, projection_version: 1 } });
        render(<Page />);
        await waitFor(() => expect(screen.getByText("产品能力")).toBeTruthy());
        expect(screen.getByText("讲解录音")).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看所属班级" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "进入达标复核" })).toBeTruthy();
    });
});
