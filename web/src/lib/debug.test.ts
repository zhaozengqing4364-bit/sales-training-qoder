import { describe, expect, it, vi } from "vitest";

import { debug } from "./debug";

describe("debug durable error seam", () => {
    it("reports durable errors through the shared seam even when dev debug is disabled", () => {
        const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
        const durableError = (debug as typeof debug & {
            durableError?: (scope: string, error: unknown, context?: Record<string, unknown>) => void;
        }).durableError;

        expect(typeof durableError).toBe("function");

        durableError?.("route-error.dashboard", new Error("boom"), {
            digest: "digest-1",
            route: "/dashboard",
        });

        expect(errorSpy).toHaveBeenCalledWith(
            "[route-error.dashboard]",
            expect.any(Error),
            expect.objectContaining({
                digest: "digest-1",
                route: "/dashboard",
            }),
        );
    });
});
