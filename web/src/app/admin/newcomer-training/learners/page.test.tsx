import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

const { replace, listLearners } = vi.hoisted(() => ({ replace: vi.fn(), listLearners: vi.fn() }));
vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/newcomer-training/learners",
    useRouter: () => ({ replace }),
    useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api/client", () => ({ api: { admin: { newcomerTraining: { listLearners } } }, getApiErrorMessage: (error: Error) => error.message }));

describe("newcomer learner operations page", () => {
    beforeEach(() => {
        listLearners.mockReset();
        replace.mockReset();
    });

    it("shows progress and the authoritative next action", async () => {
        listLearners.mockResolvedValue({ items: [{ learner: { learner_id: "learner-1", name: "张三" }, cohort: { cohort_id: "cohort-1", name: "华东新人班" }, enrollment: { enrollment_id: "enrollment-1", status: "active", revision_id: "rev-1", version: 1 }, path: { path_id: "path-1", title: "新人训练", revision_label: "首发版" }, status: "active", status_label: "训练进行中", progress: { completed_required: 1, total_required: 3, percentage: 33 }, current_activity: null, primary_action: { command_type: "continue_activity", activity_id: "a1", label: "产品讲解录音", href: "/newcomer-training/activities/a1" }, updated_at: "2026-07-18T00:00:00Z" }], total: 1, limit: 20, offset: 0, applied_filters: { search: null }, generated_at: "2026-07-18T00:00:00Z" });
        render(<Page />);
        await waitFor(() => expect(screen.getByText("张三")).toBeTruthy());
        expect(screen.getByText("33%")).toBeTruthy();
        expect(screen.getByText("下一步：产品讲解录音")).toBeTruthy();
        expect(screen.getByRole("link", { name: "查看训练详情" })).toBeTruthy();
        expect(listLearners).toHaveBeenCalledWith({ search: undefined, limit: 20, offset: 0 });
    });

    it("renders an actionable empty state", async () => {
        listLearners.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0, applied_filters: { search: null }, generated_at: "2026-07-18T00:00:00Z" });
        render(<Page />);
        expect(await screen.findByText("还没有进入新人训练的学员")).toBeTruthy();
    });
});
