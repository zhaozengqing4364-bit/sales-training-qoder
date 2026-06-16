import { describe, expect, it } from "vitest";

import { resolveClientInstrumentationConsoleMethod } from "./instrumentation-client";

describe("client instrumentation console policy", () => {
    it("keeps production unhandled errors durable", () => {
        expect(resolveClientInstrumentationConsoleMethod("production")).toBe("error");
    });

    it("avoids Next.js dev overlay for global browser noise in development", () => {
        expect(resolveClientInstrumentationConsoleMethod("development")).toBe("warn");
        expect(resolveClientInstrumentationConsoleMethod("test")).toBe("warn");
        expect(resolveClientInstrumentationConsoleMethod(undefined)).toBe("warn");
    });
});
