import { describe, expect, it, vi } from "vitest";

import { handleWebSocketMessage } from "./message-handlers";
import { INITIAL_PRACTICE_STATE, type PracticeState } from "./types";

function createMessageEvent(payload: unknown): MessageEvent {
    return new MessageEvent("message", {
        data: JSON.stringify(payload),
    });
}

function createDeps(initialState: PracticeState) {
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
            sendMessage: vi.fn(),
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
        const initial: PracticeState = {
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
        const initial: PracticeState = {
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

    it("clears transient audio runtime only after backend status marks the session paused", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            sessionStatus: "in_progress",
            aiState: "speaking",
            isPlayingAudio: true,
            isStreamingTTS: true,
            interimTranscript: "客户还在补充预算信息",
            isBackpressureActive: true,
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "status",
                timestamp: new Date().toISOString(),
                data: {
                    session_status: "paused",
                    ai_state: "idle",
                    connection_state: "connected",
                },
            }),
            deps as never,
        );

        expect(getState().sessionStatus).toBe("paused");
        expect(getState().aiState).toBe("idle");
        expect(getState().isPlayingAudio).toBe(false);
        expect(getState().isStreamingTTS).toBe(false);
        expect(getState().interimTranscript).toBe("");
        expect(getState().isBackpressureActive).toBe(false);
    });

    it("handles interrupted event by resetting playback flags to listening", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            aiState: "speaking",
            isPlayingAudio: true,
            isStreamingTTS: true,
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "interrupted",
                timestamp: new Date().toISOString(),
                data: { reason: "user_speaking" },
            }),
            deps as never,
        );

        expect(getState().aiState).toBe("listening");
        expect(getState().isPlayingAudio).toBe(false);
        expect(getState().isStreamingTTS).toBe(false);
    });

    it("maps interruption ai_message into AI chat flow", () => {
        const { deps } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "interruption",
                timestamp: new Date().toISOString(),
                data: {
                    reason: "missing_point",
                    ai_message: "请补充本页核心价值点。",
                },
            }),
            deps as never,
        );

        expect(deps.addAiMessageIfNew).toHaveBeenCalledWith(
            "请补充本页核心价值点。",
            { aiState: "speaking" },
        );
    });

    it("ignores interrupted event for stale stream_id", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            aiState: "speaking",
            isPlayingAudio: true,
            isStreamingTTS: true,
        });
        const streamingPlayer = deps.streamingPlayer as { interrupt: ReturnType<typeof vi.fn> };
        deps.currentStreamIdRef.current = "stream-live";

        handleWebSocketMessage(
            createMessageEvent({
                type: "interrupted",
                stream_id: "stream-stale",
                timestamp: new Date().toISOString(),
                data: { reason: "user_speaking" },
            }),
            deps as never,
        );

        expect(getState().aiState).toBe("speaking");
        expect(getState().isPlayingAudio).toBe(true);
        expect(getState().isStreamingTTS).toBe(true);
        expect(streamingPlayer.interrupt).not.toHaveBeenCalled();
    });

    it("clears currentStreamIdRef when interrupted stream_id matches", () => {
        const { deps } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            aiState: "speaking",
            isPlayingAudio: true,
            isStreamingTTS: true,
        });
        const streamingPlayer = deps.streamingPlayer as { interrupt: ReturnType<typeof vi.fn> };
        deps.currentStreamIdRef.current = "stream-live";

        handleWebSocketMessage(
            createMessageEvent({
                type: "interrupted",
                stream_id: "stream-live",
                timestamp: new Date().toISOString(),
                data: { reason: "user_speaking" },
            }),
            deps as never,
        );

        expect(deps.currentStreamIdRef.current).toBeNull();
        expect(streamingPlayer.interrupt).toHaveBeenCalledTimes(1);
    });

    it("updates slide and point state for presentation events", () => {
        const { deps, getState } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "slide_update",
                timestamp: new Date().toISOString(),
                data: {
                    current_page: 2,
                    page_number: 2,
                    total_pages: 8,
                    content: "Slide content",
                    page_content: "Slide content",
                    image_url: "/api/v1/presentations/ppt-1/pages/2/thumbnail",
                },
            }),
            deps as never,
        );

        handleWebSocketMessage(
            createMessageEvent({
                type: "point_covered",
                timestamp: new Date().toISOString(),
                data: {
                    point_id: "p-1",
                    is_covered: true,
                    content: "Key point",
                },
            }),
            deps as never,
        );

        expect(getState().currentSlide?.current_page).toBe(2);
        expect(getState().points).toHaveLength(1);
        expect(getState().points[0]).toMatchObject({
            point_id: "p-1",
            is_covered: true,
        });
        expect(getState().currentSlide?.image_url).toBe("/api/v1/presentations/ppt-1/pages/2/thumbnail");
        expect(getState().currentSlide?.page_content).toBe("Slide content");
    });

    it("clears stale points when receiving points_reset", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            points: [
                {
                    point_id: "old-point-1",
                    is_covered: true,
                    content: "旧页面要点",
                },
            ],
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "points_reset",
                timestamp: new Date().toISOString(),
                data: { current_page: 2 },
            }),
            deps as never,
        );

        expect(getState().points).toHaveLength(0);
    });

    it("maps feedback message to fuzzyDetections for realtime panel", () => {
        const { deps, getState } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "feedback",
                timestamp: new Date().toISOString(),
                data: {
                    feedback_type: "missing_point",
                    message: "请补充客户收益",
                    suggestions: ["补充一个量化案例"],
                    current_page: 1,
                },
            }),
            deps as never,
        );

        expect(getState().fuzzyDetections).toHaveLength(1);
        expect(getState().fuzzyDetections[0]).toMatchObject({
            category: "feedback",
            suggestion: "请补充客户收益",
        });
    });

    it("maps evaluation_feedback(stage_feedback) to score panel and realtime hint", () => {
        const { deps, getState } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "evaluation_feedback",
                timestamp: new Date().toISOString(),
                data: {
                    feedback_type: "stage_feedback",
                    stage_number: 2,
                    scores: {
                        communication: 86,
                        product_fit: 82,
                    },
                    summary: "进入需求挖掘阶段，继续追问预算与决策链。",
                    suggestions: ["下一轮聚焦预算与时间线"],
                },
            }),
            deps as never,
        );

        expect(getState().scores).toMatchObject({
            overall_score: 84,
            dimension_scores: {
                communication: 86,
                product_fit: 82,
            },
            stage_name: "阶段 2",
            suggestions: ["下一轮聚焦预算与时间线"],
        });
        expect(getState().fuzzyDetections[0]).toMatchObject({
            category: "feedback",
            suggestion: "进入需求挖掘阶段，继续追问预算与决策链。",
        });
    });

    it("keeps sales-specific score_update dimension vocabulary unchanged in frontend state", () => {
        const { deps, getState } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "score_update",
                timestamp: new Date().toISOString(),
                data: {
                    overall_score: 83,
                    turn_count: 4,
                    stage_name: "异议处理",
                    suggestions: ["补充案例证据后再回应价格异议"],
                    dimension_scores: {
                        价值表达: 87,
                        客户收益连接: 84,
                        证据使用: 72,
                        异议处理: 85,
                        推进下一步: 78,
                    },
                },
            }),
            deps as never,
        );

        expect(getState().scores).toMatchObject({
            overall_score: 83,
            turn_count: 4,
            stage_name: "异议处理",
            suggestions: ["补充案例证据后再回应价格异议"],
            dimension_scores: {
                价值表达: 87,
                客户收益连接: 84,
                证据使用: 72,
                异议处理: 85,
                推进下一步: 78,
            },
        });
    });

    it("applies same-turn score_update refreshes when sales dimensions or guidance change", () => {
        const initialScores = {
            overall_score: 83,
            turn_count: 4,
            stage_name: "需求挖掘",
            suggestions: ["继续确认客户当前流程"],
            dimension_scores: {
                价值表达: 80,
                客户收益连接: 84,
                证据使用: 72,
                异议处理: 85,
                推进下一步: 78,
            },
        };
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            scores: initialScores,
        });
        const previousScores = getState().scores;

        handleWebSocketMessage(
            createMessageEvent({
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
            }),
            deps as never,
        );

        expect(getState().scores).toMatchObject({
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
        });
        expect(getState().scores).not.toBe(previousScores);
    });

    it("keeps score_update idempotent when the full payload is unchanged", () => {
        const initial: PracticeState = {
            ...INITIAL_PRACTICE_STATE,
            scores: {
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
        };
        const { deps, getState } = createDeps(initial);
        const previousStateRef = getState();

        handleWebSocketMessage(
            createMessageEvent({
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
            }),
            deps as never,
        );

        expect(getState()).toBe(previousStateRef);
    });

    it("preserves unknown score_update dimensions for ScorePanel fallback rendering", () => {
        const { deps, getState } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "score_update",
                timestamp: new Date().toISOString(),
                data: {
                    overall_score: 66,
                    turn_count: 2,
                    suggestions: [],
                    dimension_scores: {
                        自定义维度: 66,
                    },
                },
            }),
            deps as never,
        );

        expect(getState().scores?.dimension_scores).toEqual({
            自定义维度: 66,
        });
    });

    it("maps evaluation_feedback(milestone) to realtime hint only", () => {
        const { deps, getState } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "evaluation_feedback",
                timestamp: new Date().toISOString(),
                data: {
                    feedback_type: "milestone",
                    message: "你已完成 50% 关键阶段，保持节奏。",
                },
            }),
            deps as never,
        );

        expect(getState().scores).toBeNull();
        expect(getState().fuzzyDetections[0]).toMatchObject({
            category: "feedback",
            suggestion: "你已完成 50% 关键阶段，保持节奏。",
        });
    });

    it("updates session state on session_ended event", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            sessionStatus: "in_progress",
            aiState: "speaking",
            isPlayingAudio: true,
            isStreamingTTS: true,
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "session_ended",
                timestamp: new Date().toISOString(),
                data: { session_status: "completed" },
            }),
            deps as never,
        );

        expect(getState().sessionStatus).toBe("completed");
        expect(getState().aiState).toBe("idle");
        expect(getState().isPlayingAudio).toBe(false);
        expect(getState().isStreamingTTS).toBe(false);
    });

    it("responds to heartbeat with heartbeat_ack", () => {
        const { deps } = createDeps(INITIAL_PRACTICE_STATE);

        handleWebSocketMessage(
            createMessageEvent({
                type: "heartbeat",
                timestamp: new Date().toISOString(),
                data: {},
            }),
            deps as never,
        );

        expect(deps.sendMessage).toHaveBeenCalledTimes(1);
        expect(deps.sendMessage).toHaveBeenCalledWith(
            "heartbeat_ack",
            expect.objectContaining({
                client_ts: expect.any(String),
            }),
        );
    });

    it("restores connected runtime state on reconnected event", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            connectionState: "reconnecting",
            isConnected: false,
            isConnecting: true,
            sessionStatus: "paused",
            aiState: "idle",
            error: "temporary error",
            isPlayingAudio: true,
            isStreamingTTS: true,
            interimTranscript: "临时识别文本",
            isBackpressureActive: true,
            isNetworkSlow: true,
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "reconnected",
                timestamp: new Date().toISOString(),
                data: {
                    restored_state: {
                        session_status: "in_progress",
                        ai_state: "listening",
                    },
                },
            }),
            deps as never,
        );

        expect(getState().connectionState).toBe("connected");
        expect(getState().isConnected).toBe(true);
        expect(getState().isConnecting).toBe(false);
        expect(getState().sessionStatus).toBe("in_progress");
        expect(getState().aiState).toBe("listening");
        expect(getState().isPlayingAudio).toBe(false);
        expect(getState().isStreamingTTS).toBe(false);
        expect(getState().interimTranscript).toBe("");
        expect(getState().isBackpressureActive).toBe(false);
        expect(getState().isNetworkSlow).toBe(false);
        expect(getState().error).toBeNull();
    });

    it("marks connection failed on session_timeout and surfaces error callback", () => {
        const { deps, getState } = createDeps({
            ...INITIAL_PRACTICE_STATE,
            connectionState: "connected",
            isConnected: true,
            isConnecting: false,
            aiState: "speaking",
            isPlayingAudio: true,
            isStreamingTTS: true,
        });

        handleWebSocketMessage(
            createMessageEvent({
                type: "session_timeout",
                timestamp: new Date().toISOString(),
                data: {
                    message: "会话超时，请重新开始",
                },
            }),
            deps as never,
        );

        expect(getState().connectionState).toBe("failed");
        expect(getState().isConnected).toBe(false);
        expect(getState().isConnecting).toBe(false);
        expect(getState().aiState).toBe("idle");
        expect(getState().isPlayingAudio).toBe(false);
        expect(getState().isStreamingTTS).toBe(false);
        expect(getState().error).toBe("会话超时，请重新开始");
        expect(deps.onError).toHaveBeenCalledWith("会话超时，请重新开始");
    });
});
