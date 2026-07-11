import { beforeEach, describe, expect, it, vi } from "vitest";

const { redirectMock } = vi.hoisted(() => ({
    redirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    redirect: redirectMock,
}));

import BusinessSkillsExamPage from "./page";

describe("BusinessSkillsExamPage compatibility entry", () => {
    beforeEach(() => {
        redirectMock.mockReset();
    });

    it("converges the retired standalone exam route into the governed in-flow workbench", () => {
        BusinessSkillsExamPage();

        expect(redirectMock).toHaveBeenCalledTimes(1);
        expect(redirectMock).toHaveBeenCalledWith("/sales-trainer/business-skills");
    });
});
