import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { postTelemetryEvent, resolveTelemetryUrl, trackCustomMetric } from "./performance";

describe("performance telemetry dispatch", () => {
    const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

    beforeEach(() => {
        process.env.NEXT_PUBLIC_API_URL = "http://localhost:3444/api/v1";
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 202 }));
    });

    afterEach(() => {
        process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
        vi.restoreAllMocks();
    });

    it("resolves telemetry routes against the configured backend api base", () => {
        expect(resolveTelemetryUrl("performance")).toBe(
            "http://localhost:3444/api/v1/analytics/performance",
        );
        expect(resolveTelemetryUrl("custom")).toBe(
            "http://localhost:3444/api/v1/analytics/custom",
        );
    });

    it("falls back to fetch against the backend api base when beacon delivery is unavailable", async () => {
        Object.defineProperty(window.navigator, "sendBeacon", {
            configurable: true,
            value: vi.fn().mockReturnValue(false),
        });

        postTelemetryEvent("custom", JSON.stringify({ metric: true }));

        await vi.waitFor(() => {
            expect(fetch).toHaveBeenCalledWith(
                "http://localhost:3444/api/v1/analytics/custom",
                expect.objectContaining({
                    method: "POST",
                    keepalive: true,
                    headers: expect.objectContaining({
                        "Content-Type": "application/json",
                    }),
                }),
            );
        });
    });

    it("routes custom metrics through the backend api authority instead of same-origin next routes", () => {
        const sendBeaconMock = vi.fn().mockReturnValue(true);

        Object.defineProperty(window.navigator, "sendBeacon", {
            configurable: true,
            value: sendBeaconMock,
        });

        trackCustomMetric("page_load", 123);

        expect(sendBeaconMock).toHaveBeenCalledWith(
            "http://localhost:3444/api/v1/analytics/custom",
            expect.any(Blob),
        );
    });
});
