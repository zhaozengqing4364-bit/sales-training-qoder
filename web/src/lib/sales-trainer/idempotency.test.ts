import { describe, expect, it } from "vitest";

import { generateClientToken } from "./idempotency";

describe("generateClientToken", () => {
    it("returns a non-empty string", () => {
        const token = generateClientToken();
        expect(typeof token).toBe("string");
        expect(token.length).toBeGreaterThan(0);
    });

    it("generates unique tokens across calls", () => {
        const tokens = new Set<string>();
        for (let i = 0; i < 100; i++) {
            tokens.add(generateClientToken());
        }
        // 100 次调用应全部唯一
        expect(tokens.size).toBe(100);
    });

    it("produces uuid-like format when crypto.randomUUID is available", () => {
        // 现代测试环境（jsdom/node）通常支持 crypto.randomUUID
        const token = generateClientToken();
        expect(token).toMatch(
            /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
        );
    });
});
