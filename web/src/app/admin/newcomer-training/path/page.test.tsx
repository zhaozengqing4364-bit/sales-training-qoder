import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

const { getPath } = vi.hoisted(() => ({ getPath: vi.fn() }));

vi.mock("@/lib/api/client", () => ({
    api: {
        learningContents: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) },
        admin: {
            newcomerTraining: { getPath, listCoachProfiles: vi.fn().mockResolvedValue([]), listScoringRubrics: vi.fn().mockResolvedValue([]) },
            salesTrainer: {
                listExamPapers: vi.fn().mockResolvedValue({ items: [], total: 0 }),
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

describe("newcomer path page", () => {
    beforeEach(() => {
        getPath.mockReset();
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

    it("shows a retryable inline error", async () => {
        getPath.mockRejectedValue(new Error("network"));
        render(<Page />);
        expect((await screen.findByRole("alert")).textContent).toContain("训练路径加载失败");
        expect(screen.getByRole("button", { name: "重新加载" })).toBeTruthy();
    });
});
