import { describe, expect, it, vi } from "vitest";

import { createAuthDomain, createPracticeDomain } from "./client-domains";

describe("client domain factories", () => {
    it("keeps auth login on the shared request seam with session-expiry handling disabled", async () => {
        const request = vi.fn().mockResolvedValue({ token: "token-1" });
        const auth = createAuthDomain({ request });

        await auth.login({ email: "admin@test.com", password: "secret" });

        expect(request).toHaveBeenCalledWith("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email: "admin@test.com", password: "secret" }),
            skipSessionExpiredHandling: true,
        });
    });

    it("keeps practice lifecycle helpers delegating through the domain lifecycle endpoint", async () => {
        const request = vi.fn().mockResolvedValue({ ok: true });
        const practice = createPracticeDomain({ request });

        await practice.startSession("session-1");
        await practice.pauseSession("session-1");
        await practice.resumeSession("session-1");
        await practice.endSession("session-1");

        expect(request).toHaveBeenNthCalledWith(1, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "start" }),
        });
        expect(request).toHaveBeenNthCalledWith(2, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "pause" }),
        });
        expect(request).toHaveBeenNthCalledWith(3, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "resume" }),
        });
        expect(request).toHaveBeenNthCalledWith(4, "/practice/sessions/session-1/lifecycle", {
            method: "POST",
            body: JSON.stringify({ action: "end" }),
        });
    });
});
