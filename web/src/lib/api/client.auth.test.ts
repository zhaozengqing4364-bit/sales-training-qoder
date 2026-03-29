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
    });

    it("triggers session-expired flow for authenticated endpoints on 401", async () => {
        const sessionExpiredSpy = vi.spyOn(authHandler, "sessionExpired").mockImplementation(() => {});

        mockFetchResponse(401, {
            success: false,
            error: "[INVALID_TOKEN]",
            message: "invalid token",
        });

        await expect(api.user.getMe()).rejects.toBeInstanceOf(ApiRequestError);
        expect(sessionExpiredSpy).toHaveBeenCalledTimes(1);
    });

    it("does not trigger session-expired flow for login 401", async () => {
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

    it("sends credentials for cookie-backed session requests", async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    success: true,
                    data: {
                        id: "user-1",
                        display_name: "Admin",
                        email: "admin@test.com",
                        role: "admin",
                    },
                }),
                {
                    status: 200,
                    headers: { "Content-Type": "application/json" },
                },
            ),
        );

        vi.stubGlobal("fetch", fetchMock);

        await api.user.getMe();

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/api/v1/users/me"),
            expect.objectContaining({
                credentials: "include",
            }),
        );
    });

    it("attaches W3C trace context headers to API requests", async () => {
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    success: true,
                    data: {
                        id: "user-1",
                        display_name: "Admin",
                        email: "admin@test.com",
                        role: "admin",
                    },
                }),
                {
                    status: 200,
                    headers: { "Content-Type": "application/json" },
                },
            ),
        );

        vi.stubGlobal("fetch", fetchMock);

        await api.user.getMe();

        const requestOptions = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
        const headers = new Headers(requestOptions?.headers);
        const traceId = headers.get("X-Trace-ID");
        const traceparent = headers.get("traceparent");

        expect(typeof traceId).toBe("string");
        expect(typeof traceparent).toBe("string");
        expect(traceId).toMatch(/^[a-f0-9]{32}$/);
        expect(traceparent).toMatch(
            new RegExp(`^00-${traceId}-[a-f0-9]{16}-01$`),
        );
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
        expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: "include" });
        expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ credentials: "include" });

        const firstUrl = String(fetchMock.mock.calls[0]?.[0] ?? "");
        const secondUrl = String(fetchMock.mock.calls[1]?.[0] ?? "");

        expect(firstUrl).toContain("/api/v1/auth/login");
        expect(secondUrl).toContain("/api/v1/auth/login");
        expect(secondUrl).not.toBe(firstUrl);
    });

    it("preserves structured segment playback error codes from JSON error responses", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({
                        error_code: "SEGMENT_NOT_UPLOADED",
                        message: "segment is not uploaded yet",
                    }),
                    {
                        status: 409,
                        headers: { "Content-Type": "application/json" },
                    },
                ),
            ),
        );

        await expect(
            api.sessions.getSegmentAudioBlobUrl("session-1", 3),
        ).rejects.toMatchObject({
            message: "SEGMENT_NOT_UPLOADED",
        });
    });
});
