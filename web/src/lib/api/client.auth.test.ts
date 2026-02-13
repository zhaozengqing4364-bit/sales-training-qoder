import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError, api } from "./client";
import { authHandler } from "@/lib/auth-handler";

function mockFetchResponse(status: number, payload: unknown) {
    vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
            ok: status >= 200 && status < 300,
            status,
            json: vi.fn().mockResolvedValue(payload),
        } as Response),
    );
}

describe("API client 401 handling", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        localStorage.clear();
    });

    it("triggers session-expired flow when token exists", async () => {
        localStorage.setItem("token", "expired-token");
        const sessionExpiredSpy = vi.spyOn(authHandler, "sessionExpired").mockImplementation(() => {});

        mockFetchResponse(401, {
            success: false,
            error: "[INVALID_TOKEN]",
            message: "invalid token",
        });

        await expect(api.user.getMe()).rejects.toBeInstanceOf(ApiRequestError);
        expect(sessionExpiredSpy).toHaveBeenCalledTimes(1);
    });

    it("does not trigger session-expired flow for login 401 without token", async () => {
        const sessionExpiredSpy = vi.spyOn(authHandler, "sessionExpired").mockImplementation(() => {});

        mockFetchResponse(401, {
            success: false,
            error: "[INVALID_CREDENTIALS]",
            message: "账号或凭证无效",
        });

        await expect(
            api.auth.login({ email: "admin@qoder.ai", password: "wrong-password" }),
        ).rejects.toBeInstanceOf(ApiRequestError);
        expect(sessionExpiredSpy).not.toHaveBeenCalled();
    });
});
