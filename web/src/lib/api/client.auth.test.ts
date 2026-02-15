import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError, api } from "./client";
import { authHandler } from "@/lib/auth-handler";

function mockFetchResponse(status: number, payload: unknown) {
    vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
            new Response(JSON.stringify(payload), {
                status,
                headers: { "Content-Type": "application/json" },
            }),
        ),
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

    it("normalizes network failures during login", async () => {
        vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

        await expect(
            api.auth.login({ email: "admin@qoder.ai", password: "password" }),
        ).rejects.toMatchObject({
            name: "ApiRequestError",
            errorCode: "[NETWORK_ERROR]",
        });
    });

    it("retries login request with loopback hostname fallback", async () => {
        const fetchMock = vi
            .fn()
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce(
                new Response(
                    JSON.stringify({
                        success: true,
                        data: {
                            token: "token-1",
                            user: {
                                id: "user-1",
                                name: "Admin",
                                email: "admin@test.com",
                                role: "admin",
                            },
                        },
                    }),
                    {
                        status: 200,
                        headers: { "Content-Type": "application/json" },
                    },
                ),
            );

        vi.stubGlobal("fetch", fetchMock);

        const result = await api.auth.login({ email: "admin@test.com", password: "password" });

        expect(result.token).toBe("token-1");
        expect(fetchMock).toHaveBeenCalledTimes(2);

        const firstUrl = String(fetchMock.mock.calls[0]?.[0] ?? "");
        const secondUrl = String(fetchMock.mock.calls[1]?.[0] ?? "");

        expect(firstUrl).toContain("/api/v1/auth/login");
        expect(secondUrl).toContain("/api/v1/auth/login");
        expect(secondUrl).not.toBe(firstUrl);
    });
});
