import { beforeEach, describe, expect, it, vi } from "vitest";

import { authHandler } from "./auth-handler";

describe("authHandler", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
    });

    it("clears local session when session expires", () => {
        localStorage.setItem("token", "token-value");
        localStorage.setItem("user", JSON.stringify({ id: "user-1" }));

        const listener = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);

        authHandler.sessionExpired();

        expect(localStorage.getItem("token")).toBeNull();
        expect(localStorage.getItem("user")).toBeNull();
        expect(listener).toHaveBeenCalledWith("登录已过期，请重新登录");

        unsubscribe();
    });

    it("deduplicates repeated auth notifications within cooldown window", () => {
        const listener = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);

        authHandler.unauthorized();
        authHandler.unauthorized();

        expect(listener).toHaveBeenCalledTimes(1);
        unsubscribe();
    });

    it("supports silent logout without emitting toast event", () => {
        localStorage.setItem("token", "token-value");
        localStorage.setItem("user", JSON.stringify({ id: "user-1" }));

        const listener = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);

        authHandler.logout("silent", { notify: false });

        expect(localStorage.getItem("token")).toBeNull();
        expect(localStorage.getItem("user")).toBeNull();
        expect(listener).not.toHaveBeenCalled();

        unsubscribe();
    });
});
