import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerLearnHubPage from "./page";

const { listUnitsMock } = vi.hoisted(() => ({
    listUnitsMock: vi.fn(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                listUnits: listUnitsMock,
            },
        },
    };
});

describe("SalesTrainerLearnHubPage", () => {
    beforeEach(() => {
        listUnitsMock.mockReset();
        listUnitsMock.mockResolvedValue({
            items: [
                {
                    unit_id: "business-unit",
                    name: "模块二：商务技巧",
                    description: null,
                    unit_type: "quiz",
                    config: {
                        learner: { learning_content_id: "content-1" },
                    },
                    status: "published",
                    created_by: null,
                    updated_by: null,
                    created_at: "2026-06-01T00:00:00Z",
                    updated_at: "2026-06-01T00:00:00Z",
                    questions: [],
                },
            ],
            total: 1,
        });
    });

    it("routes the legacy learning hub to the governed business skills learning page", async () => {
        render(<SalesTrainerLearnHubPage />);

        expect(await screen.findByText("商务技巧学习入口已升级")).toBeTruthy();
        expect(screen.getByRole("link", { name: "进入商务技巧学习" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills",
        );
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(screen.queryByText(/seed_coo_path_extension/)).toBeNull();
        expect(screen.queryByText(/new_seller_modules_v1/)).toBeNull();
        expect(screen.queryByText(/讲义 ID/)).toBeNull();
        expect(screen.queryByText(/COO/)).toBeNull();
    });
});
