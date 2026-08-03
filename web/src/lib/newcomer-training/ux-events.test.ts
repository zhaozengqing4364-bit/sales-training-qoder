import { beforeEach, describe, expect, it, vi } from "vitest";

import { trackFoundationUxEvent } from "./ux-events";

const trackCustomMetric = vi.hoisted(() => vi.fn());

vi.mock("@/lib/performance", () => ({ trackCustomMetric }));

describe("trackFoundationUxEvent", () => {
    beforeEach(() => trackCustomMetric.mockReset());

    it("emits only a fixed event name and numeric counter", () => {
        trackFoundationUxEvent("activity_started", "audio_assessment");

        expect(trackCustomMetric).toHaveBeenCalledWith(
            "newcomer_foundation.activity_started.audio_assessment",
            1,
        );
        expect(trackCustomMetric.mock.calls[0]).toHaveLength(2);
    });
});
