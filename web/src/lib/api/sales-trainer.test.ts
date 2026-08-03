import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";
import {
    NEWCOMER_COMPLETION_RULE_COMPATIBILITY,
    type NewcomerPathCompletionRule,
    type NewcomerTrainingCanonicalCompletionRule,
    type NewcomerTrainingCompletionRule,
} from "./types";

const fetchMock = vi.fn();

describe("api.salesTrainer facade", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("pins canonical and historical completion-rule wire values", () => {
        const historical = [
            "passed",
            "scored",
            "submitted",
        ] as const satisfies readonly NewcomerPathCompletionRule[];
        const canonical = [
            "audio_scored",
            "paper_passed",
            "all_audio_options_scored",
            "placeholder_disabled",
        ] as const satisfies readonly NewcomerTrainingCanonicalCompletionRule[];
        const allRules = [
            ...historical,
            ...canonical,
        ] satisfies readonly NewcomerTrainingCompletionRule[];

        expect(allRules).toContain("paper_passed");
        expect(NEWCOMER_COMPLETION_RULE_COMPATIBILITY).toEqual({
            audio_scored: "scored",
            paper_passed: "passed",
            all_audio_options_scored: "scored",
            placeholder_disabled: "submitted",
        });
    });

    it("keeps independent sales-practice learner reads on their own surface", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: { items: [{ unit_id: "unit-1" }], total: 1 },
            }),
        });

        const result = await api.salesTrainer.listUnits();

        expect(result.items[0].unit_id).toBe("unit-1");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/sales-trainer/units"),
            expect.any(Object),
        );
    });

    it("keeps independent learner audio history read-only", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({ success: true, data: { items: [], total: 0 } }),
        });

        const result = await api.salesTrainer.listMyAudioSubmissions({
            limit: 20,
            offset: 0,
        });

        expect(result.total).toBe(0);
        expect(api.salesTrainer.getAudioSubmissionFileUrl("submission-1")).toContain(
            "/sales-trainer/audio-submissions/submission-1/file",
        );
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining(
                "/sales-trainer/audio-submissions?limit=20&offset=0",
            ),
            expect.any(Object),
        );
    });
});
