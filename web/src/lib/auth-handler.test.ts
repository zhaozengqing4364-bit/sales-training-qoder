import { beforeEach, describe, expect, it, vi } from "vitest";

import { authHandler, interruptiveUiInventory } from "./auth-handler";

describe("authHandler", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it("notifies listeners and schedules a router-aware redirect when session expires", () => {
        vi.useFakeTimers();
        const listener = vi.fn();
        const navigateMock = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);
        const unregisterNavigator = authHandler.setNavigator(navigateMock);
        const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");

        authHandler.sessionExpired();

        expect(removeItemSpy).not.toHaveBeenCalled();
        expect(listener).toHaveBeenCalledWith("登录已过期，请重新登录");
        expect(navigateMock).not.toHaveBeenCalled();

        vi.advanceTimersByTime(1500);

        expect(navigateMock).toHaveBeenCalledWith("/login", { mode: "replace" });

        unregisterNavigator();
        unsubscribe();
        vi.useRealTimers();
    });

    it("holds the auth redirect on the shared seam until the router bridge is available", () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date(Date.now() + 2_000));
        const listener = vi.fn();
        const navigateMock = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);

        authHandler.sessionExpired();

        expect(listener).toHaveBeenCalledWith("登录已过期，请重新登录");

        vi.advanceTimersByTime(1500);

        expect(navigateMock).not.toHaveBeenCalled();

        const unregisterNavigator = authHandler.setNavigator(navigateMock);

        expect(navigateMock).toHaveBeenCalledWith("/login", { mode: "replace" });

        unregisterNavigator();
        unsubscribe();
        vi.useRealTimers();
    });

    it("queues logout redirects onto the registered navigator instead of hard browser jumps", () => {
        const navigateMock = vi.fn();
        const unregisterNavigator = authHandler.setNavigator(navigateMock);

        authHandler.logout("已退出登录", { redirectTo: "/login", notify: false, navigationMode: "push" });

        expect(navigateMock).toHaveBeenCalledWith("/login", { mode: "push" });
        unregisterNavigator();
    });

    it("deduplicates repeated auth notifications within cooldown window", () => {
        const listener = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);

        authHandler.unauthorized();
        authHandler.unauthorized();

        expect(listener).toHaveBeenCalledTimes(1);
        unsubscribe();
    });

    it("coalesces repeated session-expired calls while the login redirect is pending", () => {
        vi.useFakeTimers();
        const listener = vi.fn();
        const navigateMock = vi.fn();
        const unsubscribe = authHandler.subscribe(listener);
        const unregisterNavigator = authHandler.setNavigator(navigateMock);

        authHandler.sessionExpired();
        vi.advanceTimersByTime(1300);
        authHandler.sessionExpired();

        expect(listener).toHaveBeenCalledTimes(1);
        expect(navigateMock).not.toHaveBeenCalled();

        vi.advanceTimersByTime(200);

        expect(navigateMock).toHaveBeenCalledTimes(1);
        expect(navigateMock).toHaveBeenCalledWith("/login", { mode: "replace" });

        unregisterNavigator();
        unsubscribe();
        vi.useRealTimers();
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

    it("tracks cleaned-up interruptive UI seams and the remaining allowed exceptions for slice s02", () => {
        expect(
            interruptiveUiInventory.filter((item) => item.status === "cleaned-up").map((item) => item.id),
        ).toEqual(expect.arrayContaining([
            "auth-handler-logout-redirect",
            "dashboard-shell-auth-error",
            "records-delete-confirm",
            "records-delete-failure-alert",
            "rag-profile-delete-confirm",
            "persona-save-failure-alert",
        ]));

        expect(
            interruptiveUiInventory.filter((item) => item.status === "allowed-exception").map((item) => item.id),
        ).toEqual(expect.arrayContaining([
            "admin-error-home-fallback",
            "error-boundary-url-capture",
            "performance-url-capture-navigation-start",
            "performance-url-capture-navigation-complete",
        ]));
    });
});
