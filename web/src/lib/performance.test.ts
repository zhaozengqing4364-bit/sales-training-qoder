import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { postTelemetryEvent, resolveTelemetryUrl, trackCustomMetric } from "./performance";

describe("performance telemetry dispatch", () => {
    const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

    beforeEach(() => {
        process.env.NEXT_PUBLIC_API_URL = "http://localhost:3444/api/v1";
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 202 }));
    });

    afterEach(() => {
        document.cookie = "app_csrf=; Max-Age=0; path=/";
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

        await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
        const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
        expect(url).toBe("http://localhost:3444/api/v1/analytics/custom");
        expect(options).toEqual(expect.objectContaining({ method: "POST", keepalive: true }));
        expect(new Headers(options?.headers).get("Content-Type")).toBe("application/json");
    });

    it("uses credential-omitting fetch for a cross-origin telemetry authority", async () => {
        const sendBeaconMock = vi.fn().mockReturnValue(true);

        Object.defineProperty(window.navigator, "sendBeacon", {
            configurable: true,
            value: sendBeaconMock,
        });

        trackCustomMetric("page_load", 123);

        await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
        expect(sendBeaconMock).not.toHaveBeenCalled();
        const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
        expect(url).toBe("http://localhost:3444/api/v1/analytics/custom");
        expect(options?.credentials).toBe("same-origin");
    });

    it("uses a CSRF-protected keepalive request for same-origin cookie sessions", async () => {
        process.env.NEXT_PUBLIC_API_URL = `${window.location.origin}/api/v1`;
        document.cookie = "app_csrf=csrf-telemetry; path=/";
        const sendBeaconMock = vi.fn().mockReturnValue(true);
        Object.defineProperty(window.navigator, "sendBeacon", {
            configurable: true,
            value: sendBeaconMock,
        });

        postTelemetryEvent("custom", JSON.stringify({ metric: true }));

        await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
        expect(sendBeaconMock).not.toHaveBeenCalled();
        const [url, options] = vi.mocked(fetch).mock.calls[0] ?? [];
        expect(url).toBe(`${window.location.origin}/api/v1/analytics/custom`);
        expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("csrf-telemetry");
        expect(options?.credentials).toBe("same-origin");
    });
});
