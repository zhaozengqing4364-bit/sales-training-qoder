import { beforeEach, describe, expect, it, vi } from "vitest";

import { authHandler } from "./auth-handler";

describe("authHandler", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it("notifies listeners and schedules redirect when session expires", () => {
        const listener = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);
        const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");
        vi.spyOn(window, "setTimeout");

        authHandler.sessionExpired();

        expect(removeItemSpy).not.toHaveBeenCalled();
        expect(listener).toHaveBeenCalledWith("登录已过期，请重新登录");
        expect(setTimeout).toHaveBeenCalledWith(expect.any(Function), 1500);

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

    it("supports silent logout without emitting toast event or clearing local storage", () => {
        const listener = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);
        const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");

        authHandler.logout("silent", { notify: false });

        expect(removeItemSpy).not.toHaveBeenCalled();
        expect(listener).not.toHaveBeenCalled();

        unsubscribe();
    });
});
