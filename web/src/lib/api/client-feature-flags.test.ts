import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("feature flags api client", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("loads the curriculum examiner flag", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                curriculum: { examiner: false },
            }),
        });

        const result = await api.featureFlags.get();

        expect(result.curriculum.examiner).toBe(false);
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/feature-flags"),
            expect.any(Object),
        );
    });
});
