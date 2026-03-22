import { afterEach, describe, expect, it, vi } from "vitest";

import {
    buildTraceHeaders,
    createTraceContext,
    extractTraceIdFromTraceparent,
} from "./trace-context";

describe("trace context helpers", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.resetModules();
    });

    it("creates W3C-compatible trace context values", () => {
        const context = createTraceContext();

        expect(context.traceId).toMatch(/^[a-f0-9]{32}$/);
        expect(context.spanId).toMatch(/^[a-f0-9]{16}$/);
        expect(context.traceparent).toMatch(
            /^00-[a-f0-9]{32}-[a-f0-9]{16}-01$/,
        );
    });

    it("reuses a valid upstream traceparent trace id", () => {
        const upstreamTraceparent =
            "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01";

        const headers = buildTraceHeaders({ traceparent: upstreamTraceparent });

        expect(headers["X-Trace-ID"]).toBe(
            "4bf92f3577b34da6a3ce929d0e0e4736",
        );
        expect(extractTraceIdFromTraceparent(headers.traceparent)).toBe(
            "4bf92f3577b34da6a3ce929d0e0e4736",
        );
    });

    it("does not reuse a process-global trace id across separate server-side requests", async () => {
        vi.resetModules();
        vi.stubGlobal("window", undefined);

        const { buildTraceHeaders: buildServerTraceHeaders } = await import("./trace-context");
        const first = buildServerTraceHeaders();
        const second = buildServerTraceHeaders();

        expect(first["X-Trace-ID"]).not.toBe(second["X-Trace-ID"]);
        expect(first.traceparent).not.toBe(second.traceparent);
    });
});
