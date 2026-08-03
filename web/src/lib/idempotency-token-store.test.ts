import { describe, expect, it, vi } from "vitest";

vi.mock("./client-id", () => ({
    generateClientId: vi
        .fn()
        .mockReturnValueOnce("token-1")
        .mockReturnValueOnce("token-2")
        .mockReturnValueOnce("token-3"),
}));

import { createIdempotencyTokenStore } from "./idempotency-token-store";

describe("createIdempotencyTokenStore", () => {
    it("reuses a token after an uncertain failure and rotates on changed input or success", () => {
        sessionStorage.clear();
        const store = createIdempotencyTokenStore();

        expect(store.tokenFor("same-input")).toBe("token-1");
        expect(store.tokenFor("same-input")).toBe("token-1");
        expect(createIdempotencyTokenStore().tokenFor("same-input")).toBe("token-1");
        expect(store.tokenFor("changed-input")).toBe("token-2");
        expect(store.tokenFor("same-input")).toBe("token-1");

        store.complete("changed-input");
        expect(store.tokenFor("changed-input")).toBe("token-3");
        sessionStorage.clear();
    });
});
