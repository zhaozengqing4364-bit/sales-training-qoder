import { afterEach, describe, expect, it, vi } from "vitest";

import { generateClientId } from "./client-id";

describe("generateClientId", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    it("generates an RFC 4122 v4 identifier when randomUUID is unavailable", () => {
        vi.stubGlobal("crypto", {
            getRandomValues: (buffer: Uint8Array) => {
                buffer.forEach((_, index) => {
                    buffer[index] = index;
                });
                return buffer;
            },
        });

        expect(generateClientId()).toBe("00010203-0405-4607-8809-0a0b0c0d0e0f");
    });

    it("still returns different identifiers without Web Crypto", () => {
        vi.stubGlobal("crypto", undefined);
        vi.spyOn(Math, "random")
            .mockReturnValueOnce(0.01)
            .mockReturnValueOnce(0.02)
            .mockReturnValue(0.03);

        const first = generateClientId();
        const second = generateClientId();

        expect(first).not.toBe(second);
        expect(first).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    });
});
