import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError, api, resolveApiBaseUrl } from "./client";
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

    it("delegates each authenticated 401 to the auth handler without a client-side cooldown", async () => {
        const sessionExpiredSpy = vi.spyOn(authHandler, "sessionExpired").mockImplementation(() => {});

        mockFetchResponse(401, {
            success: false,
            error: "[INVALID_TOKEN]",
            message: "invalid token",
        });

        await expect(api.user.getMe()).rejects.toBeInstanceOf(ApiRequestError);
        await expect(api.user.getMe()).rejects.toBeInstanceOf(ApiRequestError);

        expect(sessionExpiredSpy).toHaveBeenCalledTimes(2);
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

    it("normalizes admin TTS preview blob body read failures through the shared API client", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue({
                ok: true,
                status: 200,
                blob: () => Promise.reject(new TypeError("body stream failed")),
            }),
        );

        await expect(
            api.admin.previewTTSBlob({ text: "读取失败试听" }),
        ).rejects.toMatchObject({
            name: "ApiRequestError",
            status: 0,
            errorCode: "[NETWORK_ERROR]",
            rawMessage: "body stream failed",
        });
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

    it("password login request aborts after configured timeout", async () => {
        vi.useFakeTimers();
        try {
            const fetchMock = vi.fn(
                (_url: RequestInfo | URL, init?: RequestInit) => new Promise((_resolve, reject) => {
                    init?.signal?.addEventListener("abort", () => {
                        reject(new DOMException("The operation was aborted.", "AbortError"));
                    });
                }),
            );
            vi.stubGlobal("fetch", fetchMock);

            const request = api.auth.login({ email: "admin@qoder.ai", password: "password" });
            const rejection = expect(request).rejects.toMatchObject({
                name: "ApiRequestError",
                status: 0,
                errorCode: "[REQUEST_TIMEOUT]",
                message: "登录超时，请重试。",
            });
            await vi.advanceTimersByTimeAsync(8000);

            const requestSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal | undefined;
            expect(requestSignal?.aborted).toBe(true);
            await rejection;
        } finally {
            vi.useRealTimers();
        }
    });

    it("password login request aborts when JSON body read stalls past the configured timeout", async () => {
        vi.useFakeTimers();
        try {
            const fetchMock = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => Promise.resolve({
                ok: true,
                status: 200,
                json: () => new Promise((_resolve, reject) => {
                    init?.signal?.addEventListener("abort", () => {
                        reject(new DOMException("The operation was aborted.", "AbortError"));
                    });
                }),
            }));
            vi.stubGlobal("fetch", fetchMock);

            const request = api.auth.login({ email: "admin@qoder.ai", password: "password" });
            const rejection = expect(request).rejects.toMatchObject({
                name: "ApiRequestError",
                status: 0,
                errorCode: "[REQUEST_TIMEOUT]",
                message: "登录超时，请重试。",
            });
            await vi.advanceTimersByTimeAsync(8000);

            const requestSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal | undefined;
            expect(requestSignal?.aborted).toBe(true);
            await rejection;
        } finally {
            vi.useRealTimers();
        }
    });

    it("current-user request aborts after configured timeout", async () => {
        vi.useFakeTimers();
        try {
            const fetchMock = vi.fn(
                (_url: RequestInfo | URL, init?: RequestInit) => new Promise((_resolve, reject) => {
                    init?.signal?.addEventListener("abort", () => {
                        reject(new DOMException("The operation was aborted.", "AbortError"));
                    });
                }),
            );
            vi.stubGlobal("fetch", fetchMock);

            const request = api.user.getMe();
            const rejection = expect(request).rejects.toMatchObject({
                name: "ApiRequestError",
                status: 0,
                errorCode: "[REQUEST_TIMEOUT]",
            });
            await vi.advanceTimersByTimeAsync(8000);

            const requestSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal | undefined;
            expect(requestSignal?.aborted).toBe(true);
            await rejection;
        } finally {
            vi.useRealTimers();
        }
    });

    it("dashboard stats request aborts after configured timeout with section fallback copy", async () => {
        vi.useFakeTimers();
        try {
            const fetchMock = vi.fn(
                (_url: RequestInfo | URL, init?: RequestInit) => new Promise((_resolve, reject) => {
                    init?.signal?.addEventListener("abort", () => {
                        reject(new DOMException("The operation was aborted.", "AbortError"));
                    });
                }),
            );
            vi.stubGlobal("fetch", fetchMock);

            const request = api.dashboard.getStats();
            const rejection = expect(request).rejects.toMatchObject({
                name: "ApiRequestError",
                status: 0,
                errorCode: "[REQUEST_TIMEOUT]",
                message: "训练统计加载较慢，请稍后刷新。",
            });
            await vi.advanceTimersByTimeAsync(8000);

            const requestSignal = fetchMock.mock.calls[0]?.[1]?.signal as AbortSignal | undefined;
            expect(requestSignal?.aborted).toBe(true);
            await rejection;
        } finally {
            vi.useRealTimers();
        }
    });

    it("aligns loopback API host with the current page host so dev-login cookies survive on 127.0.0.1", () => {
        vi.stubGlobal("window", {
            location: {
                hostname: "127.0.0.1",
            },
        });

        expect(resolveApiBaseUrl()).toBe("http://127.0.0.1:3444/api/v1");
    });

    it("does not retry cookie-backed login request against another loopback host", async () => {
        const fetchMock = vi
            .fn()
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce(new Response(JSON.stringify({ success: true }), { status: 200 }));
        const sessionExpiredSpy = vi.spyOn(authHandler, "sessionExpired").mockImplementation(() => {});

        vi.stubGlobal("fetch", fetchMock);

        await expect(
            api.auth.login({ email: "admin@test.com", password: "password" }),
        ).rejects.toMatchObject({
            name: "ApiRequestError",
            errorCode: "[NETWORK_ERROR]",
        });

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: "include" });
        expect(sessionExpiredSpy).not.toHaveBeenCalled();
    });

    it("does not retry cookie-backed authenticated requests against another loopback host", async () => {
        const fetchMock = vi
            .fn()
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce(
                new Response(
                    JSON.stringify({
                        success: false,
                        error: "[AUTHENTICATION_REQUIRED]",
                        message: "missing cookie on fallback host",
                    }),
                    { status: 401, headers: { "Content-Type": "application/json" } },
                ),
            );
        const sessionExpiredSpy = vi.spyOn(authHandler, "sessionExpired").mockImplementation(() => {});

        vi.stubGlobal("fetch", fetchMock);

        await expect(api.learningPath.getNextTask()).rejects.toMatchObject({
            name: "ApiRequestError",
            errorCode: "[NETWORK_ERROR]",
        });

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ credentials: "include" });
        expect(sessionExpiredSpy).not.toHaveBeenCalled();
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
