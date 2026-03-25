import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePracticeWebSocket } from "./use-practice-websocket";
import { handleWebSocketMessage } from "./websocket/message-handlers";

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

function emitJsonMessage(ws: MockWebSocket, payload: unknown) {
    ws.onmessage?.(
        new MessageEvent("message", {
            data: JSON.stringify(payload),
        }),
    );
}

describe("usePracticeWebSocket reconnect lifecycle", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        MockWebSocket.instances = [];
        unstableStreamingPlayerMode = false;
        mockAudioQueueRef.current = [];
        mockIsPlayingRef.current = false;
        vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
        vi.mocked(handleWebSocketMessage).mockImplementation((event, deps) => {
            const message = JSON.parse((event as MessageEvent).data as string) as {
                type: string;
                data?: {
                    ai_state?: string;
                    connection_state?: string;
                    session_status?: string;
                    restored_state?: {
                        ai_state?: string;
                        session_status?: string;
                    };
                };
            };

            if (message.type === "status") {
                deps.setState((prev) => {
                    const nextConnectionState = (message.data?.connection_state ?? prev.connectionState) as typeof prev.connectionState;
                    return {
                        ...prev,
                        connectionState: nextConnectionState,
                        isConnected: nextConnectionState === "connected",
                        isConnecting: nextConnectionState === "connecting" || nextConnectionState === "reconnecting",
                        sessionStatus: (message.data?.session_status ?? prev.sessionStatus) as typeof prev.sessionStatus,
                        aiState: (message.data?.ai_state ?? prev.aiState) as typeof prev.aiState,
                    };
                });
                return;
            }

            if (message.type === "reconnected") {
                deps.setState((prev) => ({
                    ...prev,
                    connectionState: "connected",
                    isConnected: true,
                    isConnecting: false,
                    error: null,
                    sessionStatus: (message.data?.restored_state?.session_status ?? prev.sessionStatus) as typeof prev.sessionStatus,
                    aiState: (message.data?.restored_state?.ai_state ?? prev.aiState) as typeof prev.aiState,
                }));
            }
        });
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

    it("waits for backend paused status before gating audio send", () => {
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
            if (!ws) return;
            emitJsonMessage(ws, {
                type: "status",
                data: {
                    session_status: "in_progress",
                    ai_state: "listening",
                    connection_state: "connected",
                },
            });
        });

        expect(result.current.sessionStatus).toBe("in_progress");

        act(() => {
            result.current.sendControl("pause");
        });

        expect(result.current.sessionStatus).toBe("in_progress");

        ws?.send.mockClear();

        act(() => {
            result.current.sendAudio("base64-audio-before-status");
        });

        expect(ws?.send).toHaveBeenCalledTimes(1);

        act(() => {
            if (!ws) return;
            emitJsonMessage(ws, {
                type: "status",
                data: {
                    session_status: "paused",
                    ai_state: "idle",
                    connection_state: "connected",
                },
            });
        });

        expect(result.current.sessionStatus).toBe("paused");

        ws?.send.mockClear();

        act(() => {
            result.current.sendAudio("base64-audio-after-status");
        });

        expect(ws?.send).not.toHaveBeenCalled();
    });

    it("restores audio send only after reconnected reports the session back in progress", () => {
        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-6",
                scenarioType: "sales",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
            emitJsonMessage(ws, {
                type: "status",
                data: {
                    session_status: "paused",
                    ai_state: "idle",
                    connection_state: "connected",
                },
            });
        });

        expect(result.current.sessionStatus).toBe("paused");

        ws?.send.mockClear();

        act(() => {
            result.current.sendAudio("audio-while-paused");
        });

        expect(ws?.send).not.toHaveBeenCalled();

        act(() => {
            if (!ws) return;
            emitJsonMessage(ws, {
                type: "reconnected",
                data: {
                    restored_state: {
                        session_status: "in_progress",
                        ai_state: "listening",
                    },
                },
            });
        });

        expect(result.current.sessionStatus).toBe("in_progress");
        expect(result.current.aiState).toBe("listening");

        ws?.send.mockClear();

        act(() => {
            result.current.sendAudio("audio-after-reconnect");
        });

        expect(ws?.send).toHaveBeenCalledTimes(1);
    });

    it("clears stale action-card hints on reconnect while preserving the objection proof prompt in scores", async () => {
        const actualHandlers = await vi.importActual<typeof import("./websocket/message-handlers")>(
            "./websocket/message-handlers",
        );
        vi.mocked(handleWebSocketMessage).mockImplementation((event, deps) =>
            actualHandlers.handleWebSocketMessage(event, deps),
        );

        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-reconnect-ledger",
                scenarioType: "sales",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
            emitJsonMessage(ws, {
                type: "score_update",
                timestamp: new Date().toISOString(),
                data: {
                    overall_score: 79,
                    turn_count: 5,
                    stage_name: "异议处理",
                    suggestions: ["给出 6 个月回本测算"],
                    dimension_scores: {
                        价值表达: 84,
                        客户收益连接: 82,
                        证据使用: 58,
                        异议处理: 76,
                        推进下一步: 68,
                    },
                },
            });
            emitJsonMessage(ws, {
                type: "action_card",
                timestamp: new Date().toISOString(),
                data: {
                    issue: "痛点已经聊到，但价值主张还缺少可验证的案例或数据。",
                    replacement: "在确认痛点后，补一个同类客户案例、数据或ROI区间。",
                    next_turn_rule: "下一轮先确认痛点影响，再补一个案例或ROI数据。",
                },
            });
            emitJsonMessage(ws, {
                type: "fuzzy_detection",
                timestamp: new Date().toISOString(),
                data: {
                    detections: [
                        {
                            category: "feedback",
                            matched: [],
                            suggestion: "先别急着切到报价。",
                            severity: "medium",
                        },
                    ],
                },
            });
        });

        expect(result.current.actionCard?.issue).toContain("价值主张还缺少可验证的案例或数据");
        expect(result.current.fuzzyDetections).toHaveLength(1);
        expect(result.current.scores?.suggestions).toEqual(["给出 6 个月回本测算"]);

        act(() => {
            if (!ws) return;
            ws.emitClose(1006, "network-drop");
        });

        expect(result.current.connectionState).toBe("reconnecting");
        expect(result.current.actionCard).toBeNull();
        expect(result.current.fuzzyDetections).toEqual([]);
        expect(result.current.scores?.suggestions).toEqual(["给出 6 个月回本测算"]);
    });

    it("does not reconnect when streaming player reference changes", () => {
        unstableStreamingPlayerMode = true;

        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-7",
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
                sessionId: "session-8",
                scenarioType: "sales",
                agentId: "agent-1",
                personaId: "persona-1",
                voiceMode: "legacy",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();
        expect(ws?.url).toContain("session_id=session-8");
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

    it("clears stale turn hints on final transcripts through the websocket wrapper while keeping stage and score context", async () => {
        const actualHandlers = await vi.importActual<typeof import("./websocket/message-handlers")>(
            "./websocket/message-handlers",
        );
        vi.mocked(handleWebSocketMessage).mockImplementation((event, deps) =>
            actualHandlers.handleWebSocketMessage(event, deps),
        );

        const { result } = renderHook(() =>
            usePracticeWebSocket({
                sessionId: "session-turn-reset",
                scenarioType: "sales",
            }),
        );

        const ws = MockWebSocket.instances.at(-1);
        expect(ws).toBeDefined();

        act(() => {
            if (!ws) return;
            ws.readyState = MockWebSocket.OPEN;
            ws.onopen?.(new Event("open"));
            emitJsonMessage(ws, {
                type: "stage_update",
                timestamp: new Date().toISOString(),
                data: {
                    current_stage: "objection",
                    stage_name: "异议处理",
                    key_actions: ["先回应风险", "再补证据"],
                    guidance: "保持问题澄清后再推进下一步",
                    progress: 0.72,
                },
            });
            emitJsonMessage(ws, {
                type: "score_update",
                timestamp: new Date().toISOString(),
                data: {
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["先补一个 ROI 证据，再回应价格异议"],
                    dimension_scores: {
                        价值表达: 80,
                        客户收益连接: 84,
                        证据使用: 79,
                        异议处理: 85,
                        推进下一步: 78,
                    },
                },
            });
            emitJsonMessage(ws, {
                type: "action_card",
                timestamp: new Date().toISOString(),
                data: {
                    issue: "直接跳到报价",
                    replacement: "我先确认预算审批链路，再给你报价区间。",
                    next_turn_rule: "下一轮先确认预算与决策人。",
                },
            });
            emitJsonMessage(ws, {
                type: "fuzzy_detection",
                timestamp: new Date().toISOString(),
                data: {
                    detections: [
                        {
                            category: "feedback",
                            matched: [],
                            suggestion: "先别急着报价。",
                            severity: "medium",
                        },
                    ],
                },
            });
        });

        expect(result.current.actionCard?.issue).toBe("直接跳到报价");
        expect(result.current.fuzzyDetections).toHaveLength(1);
        expect(result.current.salesStage?.stage_name).toBe("异议处理");
        expect(result.current.scores?.overall_score).toBe(83);

        act(() => {
            if (!ws) return;
            emitJsonMessage(ws, {
                type: "transcript",
                timestamp: new Date().toISOString(),
                data: {
                    text: "客户现在担心上线风险和预算审批。",
                    is_final: true,
                },
            });
        });

        expect(result.current.actionCard).toBeNull();
        expect(result.current.fuzzyDetections).toEqual([]);
        expect(result.current.salesStage?.stage_name).toBe("异议处理");
        expect(result.current.scores?.overall_score).toBe(83);
        expect(result.current.messages.at(-1)).toMatchObject({
            sender: "user",
            message: "客户现在担心上线风险和预算审批。",
        });
    });
});
