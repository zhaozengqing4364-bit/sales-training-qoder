import { describe, expect, it, vi } from "vitest";

import { handleWebSocketMessage } from "./message-handlers";
import { INITIAL_PRACTICE_STATE, type PracticeState } from "./types";

function createMessageEvent(payload: unknown): MessageEvent {
    return new MessageEvent("message", {
        data: JSON.stringify(payload),
    });
}

function createDeps(initialState: PracticeState & { connectionState?: string }) {
    let state = initialState;

    const setState = vi.fn((updater: unknown) => {
        if (typeof updater === "function") {
            state = (updater as (prev: typeof state) => typeof state)(state);
            return;
        }
        state = updater as typeof state;
    });

    return {
        getState: () => state,
        deps: {
            onMessage: vi.fn(),
            onError: vi.fn(),
            onTTSChunk: vi.fn(),
            useStreamingTTS: true,
            setState,
            queueTTSAudio: vi.fn(),
            addAiMessageIfNew: vi.fn(),
            streamingPlayer: {
                start: vi.fn(),
                reset: vi.fn(),
                appendChunk: vi.fn(),
                end: vi.fn(),
                interrupt: vi.fn(() => ({ wasPlaying: false, clearedChunks: 0 })),
                stop: vi.fn(),
                clearQueue: vi.fn(),
                state: {},
            } as unknown,
            currentStreamIdRef: { current: null as string | null },
            currentRequestIdRef: { current: 0 },
            isBackpressureActiveRef: { current: false },
            audioQueueRef: { current: [] },
            isPlayingRef: { current: false },
            flushLocalAudioBuffer: vi.fn(),
            scheduleInterimTranscriptUpdate: vi.fn(),
            clearInterimTranscriptThrottle: vi.fn(),
        },
    };
}

describe("handleWebSocketMessage connection/status behavior", () => {
    it("promotes connection_state to connected on connected event", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            connectionState: "connecting",
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "connected",
                timestamp: new Date().toISOString(),
                data: { session_id: "session-1" },
            }),
            deps as never,
        );

        expect(getState().connectionState).toBe("connected");
    });

    it("does not create new state object for duplicate status payload", () => {
        const initial = {
            ...INITIAL_PRACTICE_STATE,
            sessionStatus: "in_progress" as const,
            aiState: "thinking" as const,
            connectionState: "connected",
        };
        const { deps, getState } = createDeps(initial);
        const previousStateRef = getState();

        handleWebSocketMessage(
            createMessageEvent({
                type: "status",
                timestamp: new Date().toISOString(),
                data: {
                    session_status: "in_progress",
                    ai_state: "thinking",
                },
            }),
            deps as never,
        );

        expect(getState()).toBe(previousStateRef);
    });

    it("does not create new state object for duplicate stage_update payload", () => {
        const initial = {
            ...INITIAL_PRACTICE_STATE,
            salesStage: {
                current_stage: "opening",
                stage_name: "开场破冰",
                key_actions: ["建立信任", "了解背景"],
                guidance: "保持自然开场",
                progress: 0.2,
            },
        };
        const { deps, getState } = createDeps(initial);
        const previousStateRef = getState();

        handleWebSocketMessage(
            createMessageEvent({
                type: "stage_update",
                timestamp: new Date().toISOString(),
                data: {
                    current_stage: "opening",
                    stage_name: "开场破冰",
                    key_actions: ["建立信任", "了解背景"],
                    guidance: "保持自然开场",
                    progress: 0.2,
                },
            }),
            deps as never,
        );

        expect(getState()).toBe(previousStateRef);
    });
});
