import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerScoreStandardsPage from "./page";

const {
    listScorePromptsMock,
    pushMock,
    toastErrorMock,
    toastSuccessMock,
} = vi.hoisted(() => ({
    listScorePromptsMock: vi.fn(),
    pushMock: vi.fn(),
    toastErrorMock: vi.fn(),
    toastSuccessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/score-standards",
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: toastSuccessMock,
        error: toastErrorMock,
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    listScorePrompts: listScorePromptsMock,
                    publishScorePrompt: vi.fn(),
                    createScorePrompt: vi.fn(),
                },
            },
        },
    };
});

describe("SalesTrainerScoreStandardsPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        toastErrorMock.mockReset();
        toastSuccessMock.mockReset();
        listScorePromptsMock.mockReset();
        listScorePromptsMock.mockResolvedValue({
            items: [
                {
                    prompt_id: "prompt-1",
                    name: "PPT 讲解评分",
                    purpose: "ppt_pitch",
                    system_prompt: "system",
                    scoring_template: "{transcript}",
                    output_schema: {},
                    learner_rubric: {},
                    version: 1,
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-01T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                },
            ],
            total: 1,
        });
    });

    it("shows published scoring standards with edit as the normal revision path", async () => {
        render(<SalesTrainerScoreStandardsPage />);

        await waitFor(() => {
            expect(listScorePromptsMock).toHaveBeenCalledWith({ include_archived: true });
        });

        expect(await screen.findByText("PPT 讲解评分")).toBeTruthy();
        expect(screen.getByText("PPT 讲解录音")).toBeTruthy();
        expect(screen.queryByText("ppt_pitch")).toBeNull();
        expect(screen.getByText("已发布")).toBeTruthy();
        expect(screen.queryByText("published")).toBeNull();
        expect(screen.getByRole("button", { name: "编辑" })).toBeTruthy();
        expect(screen.queryByRole("button", { name: /复制草稿/ })).toBeNull();
    });
});
