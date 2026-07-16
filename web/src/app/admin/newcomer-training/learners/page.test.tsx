import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/newcomer-training/learners",
}));

const { listJourneys } = vi.hoisted(() => ({ listJourneys: vi.fn() }));
vi.mock("@/lib/api/client", () => ({ api: { admin: { newcomerTraining: { listJourneys } } }, getApiErrorMessage: (error: Error) => error.message }));
vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => ({
        capabilities: { capabilities: { admin_full_access: true } },
        canAccess: true,
        denialMessage: null,
        error: null,
        isLoading: false,
        reloadCapabilities: vi.fn(),
    }),
}));

describe("newcomer learner operations page", () => {
    beforeEach(() => listJourneys.mockReset());

    it("shows progress and the authoritative next action", async () => {
        listJourneys.mockResolvedValue({ items: [{ learner_id: "learner-1", learner_name: "张三", team: { team_id: "team-east", code: "east", name: "华东销售" }, summary: { path_revision_id: "rev-1", path_title: "新人训练", current_phase: null, progress: { completed: false, completed_count: 1, total_required: 3, percent: 33 }, primary_next_action: { activity_id: "a1", activity_type: "audio_assessment", action_key: "record_audio", label: "产品讲解录音" }, risk_labels: [] } }], total: 1 });
        render(<Page />);
        await waitFor(() => expect(screen.getByText("张三")).toBeTruthy());
        expect(screen.getByText("33%")).toBeTruthy();
        expect(screen.getByText("下一步：产品讲解录音")).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看训练详情" })).toBeTruthy();
    });

    it("renders an actionable empty state", async () => {
        listJourneys.mockResolvedValue({ items: [], total: 0 });
        render(<Page />);
        expect(await screen.findByText("还没有进入新人训练的学员")).toBeTruthy();
    });
});
