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
let unstableStreamingPlayerMode = false;

const getMockStreamingPlayer = () => {
    if (unstableStreamingPlayerMode) {
        return createMockStreamingPlayer();
    }
    return mockStreamingPlayer;
};

vi.mock("./use-streaming-audio-player", () => ({
    useStreamingAudioPlayer: () => getMockStreamingPlayer(),
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

vi.mock("./websocket/message-handlers", () => ({
    handleWebSocketMessage: vi.fn(),
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

    emitClose(code: number, reason = "") {
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.({ code, reason } as CloseEvent);
    }
}

describe("usePracticeWebSocket reconnect lifecycle", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        MockWebSocket.instances = [];
        unstableStreamingPlayerMode = false;
        mockAudioQueueRef.current = [];
        mockIsPlayingRef.current = false;
        vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    });

    afterEach(() => {
        vi.clearAllMocks();
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });

    it("switches to reconnecting when abnormal close triggers retry", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-1",
                scenarioType: "sales",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            ws?.emitClose(1006, "abnormal-close");
        });

        expect((result.current as unknown as { connectionState?: string }).connectionState).toBe("reconnecting");
    });

    it("switches to failed after exhausting reconnect retries", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-2",
                scenarioType: "sales",
            }),
        );

        for (let attempt = 0; attempt < 6; attempt += 1) {
            const ws = MockWebSocket.instances.at(-1);
            expect(ws).toBeDefined();

            act(() => {
                ws?.emitClose(1006, `abnormal-${attempt}`);
            });

            if (attempt < 5) {
                const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
                act(() => {
                    vi.advanceTimersByTime(delay);
                });
            }
        }

        expect((result.current as unknown as { connectionState?: string }).connectionState).toBe("failed");
    });

    it("forces failed state when disconnect is called explicitly", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-3",
                scenarioType: "sales",
            }),
        );

        act(() => {
            result.current.disconnect();
        });

        expect((result.current as unknown as { connectionState?: string }).connectionState).toBe("failed");
    });

    it("resets retry budget when user reconnects from failed state", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-4",
                scenarioType: "sales",
            }),
        );

        for (let attempt = 0; attempt < 6; attempt += 1) {
            const ws = MockWebSocket.instances.at(-1);
            expect(ws).toBeDefined();

            act(() => {
                ws?.emitClose(1006, `abnormal-${attempt}`);
            });

            if (attempt < 5) {
                const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
                act(() => {
                    vi.advanceTimersByTime(delay);
                });
            }
        }

        expect((result.current as unknown as { connectionState?: string }).connectionState).toBe("failed");

        act(() => {
            result.current.connect();
        });

        const retryWs = MockWebSocket.instances.at(-1);
        expect(retryWs).toBeDefined();

        act(() => {
            retryWs?.emitClose(1006, "manual-retry-failed");
        });

        expect((result.current as unknown as { connectionState?: string }).connectionState).toBe("reconnecting");
    });

    it("gates audio send when session is paused", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-5",
                scenarioType: "sales",
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
            result.current.sendControl("pause");
        });

        ws?.send.mockClear();

        act(() => {
            result.current.sendAudio("base64-audio");
        });

        expect(ws?.send).not.toHaveBeenCalled();
    });

    it("does not reconnect when streaming player reference changes", () => {
        unstableStreamingPlayerMode = true;

        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-6",
                scenarioType: "sales",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();
        expect(MockWebSocket.instances).toHaveLength(1);

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
        });

        act(() => {
            result.current.sendControl("pause");
        });

        expect(MockWebSocket.instances).toHaveLength(1);
    });

    it("does not append auth token query params to websocket url", () => {
        localStorage.setItem("token", "legacy-token");

        renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-7",
                scenarioType: "sales",
                agentId: "agent-1",
                personaId: "persona-1",
                voiceMode: "legacy",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();
        expect(ws?.url).toContain("session_id=session-7");
        expect(ws?.url).toContain("agent_id=agent-1");
        expect(ws?.url).toContain("persona_id=persona-1");
        expect(ws?.url).toContain("voice_mode=legacy");
        expect(ws?.url).not.toContain("token=");
    });

    it("includes a request trace id in the websocket url", () => {
        renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-trace",
                scenarioType: "sales",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        const url = new URL(ws!.url);
        const traceId = url.searchParams.get("trace_id");
        expect(typeof traceId).toBe("string");
        expect(traceId).toMatch(/^[a-f0-9]{32}$/);
    });
});
