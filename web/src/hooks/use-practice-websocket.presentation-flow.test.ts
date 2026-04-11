import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePracticeWebSocket } from "./use-practice-websocket";

function createMockStreamingPlayer() {
    return {
        start: vi.fn(),
        stop: vi.fn(),
        reset: vi.fn(),
        clearQueue: vi.fn(),
        appendChunk: vi.fn(),
        end: vi.fn(),
        interrupt: vi.fn(() => ({ wasPlaying: false, clearedChunks: 0 })),
        state: {},
    };
}

const mockStreamingPlayer = createMockStreamingPlayer();

vi.mock("./use-streaming-audio-player", () => ({
    useStreamingAudioPlayer: () => mockStreamingPlayer,
}));

const mockAudioQueueRef = { current: [] as unknown[] };
const mockIsPlayingRef = { current: false };
const mockQueueTTSAudio = vi.fn();
const mockUnlockAudio = vi.fn();

vi.mock("./websocket/use-audio-playback", () => ({
    useAudioPlayback: () => ({
        audioQueueRef: mockAudioQueueRef,
        isPlayingRef: mockIsPlayingRef,
        queueTTSAudio: mockQueueTTSAudio,
        unlockAudio: mockUnlockAudio,
    }),
}));

class MockWebSocket {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSING = 2;
    static readonly CLOSED = 3;

    static instances: MockWebSocket[] = [];

    readonly url: string;
    readyState = MockWebSocket.CONNECTING;
    onopen: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;

    send = vi.fn();

    constructor(url: string) {
        this.url = url;
        MockWebSocket.instances.push(this);
    }

    close = vi.fn((code = 1000, reason = "") => {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.({ code, reason } as CloseEvent);
    });

    emitMessage(payload: unknown) {
        this.onmessage?.(
            new MessageEvent("message", {
                data: JSON.stringify(payload),
            }),
        );
    }
}

describe("usePracticeWebSocket presentation flow boundary", () => {
    beforeEach(() => {
        MockWebSocket.instances = [];
        mockAudioQueueRef.current = [];
        mockIsPlayingRef.current = false;
        vi.clearAllMocks();
        vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("keeps control:start as an outbound command until backend status advances the presentation session", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "ppt-session-1",
                scenarioType: "presentation",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
        });

        act(() => {
            result.current.sendControl("start");
        });

        const startControlPayload = ws?.send.mock.calls
            .map(call => JSON.parse(call[0] as string))
            .find((payload: { type: string; data?: { action?: string } }) => (
                payload.type === "control" && payload.data?.action === "start"
            ));
        expect(startControlPayload).toBeDefined();
        expect(result.current.sessionStatus).toBe("preparing");
        expect(result.current.aiState).toBe("idle");

        act(() => {
            ws?.emitMessage({
                type: "status",
                timestamp: new Date().toISOString(),
                data: {
                    session_status: "in_progress",
                    ai_state: "listening",
                    connection_state: "connected",
                },
            });
            ws?.emitMessage({
                type: "slide_update",
                timestamp: new Date().toISOString(),
                data: {
                    current_page: 2,
                    total_pages: 5,
                    content: "第二页内容",
                },
            });
        });

        expect(result.current.sessionStatus).toBe("in_progress");
        expect(result.current.aiState).toBe("listening");
        expect(result.current.currentSlide).toMatchObject({
            current_page: 2,
            total_pages: 5,
            content: "第二页内容",
        });
    });

    it("keeps speaking on stale interrupt and transitions on matching stream interrupt within the inbound presentation boundary", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "ppt-session-2",
                scenarioType: "presentation",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
            ws.emitMessage({
                type: "tts_chunk",
                stream_id: "stream-live",
                request_id: 1,
                timestamp: new Date().toISOString(),
                data: {
                    chunk_index: 0,
                    audio: "ZmFrZS1hdWRpbw==",
                    is_final: false,
                    audio_format: "mp3",
                },
            });
        });

        expect(result.current.aiState).toBe("speaking");
        expect(result.current.isStreamingTTS).toBe(true);

        act(() => {
            ws?.emitMessage({
                type: "interrupted",
                stream_id: "stream-stale",
                timestamp: new Date().toISOString(),
                data: { reason: "user_speaking" },
            });
        });

        expect(result.current.aiState).toBe("speaking");
        expect(result.current.isStreamingTTS).toBe(true);

        act(() => {
            ws?.emitMessage({
                type: "interrupted",
                stream_id: "stream-live",
                timestamp: new Date().toISOString(),
                data: { reason: "user_speaking" },
            });
        });

        expect(mockStreamingPlayer.interrupt).toHaveBeenCalledTimes(1);
        expect(result.current.aiState).toBe("listening");
        expect(result.current.isStreamingTTS).toBe(false);
    });

    it("moves to thinking immediately after user audio ends once backend status marks the presentation session in progress", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "ppt-session-3",
                scenarioType: "presentation",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
            ws.emitMessage({
                type: "status",
                timestamp: new Date().toISOString(),
                data: {
                    session_status: "in_progress",
                    ai_state: "listening",
                    connection_state: "connected",
                },
            });
        });

        act(() => {
            result.current.sendControl("start");
            result.current.sendAudioEnd();
        });

        expect(result.current.sessionStatus).toBe("in_progress");
        expect(result.current.aiState).toBe("thinking");
    });

    it("ignores stale interrupt confirmations after reconnect resets the presentation stream epoch", () => {
        vi.useFakeTimers();

        try {
            const { result } = renderHook(() =>
                usePracticeWebSocket({
                    sessionId: "ppt-session-4",
                    scenarioType: "presentation",
                }),
            );

            const ws = MockWebSocket.instances.at(-1);
            expect(ws).toBeDefined();

            act(() => {
                if (!ws) return;
                ws.readyState = MockWebSocket.OPEN;
                ws.onopen?.(new Event("open"));
                ws.emitMessage({
                    type: "status",
                    timestamp: new Date().toISOString(),
                    data: {
                        session_status: "in_progress",
                        ai_state: "listening",
                        connection_state: "connected",
                    },
                });
                ws.emitMessage({
                    type: "tts_chunk",
                    stream_id: "stream-live",
                    request_id: 1,
                    timestamp: new Date().toISOString(),
                    data: {
                        chunk_index: 0,
                        audio: "ZmFrZS1hdWRpbw==",
                        is_final: false,
                        audio_format: "mp3",
                    },
                });
            });

            expect(result.current.aiState).toBe("speaking");
            expect(result.current.isStreamingTTS).toBe(true);

            act(() => {
                ws?.close(1006, "network-drop");
            });

            expect(result.current.connectionState).toBe("reconnecting");
            expect(result.current.aiState).toBe("listening");
            expect(result.current.isStreamingTTS).toBe(false);
            expect(mockStreamingPlayer.interrupt).toHaveBeenCalledTimes(1);

            act(() => {
                vi.advanceTimersByTime(1000);
            });

            const retryWs = MockWebSocket.instances.at(-1);
            expect(retryWs).toBeDefined();
            expect(retryWs).not.toBe(ws);

            act(() => {
                if (!retryWs) return;
                retryWs.readyState = MockWebSocket.OPEN;
                retryWs.onopen?.(new Event("open"));
                retryWs.emitMessage({
                    type: "interrupted",
                    stream_id: "stream-live",
                    timestamp: new Date().toISOString(),
                    data: { reason: "user_speaking" },
                });
            });

            expect(mockStreamingPlayer.interrupt).toHaveBeenCalledTimes(1);
            expect(result.current.aiState).toBe("listening");
            expect(result.current.isStreamingTTS).toBe(false);
        } finally {
            vi.useRealTimers();
        }
    });
});
