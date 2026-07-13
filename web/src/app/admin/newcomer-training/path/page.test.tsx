import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/newcomer-training/path",
}));

const { getPath, listExamPapers } = vi.hoisted(() => ({ getPath: vi.fn(), listExamPapers: vi.fn() }));

vi.mock("@/lib/api/client", () => ({
    api: {
        learningContents: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
        admin: {
            newcomerTraining: { getPath, listCoachProfiles: vi.fn().mockResolvedValue([]), listScoringRubrics: vi.fn().mockResolvedValue([]) },
            salesTrainer: {
                listExamPapers,
                listMaterials: vi.fn().mockResolvedValue({ items: [], total: 0 }),
            },
            listPracticeTemplates: vi.fn().mockResolvedValue({ items: [], total: 0 }),
            getVoiceRuntimeProfiles: vi.fn().mockResolvedValue({ items: [], total: 0 }),
        },
    },
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn(), showToast: vi.fn() }),
}));

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

describe("newcomer path page", () => {
    beforeEach(() => {
        getPath.mockReset();
        listExamPapers.mockReset().mockResolvedValue({ items: [], total: 0 });
    });

    it("keeps the editor usable when one resource catalog fails", async () => {
        const user = userEvent.setup();
        getPath.mockResolvedValue({
            active_revision_id: null, active_revision_no: null, working_revision_id: null,
            payload: { schema_version: "newcomer_training_orchestration_v1", title: "新人训练路径", description: null, phases: [] },
            validation: null,
        });
        listExamPapers.mockRejectedValue(new Error("paper catalog unavailable"));

        render(<Page />);

        await waitFor(() => expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy());
        expect(screen.getByRole("alert").textContent).toContain("试卷目录暂不可用");
        expect(screen.getByRole("button", { name: "重新加载试卷目录" })).toBeTruthy();

        listExamPapers.mockResolvedValue({ items: [], total: 0 });
        await user.click(screen.getByRole("button", { name: "重新加载试卷目录" }));
        await waitFor(() => expect(screen.queryByText("试卷目录暂不可用")).toBeNull());
        expect(getPath).toHaveBeenCalledTimes(1);
        expect(listExamPapers).toHaveBeenCalledTimes(2);
    });

    it("loads the focused editor from the canonical API", async () => {
        getPath.mockResolvedValue({
            active_revision_id: null,
            active_revision_no: null,
            working_revision_id: null,
            payload: {
                schema_version: "newcomer_training_orchestration_v1",
                title: "新人训练路径",
                description: null,
                phases: [],
            },
            validation: null,
        });

        render(<Page />);
        expect(screen.getByText("正在加载训练路径…")).toBeTruthy();
        await waitFor(() => expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy());
        expect(getPath).toHaveBeenCalledTimes(1);
    });

    it("shows the path editor without waiting for slow resource catalogs", async () => {
        getPath.mockResolvedValue({
            active_revision_id: null,
            active_revision_no: null,
            working_revision_id: null,
            payload: {
                schema_version: "newcomer_training_orchestration_v1",
                title: "新人训练路径",
                description: null,
                phases: [],
            },
            validation: null,
        });
        listExamPapers.mockImplementation(() => new Promise(() => undefined));

        render(<Page />);

        expect(await screen.findByRole("tree", { name: "训练路径大纲" })).toBeTruthy();
        expect(screen.getByText("可选资源仍在后台加载，不影响查看和编排路径。")).toBeTruthy();
    });

    it("shows a retryable inline error", async () => {
        getPath.mockRejectedValue(new Error("network"));
        render(<Page />);
        expect((await screen.findByRole("alert")).textContent).toContain("训练路径加载失败");
        expect(screen.getByRole("button", { name: "重新加载" })).toBeTruthy();
    });
});
