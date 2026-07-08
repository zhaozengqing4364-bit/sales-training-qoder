import { describe, expect, it, vi } from "vitest";

import LegacyTrainingTaskDetailPage from "./page";

const { redirectMock } = vi.hoisted(() => ({
    redirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    redirect: redirectMock,
}));

describe("LegacyTrainingTaskDetailPage", () => {
    it("redirects the legacy scenario detail to the matching audio task", async () => {
        await LegacyTrainingTaskDetailPage({
            params: Promise.resolve({ scenarioSlug: "company-product-demo" }),
        });

        expect(redirectMock).toHaveBeenCalledWith(
            "/admin/sales-trainer/audio/company-product-demo",
        );
    });
});
