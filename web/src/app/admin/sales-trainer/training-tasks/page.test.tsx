import { describe, expect, it, vi } from "vitest";

import LegacyTrainingTasksPage from "./page";

const { redirectMock } = vi.hoisted(() => ({
    redirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    redirect: redirectMock,
}));

describe("LegacyTrainingTasksPage", () => {
    it("redirects the legacy training task list to audio management", () => {
        LegacyTrainingTasksPage();

        expect(redirectMock).toHaveBeenCalledWith("/admin/sales-trainer/audio");
    });
});
