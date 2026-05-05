/**
 * useContinuousAudioUploader Hook Tests
 *
 * Tests for the continuous audio uploader hook that captures browser microphone
 * audio via MediaRecorder, splits into ~15s segments, uploads to OSS via
 * presigned URLs, and registers metadata with the backend.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useContinuousAudioUploader } from "./use-continuous-audio-uploader";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetUserMedia = vi.fn();
const mockMediaRecorderStart = vi.fn();
const mockMediaRecorderStop = vi.fn();
const mockMediaRecorderAddEventListener = vi.fn();
const mockMediaRecorderRemoveEventListener = vi.fn();

let ondataavailableHandler: ((event: BlobEvent) => void) | null = null;
let onerrorHandler: ((event: Event) => void) | null = null;

class MockMediaRecorder {
    state: RecordingState = "inactive";
    mimeType: string;

    static isTypeSupported = vi.fn().mockReturnValue(true);

    constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
        this.mimeType = options?.mimeType || "audio/webm";
        ondataavailableHandler = null;
        onerrorHandler = null;
    }

    set ondataavailable(fn: (event: BlobEvent) => void) {
        ondataavailableHandler = fn;
    }
    get ondataavailable() {
        return ondataavailableHandler as (event: BlobEvent) => void;
    }

    set onerror(fn: (event: Event) => void) {
        onerrorHandler = fn;
    }

    start = mockMediaRecorderStart.mockImplementation((timeslice?: number) => {
        void timeslice;
        this.state = "recording";
    });

    stop = mockMediaRecorderStop.mockImplementation(() => {
        this.state = "inactive";
    });

    addEventListener = mockMediaRecorderAddEventListener;
    removeEventListener = mockMediaRecorderRemoveEventListener;
}

// Helper to fire ondataavailable from test
function fireDataAvailable(blobSize: number, mimeType = "audio/webm") {
    if (!ondataavailableHandler) throw new Error("No ondataavailable handler");
    const blob = new Blob([new ArrayBuffer(blobSize)], { type: mimeType });
    const event = { data: blob } as BlobEvent;
    ondataavailableHandler(event);
}

function fireMediaRecorderError() {
    if (!onerrorHandler) throw new Error("No onerror handler");
    onerrorHandler(new Event("error"));
}

// Mock fetch for API calls
const mockFetch = vi.fn();
const originalFetch = globalThis.fetch;

function mockFetchResponse(status: number, body: Record<string, unknown>) {
    return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: () => Promise.resolve(body),
    } as Response);
}

function getHeaderValue(headers: HeadersInit | undefined, name: string): string | null {
    if (!headers) return null;
    if (headers instanceof Headers) {
        return headers.get(name);
    }
    if (Array.isArray(headers)) {
        const entry = headers.find(([key]) => key.toLowerCase() === name.toLowerCase());
        return entry?.[1] ?? null;
    }
    const record = headers as Record<string, string>;
    return record[name] ?? record[name.toLowerCase()] ?? null;
}

beforeEach(() => {
    vi.clearAllMocks();

    // Mock navigator.mediaDevices
    Object.defineProperty(globalThis, "navigator", {
        value: {
            mediaDevices: {
                getUserMedia: mockGetUserMedia.mockResolvedValue({
                    getTracks: () => [{ stop: vi.fn() }],
                }),
            },
        },
        writable: true,
        configurable: true,
    });

    // Mock MediaRecorder
    (globalThis as unknown as Record<string, unknown>).MediaRecorder =
        MockMediaRecorder as unknown as Record<string, unknown>;

    // Mock fetch
    globalThis.fetch = mockFetch;

    // Default: signing endpoint returns success
    mockFetch.mockImplementation((url: string | Request) => {
        const urlStr = typeof url === "string" ? url : url.url;

        if (urlStr.includes("/audio-upload-urls")) {
            return mockFetchResponse(200, {
                data: {
                    url: "https://oss.example.com/signed-put",
                    object_key: "audio/session/seg-0.webm",
                    expires_at: "2026-03-29T12:00:00Z",
                },
            });
        }
        if (urlStr.includes("/audio-segments") && urlStr.includes("practice")) {
            return mockFetchResponse(200, {
                data: {
                    id: "seg-uuid",
                    segment_sequence: 0,
                    upload_status: "uploaded",
                },
            });
        }
        // OSS PUT
        if (urlStr.includes("oss.example.com")) {
            return mockFetchResponse(200, {});
        }
        return mockFetchResponse(404, { error: "not found" });
    });
});

afterEach(() => {
    globalThis.fetch = originalFetch;
    ondataavailableHandler = null;
    onerrorHandler = null;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useContinuousAudioUploader", () => {
    const sessionId = "test-session-123";

    it("starts uploading when enabled and startUpload is called", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        expect(result.current.uploadStatus).toBe("idle");

        await act(async () => {
            await result.current.startUpload();
        });

        expect(result.current.isUploading).toBe(true);
        expect(result.current.uploadStatus).toBe("uploading");
        expect(mockGetUserMedia).toHaveBeenCalledTimes(1);
        expect(mockMediaRecorderStart).toHaveBeenCalledWith(15_000);
    });

    it("does not start when enabled is false", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: false }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        expect(result.current.isUploading).toBe(false);
        expect(mockGetUserMedia).not.toHaveBeenCalled();
    });

    it("increments segment sequence through timeslice events", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        // Fire two data-available events
        await act(async () => {
            fireDataAvailable(1024);
        });

        await waitFor(() => {
            expect(result.current.segmentCount).toBe(1);
        });

        await act(async () => {
            fireDataAvailable(2048);
        });

        await waitFor(() => {
            expect(result.current.segmentCount).toBe(2);
        });

        // Verify both segments requested signed URLs
        const signCalls = mockFetch.mock.calls.filter(
            (c) => typeof c[0] === "string" && c[0].includes("/audio-upload-urls"),
        );
        expect(signCalls.length).toBe(2);

        // Verify sequences in request bodies
        expect(JSON.parse(signCalls[0][1].body)).toEqual({
            segment_sequence: 0,
            content_type: "audio/webm",
        });
        expect(JSON.parse(signCalls[1][1].body)).toEqual({
            segment_sequence: 1,
            content_type: "audio/webm",
        });
    });

    it("performs PUT to signed OSS URL for each segment", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(4096);
        });

        await waitFor(() => {
            expect(result.current.segmentCount).toBe(1);
        });

        // Should have: 1) sign URL, 2) OSS PUT, 3) register metadata
        const putCalls = mockFetch.mock.calls.filter(
            (c) =>
                typeof c[0] === "string" &&
                c[0].includes("oss.example.com") &&
                c[1]?.method === "PUT",
        );
        expect(putCalls.length).toBe(1);
        expect(putCalls[0][1].headers["Content-Type"]).toBe("audio/webm");
    });

    it("uses the unified API base and CSRF header for backend segment requests", async () => {
        document.cookie = "app_csrf=csrf-token";

        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(4096);
        });

        await waitFor(() => {
            expect(result.current.segmentCount).toBe(1);
        });

        const signCall = mockFetch.mock.calls.find(
            (c) => typeof c[0] === "string" && c[0].includes("/audio-upload-urls"),
        ) as [string, RequestInit] | undefined;
        const registerCall = mockFetch.mock.calls.find(
            (c) =>
                typeof c[0] === "string" &&
                c[0].includes("/audio-segments") &&
                c[0].includes("practice") &&
                c[1]?.method === "POST",
        ) as [string, RequestInit] | undefined;

        expect(signCall?.[0]).toBe(
            `http://localhost:3444/api/v1/practice/sessions/${sessionId}/audio-upload-urls`,
        );
        expect(getHeaderValue(signCall?.[1].headers, "X-CSRF-Token")).toBe("csrf-token");
        expect(registerCall?.[0]).toBe(
            `http://localhost:3444/api/v1/practice/sessions/${sessionId}/audio-segments`,
        );
        expect(getHeaderValue(registerCall?.[1].headers, "X-CSRF-Token")).toBe("csrf-token");

        document.cookie = "app_csrf=; Max-Age=0";
    });

    it("registers segment metadata after successful OSS upload", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(8192);
        });

        await waitFor(() => {
            expect(result.current.segmentCount).toBe(1);
        });

        const regCalls = mockFetch.mock.calls.filter(
            (c) =>
                typeof c[0] === "string" &&
                c[0].includes("/audio-segments") &&
                c[0].includes("practice") &&
                c[1]?.method === "POST",
        );
        expect(regCalls.length).toBe(1);

        const body = JSON.parse(regCalls[0][1].body);
        expect(body.segment_sequence).toBe(0);
        expect(body.object_key).toBe("audio/session/seg-0.webm");
        expect(body.size_bytes).toBe(8192);
    });

    it("handles upload failure without crashing the recording loop", async () => {
        // Make signing endpoint fail
        mockFetch.mockImplementation((url: string | Request) => {
            const urlStr = typeof url === "string" ? url : url.url;
            if (urlStr.includes("/audio-upload-urls")) {
                return mockFetchResponse(503, {
                    error: "OSS 服务暂不可用",
                });
            }
            return mockFetchResponse(200, {});
        });

        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        // Fire a segment — it should fail gracefully
        await act(async () => {
            fireDataAvailable(1024);
        });

        await waitFor(() => {
            expect(result.current.lastError).toBeTruthy();
        });

        // Hook should still be in uploading state (recording continues)
        expect(result.current.isUploading).toBe(true);
        expect(result.current.uploadStatus).toBe("uploading");
        expect(result.current.lastError).toContain("OSS 服务暂不可用");
        const failureCall = mockFetch.mock.calls.find(
            (c) => typeof c[0] === "string" && c[0].includes("/audio-segments/failure"),
        ) as [string, RequestInit] | undefined;
        expect(JSON.parse(String(failureCall?.[1].body))).toEqual({
            segment_sequence: 0,
            error_token: "signing_failed",
        });

        // Now make it succeed and fire another segment
        mockFetch.mockImplementation((url: string | Request) => {
            const urlStr = typeof url === "string" ? url : url.url;
            if (urlStr.includes("/audio-upload-urls")) {
                return mockFetchResponse(200, {
                    data: {
                        url: "https://oss.example.com/signed-put",
                        object_key: "audio/session/seg-1.webm",
                        expires_at: "2026-03-29T12:00:00Z",
                    },
                });
            }
            if (urlStr.includes("oss.example.com")) {
                return mockFetchResponse(200, {});
            }
            if (urlStr.includes("/audio-segments") && urlStr.includes("practice")) {
                return mockFetchResponse(200, { data: { id: "seg-1" } });
            }
            return mockFetchResponse(404, {});
        });

        await act(async () => {
            fireDataAvailable(2048);
        });

        await waitFor(() => {
            // Second segment succeeds at sequence 1, so count is sequence+1 = 2
            expect(result.current.segmentCount).toBe(2);
        });
    });

    it("handles OSS PUT failure without crashing", async () => {
        mockFetch.mockImplementation((url: string | Request) => {
            const urlStr = typeof url === "string" ? url : url.url;
            if (urlStr.includes("/audio-upload-urls")) {
                return mockFetchResponse(200, {
                    data: {
                        url: "https://oss.example.com/signed-put",
                        object_key: "audio/session/seg-0.webm",
                        expires_at: "2026-03-29T12:00:00Z",
                    },
                });
            }
            if (urlStr.includes("oss.example.com")) {
                return mockFetchResponse(403, {}); // OSS rejects
            }
            return mockFetchResponse(200, {});
        });

        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(1024);
        });

        await waitFor(() => {
            expect(result.current.lastError).toContain("OSS PUT 失败");
        });
        const failureCall = mockFetch.mock.calls.find(
            (c) => typeof c[0] === "string" && c[0].includes("/audio-segments/failure"),
        ) as [string, RequestInit] | undefined;
        expect(JSON.parse(String(failureCall?.[1].body))).toEqual({
            segment_sequence: 0,
            error_token: "oss_put_failed",
        });

        expect(result.current.isUploading).toBe(true);
    });

    it("handles backend 401/403 and surfaces error", async () => {
        mockFetch.mockImplementation((url: string | Request) => {
            const urlStr = typeof url === "string" ? url : url.url;
            if (urlStr.includes("/audio-upload-urls")) {
                return mockFetchResponse(401, {
                    error: "未授权，请先登录",
                });
            }
            return mockFetchResponse(200, {});
        });

        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(512);
        });

        await waitFor(() => {
            expect(result.current.lastError).toContain("未授权");
        });
    });

    it("stopUpload finalizes and cleans up", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        expect(result.current.isUploading).toBe(true);

        await act(async () => {
            await result.current.stopUpload();
        });

        expect(result.current.isUploading).toBe(false);
        expect(result.current.uploadStatus).toBe("stopped");
        expect(mockMediaRecorderStop).toHaveBeenCalled();
    });

    it("flushAndStop waits for pending segment registration before marking evidence complete", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(2048);
        });

        await waitFor(() => {
            expect(result.current.segmentCount).toBe(1);
        });

        let flushResult: Awaited<ReturnType<typeof result.current.flushAndStop>> | null = null;
        await act(async () => {
            flushResult = await result.current.flushAndStop({ timeoutMs: 500 });
        });

        expect(flushResult).toEqual({
            status: "completed",
            pendingUploads: 0,
            error: null,
        });
        expect(result.current.pendingUploads).toBe(0);
        expect(result.current.uploadStatus).toBe("stopped");
    });

    it("flushAndStop returns a timeout outcome when evidence registration is still pending", async () => {
        mockFetch.mockImplementation((url: string | Request) => {
            const urlStr = typeof url === "string" ? url : url.url;
            if (urlStr.includes("/audio-upload-urls")) {
                return new Promise<Response>(() => {
                    // Keep the upload pending so the bounded flush has to time out.
                });
            }
            return mockFetchResponse(200, {});
        });

        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        await act(async () => {
            fireDataAvailable(2048);
        });

        await waitFor(() => {
            expect(result.current.pendingUploads).toBe(1);
        });

        let flushResult: Awaited<ReturnType<typeof result.current.flushAndStop>> | null = null;
        await act(async () => {
            flushResult = await result.current.flushAndStop({ timeoutMs: 1 });
        });

        expect(flushResult).toEqual({
            status: "timed_out",
            pendingUploads: 1,
            error: null,
        });
        expect(result.current.uploadStatus).toBe("stopped");
    });

    it("handles microphone permission denial", async () => {
        mockGetUserMedia.mockRejectedValueOnce(
            new DOMException("Permission denied", "NotAllowedError"),
        );

        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        expect(result.current.isUploading).toBe(false);
        expect(result.current.uploadStatus).toBe("error");
        expect(result.current.lastError).toBeTruthy();
    });

    it("ignores zero-size blobs from ondataavailable", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        // Fire a zero-size blob
        await act(async () => {
            fireDataAvailable(0);
        });

        // Should not trigger any fetch calls for this segment
        const signCalls = mockFetch.mock.calls.filter(
            (c) => typeof c[0] === "string" && c[0].includes("/audio-upload-urls"),
        );
        expect(signCalls.length).toBe(0);
        expect(result.current.segmentCount).toBe(0);
    });

    it("handles MediaRecorder runtime error", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        expect(result.current.uploadStatus).toBe("uploading");

        // Simulate a MediaRecorder error
        act(() => {
            fireMediaRecorderError();
        });

        expect(result.current.lastError).toBe("MediaRecorder 运行错误");
        expect(result.current.uploadStatus).toBe("error");
    });

    it("does not double-start if already uploading", async () => {
        const { result } = renderHook(() =>
            useContinuousAudioUploader({ sessionId, enabled: true }),
        );

        await act(async () => {
            await result.current.startUpload();
        });

        expect(mockGetUserMedia).toHaveBeenCalledTimes(1);

        // Try to start again
        await act(async () => {
            await result.current.startUpload();
        });

        // Should still only be called once
        expect(mockGetUserMedia).toHaveBeenCalledTimes(1);
    });
});
