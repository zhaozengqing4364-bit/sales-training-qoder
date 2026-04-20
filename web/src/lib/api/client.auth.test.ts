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

    it("adds csrf header for cookie-backed unsafe requests when the csrf cookie is present", async () => {
        document.cookie = "app_csrf=csrf-token-123; path=/";
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    success: true,
                    data: { message: "ok" },
                }),
                {
                    status: 200,
                    headers: { "Content-Type": "application/json" },
                },
            ),
        );

        vi.stubGlobal("fetch", fetchMock);

        await api.auth.logout();

        const requestOptions = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
        const headers = new Headers(requestOptions?.headers);
        expect(headers.get("X-CSRF-Token")).toBe("csrf-token-123");
    });

    it("previews admin TTS through the shared API client with CSRF protection", async () => {
        document.cookie = "app_csrf=tts-csrf-token; path=/";
        const audioBlob = new Blob(["mp3"], { type: "audio/mpeg" });
        const fetchMock = vi.fn().mockResolvedValue(
            new Response(audioBlob, {
                status: 200,
                headers: { "Content-Type": "audio/mpeg" },
            }),
        );

        vi.stubGlobal("fetch", fetchMock);

        const result = await api.admin.previewTTSBlob({
            text: "试听统一客户端",
            voice: "zh-CN-XiaoxiaoNeural",
            rate: "+10%",
            volume: "+5%",
            pitch: "+2Hz",
        });

        expect(result.type).toBe("audio/mpeg");
        expect(result.size).toBeGreaterThan(0);
        expect(fetchMock).toHaveBeenCalledTimes(1);

        const [url, requestOptions] = fetchMock.mock.calls[0] as [string, RequestInit];
        const parsed = new URL(url);
        const headers = new Headers(requestOptions.headers);

        expect(parsed.pathname).toBe("/api/v1/admin/model-configs/tts/preview");
        expect(parsed.searchParams.get("text")).toBe("试听统一客户端");
        expect(parsed.searchParams.get("voice")).toBe("zh-CN-XiaoxiaoNeural");
        expect(parsed.searchParams.get("rate")).toBe("+10%");
        expect(parsed.searchParams.get("volume")).toBe("+5%");
        expect(parsed.searchParams.get("pitch")).toBe("+2Hz");
        expect(requestOptions).toMatchObject({
            method: "POST",
            credentials: "include",
        });
        expect(headers.get("X-CSRF-Token")).toBe("tts-csrf-token");
    });

    it("normalizes admin TTS preview failures into Chinese ApiRequestError text", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({
                        success: false,
                        error: "[TTS_PREVIEW_FAILED]",
                        message: "upstream timeout",
                        trace_id: "trace-tts-1",
                    }),
                    {
                        status: 502,
                        headers: { "Content-Type": "application/json" },
                    },
                ),
            ),
        );

        await expect(
            api.admin.previewTTSBlob({ text: "失败试听" }),
        ).rejects.toMatchObject({
            name: "ApiRequestError",
            status: 502,
            errorCode: "[TTS_PREVIEW_FAILED]",
            message: "语音试听失败，请稍后重试。 (trace_id: trace-tts-1)",
            rawMessage: "upstream timeout",
            traceId: "trace-tts-1",
        });
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

    it("normalizes structured segment playback errors into ApiRequestError", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({
                        error_code: "SEGMENT_NOT_UPLOADED",
                        message: "segment is not uploaded yet",
                        trace_id: "trace-segment-1",
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
            name: "ApiRequestError",
            status: 409,
            errorCode: "SEGMENT_NOT_UPLOADED",
            rawMessage: "segment is not uploaded yet",
            traceId: "trace-segment-1",
        });
    });

    it("normalizes validation-array payloads into a stable ApiRequestError", async () => {
        mockFetchResponse(422, {
            detail: [
                {
                    type: "missing",
                    loc: ["body", "email"],
                    msg: "Field required",
                },
            ],
        });

        await expect(
            api.auth.login({ email: "", password: "password" }),
        ).rejects.toMatchObject({
            name: "ApiRequestError",
            status: 422,
            errorCode: "[REQUEST_VALIDATION_ERROR]",
            rawMessage: "Field required",
        });
    });

    it("normalizes dependency detail payloads for admin-only endpoints", async () => {
        mockFetchResponse(403, {
            detail: {
                error: "[ROLE_REQUIRED]",
                message: "当前账号权限不足，无法执行该操作。",
            },
        });

        await expect(api.admin.getKnowledgeBases()).rejects.toMatchObject({
            name: "ApiRequestError",
            status: 403,
            errorCode: "[ROLE_REQUIRED]",
            rawMessage: "当前账号权限不足，无法执行该操作。",
        });
    });

    it("normalizes top-level voice runtime profile errors into ApiRequestError", async () => {
        mockFetchResponse(404, {
            success: false,
            error: "[VOICE_RUNTIME_PROFILE_NOT_FOUND]",
            message: "运行时配置不存在。",
            trace_id: "trace-runtime-1",
        });

        await expect(
            api.admin.updateVoiceRuntimeProfile("profile-missing", { name: "新名称" }),
        ).rejects.toMatchObject({
            name: "ApiRequestError",
            status: 404,
            errorCode: "[VOICE_RUNTIME_PROFILE_NOT_FOUND]",
            rawMessage: "运行时配置不存在。",
            traceId: "trace-runtime-1",
        });
    });

    it("normalizes top-level evaluation report errors into ApiRequestError", async () => {
        mockFetchResponse(404, {
            success: false,
            error: "[REPORT_NOT_FOUND]",
            message: "报告不存在。",
            trace_id: "trace-report-1",
        });

        await expect(api.admin.getComprehensiveReport("session-1")).rejects.toMatchObject({
            name: "ApiRequestError",
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            rawMessage: "报告不存在。",
            traceId: "trace-report-1",
        });
    });
});
