"use client";

/**
 * usePracticeWebSocket — Orchestrator hook for real-time sales / presentation practice.
 *
 * v1-6 Refactor: Split from monolithic 1097-line file into composable modules:
 *   - websocket/types.ts              — All type definitions & constants
 *   - websocket/use-audio-playback.ts — Audio queue, playback, unlock
 *   - websocket/message-handlers.ts   — Inbound WebSocket protocol → practice state projection
 *   - websocket/transport.ts          — URL assembly, reconnect/backoff policy, pending queue helpers
 *   - (this file)                     — Transport/orchestration boundary for the outward contract
 *
 * Real responsibility boundary (M017/S02/T01):
 *   - This hook owns transport lifecycle: connect/disconnect, reconnect budget, URL/runtime lock,
 *     pending outbound message flush, and binary negotiation on open.
 *   - This hook owns outbound realtime pacing: audio send gating, local backpressure buffering/
 *     flush aborts, and interrupt pre-cleanup across playback refs, throttled interim transcript state,
 *     and browser speech synthesis.
 *   - message-handlers owns inbound protocol application: status/reconnected/interrupted/
 *     backpressure events become state updates once the server tells us what runtime state is true.
 *   - The remaining complexity seam is therefore outbound orchestration around reconnect /
 *     backpressure / interrupt, not a generic “the file is too large so split it again” problem.
 *
 * M019/S03/T01 transport contract inventory:
 *   - outward consumer: `app/(user)/practice/[sessionId]/page.tsx` owns the live practice UI and
 *     page tests/mock wiring rely on the current `usePracticeWebSocket(...)` return contract.
 *   - already extracted behind this hook: `websocket/message-handlers.ts` (inbound projection),
 *     `websocket/transport.ts` (URL assembly, reconnect/backoff policy, pending outbound queue,
 *     close-reason mapping), `websocket/use-audio-playback.ts` (legacy audio queue/unlock),
 *     `use-streaming-audio-player.ts` (chunk playback), and
 *     `use-voice-speed-preference.ts` (playback-rate preference).
 *   - intentionally retained here: socket connect/disconnect lifecycle, runtime lock inputs,
 *     binary negotiation, flush-session abort control, local backpressure buffer/flush,
 *     interrupt cleanup across local playback/runtime refs, and the outward return contract.
 *   - follow-up split rule: transport helpers may move out, but the page must keep depending on
 *     this hook instead of rebuilding websocket lifecycle or backpressure logic locally.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
    useVoiceSpeedPreference,
} from "./use-voice-speed-preference";
import { useStreamingAudioPlayer } from "./use-streaming-audio-player";
import { debug } from "@/lib/debug";
import { getSharedTraceId } from "@/lib/observability/trace-context";
import { practiceUxConfig } from "@/lib/practice-ux-config";

// ── Re-export every public type so existing consumers stay untouched ──
export type {
    InterruptReason, InterruptMessageData, WSMessage, ChatMessage,
    FuzzyDetection, SalesStage, ScoreDimension, ScoreUpdate, ActionCard,
    CoachHealth, SlideUpdate, PointCovered, ForbiddenWordDetection,
    TTSAudioData, TTSChunkMessage, PracticeState, SessionStatus, ConnectionState,
    UsePracticeWebSocketOptions, TTSChunkData, LiveSessionConclusionSummary,
    SessionClaimTruthPayload,
} from "./websocket/types";

import type {
    WSMessage, ChatMessage, PracticeState, InterruptMessageData,
    UsePracticeWebSocketOptions, ConnectionState,
} from "./websocket/types";
import type { InterruptReason } from "./websocket/types";
import { WS_BASE_URL, INITIAL_PRACTICE_STATE } from "./websocket/types";
import { useAudioPlayback } from "./websocket/use-audio-playback";
import { handleWebSocketMessage } from "./websocket/message-handlers";
import {
    buildPracticeWebSocketUrl,
    createPendingMessageQueue,
    deriveConnectionFlags,
    maskWsUrlToken,
    nextReconnectDelay,
    toCloseReasonMessage,
} from "./websocket/transport";

// ── Constants ──
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_LOCAL_BUFFER_SIZE = 200; // ~4 seconds of audio at 20ms chunks
const INTERIM_TRANSCRIPT_THROTTLE_MS = 80;
const MAX_CHAT_MESSAGES = 200;
const MAX_PENDING_OUTGOING_MESSAGES = 80;

// v1-13: Binary frame type constants (must match backend)
const BINARY_AUDIO_CHUNK = 0x01;
const BINARY_AUDIO_INTERRUPT = 0x02;
type OutgoingMessagePriority = "high" | "normal";

/** v1-13: Convert Int16Array PCM to Base64 string (used only during backpressure fallback). */
function pcmToBase64(pcmData: Int16Array): string {
    const bytes = new Uint8Array(pcmData.buffer, pcmData.byteOffset, pcmData.byteLength);
    const binary = String.fromCharCode(...bytes);
    return btoa(binary);
}

export function usePracticeWebSocket(options: UsePracticeWebSocketOptions) {
    const {
        sessionId, scenarioType, agentId, personaId,
        onMessage, onError, onTTSAudio, onTTSChunk,
        useStreamingTTS = true,
        voiceMode = "legacy",
    } = options;
    const { voiceSpeedPreference } = useVoiceSpeedPreference();

    // ── Core refs ──
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const isConnectingRef = useRef(false);
    const manualDisconnectRef = useRef(false);
    const pendingMessagesRef = useRef(createPendingMessageQueue(MAX_PENDING_OUTGOING_MESSAGES));

    // ── State ──
    const [state, setState] = useState<PracticeState>(INITIAL_PRACTICE_STATE);
    const connectionStateRef = useRef<ConnectionState>(INITIAL_PRACTICE_STATE.connectionState);
    connectionStateRef.current = state.connectionState;

    // ── High-frequency transcript throttling ──
    const interimTranscriptPendingRef = useRef("");
    const interimTranscriptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ── Streaming audio player (for tts_chunk messages) ──
    const streamingPlayer = useStreamingAudioPlayer({
        playbackRate: voiceSpeedPreference,
        onPlaybackStart: () => {
            setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));
        },
        onPlaybackEnd: () => {
            setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening", isStreamingTTS: false }));
        },
        onError: (error) => {
            debug.error("[StreamingTTS] Error:", error);
            setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening", isStreamingTTS: false }));
        },
    });
    const streamingInterruptRef = useRef(streamingPlayer.interrupt);
    const streamingStopRef = useRef(streamingPlayer.stop);
    const streamingResetRef = useRef(streamingPlayer.reset);
    const streamingClearQueueRef = useRef(streamingPlayer.clearQueue);

    useEffect(() => {
        streamingInterruptRef.current = streamingPlayer.interrupt;
        streamingStopRef.current = streamingPlayer.stop;
        streamingResetRef.current = streamingPlayer.reset;
        streamingClearQueueRef.current = streamingPlayer.clearQueue;
    }, [
        streamingPlayer.interrupt,
        streamingPlayer.stop,
        streamingPlayer.reset,
        streamingPlayer.clearQueue,
    ]);

    const interruptStreamingPlayback = useCallback(
        () => streamingInterruptRef.current(),
        [],
    );
    const stopStreamingPlayback = useCallback(
        () => streamingStopRef.current(),
        [],
    );
    const resetStreamingPlayback = useCallback(
        () => streamingResetRef.current(),
        [],
    );
    const clearStreamingPlaybackQueue = useCallback(
        () => streamingClearQueueRef.current(),
        [],
    );

    // ── Audio playback sub-hook ──
    const {
        audioQueueRef, isPlayingRef,
        queueTTSAudio, unlockAudio,
    } = useAudioPlayback({ onTTSAudio, setState });

    // ── Message dedup (P2-15 + NEW-4) ──
    const seenAiMessagesRef = useRef<Map<string, number>>(new Map());

    const pruneSeenAiMessages = useCallback((now: number) => {
        const expiresBefore = now - practiceUxConfig.messageDedupeWindowMs;
        for (const [key, seenAt] of seenAiMessagesRef.current) {
            if (seenAt < expiresBefore) {
                seenAiMessagesRef.current.delete(key);
            }
        }

        while (seenAiMessagesRef.current.size >= practiceUxConfig.messageDedupeMaxEntries) {
            const first = seenAiMessagesRef.current.keys().next().value;
            if (first === undefined) break;
            seenAiMessagesRef.current.delete(first);
        }
    }, []);

    // P1-7 + P2-15: Extracted helper for adding AI messages with bounded cross-reconnect dedup
    const addAiMessageIfNew = useCallback((
        text: string,
        extraState?: Partial<PracticeState> & { knowledgeAnswerDiagnostics?: import("./websocket/types").KnowledgeAnswerDiagnostics | null },
        dedupeKey?: string,
    ) => {
        if (!text) return;
        const now = Date.now();
        pruneSeenAiMessages(now);
        const cacheKey = dedupeKey || `text:${text.trim()}`;
        if (seenAiMessagesRef.current.has(cacheKey)) return;
        seenAiMessagesRef.current.set(cacheKey, now);
        const newMsg: ChatMessage = {
            id: `ai-${Date.now()}`,
            sender: "ai",
            message: text,
            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
            ...(extraState?.knowledgeAnswerDiagnostics
                ? { knowledgeAnswerDiagnostics: extraState.knowledgeAnswerDiagnostics }
                : {}),
        };
        setState(prev => {
            const nextMessages = [...prev.messages, newMsg];
            const restExtraState = { ...(extraState || {}) };
            delete restExtraState.knowledgeAnswerDiagnostics;
            return {
                ...prev,
                ...restExtraState,
                messages:
                    nextMessages.length > MAX_CHAT_MESSAGES
                        ? nextMessages.slice(-MAX_CHAT_MESSAGES)
                        : nextMessages,
            };
        });
    }, [pruneSeenAiMessages]);

    // ── Stream tracking (Critical Fix #2) ──
    const currentStreamIdRef = useRef<string | null>(null);
    const currentRequestIdRef = useRef<number>(0);

    // ── Backpressure state (Voice Practice Optimization P0-2) ──
    const isBackpressureActiveRef = useRef(false);
    const localAudioBufferRef = useRef<string[]>([]);
    const isFlushingRef = useRef(false); // Critical Fix #4
    const flushSessionRef = useRef(0); // Abort stale flush loops safely

    const flushInterimTranscript = useCallback(() => {
        interimTranscriptTimerRef.current = null;
        const pending = interimTranscriptPendingRef.current;
        setState(prev => (prev.interimTranscript === pending ? prev : { ...prev, interimTranscript: pending }));
    }, []);

    const scheduleInterimTranscriptUpdate = useCallback((text: string) => {
        interimTranscriptPendingRef.current = text;
        if (interimTranscriptTimerRef.current !== null) return;
        interimTranscriptTimerRef.current = setTimeout(
            flushInterimTranscript,
            INTERIM_TRANSCRIPT_THROTTLE_MS,
        );
    }, [flushInterimTranscript]);

    const clearInterimTranscriptThrottle = useCallback(() => {
        interimTranscriptPendingRef.current = "";
        if (interimTranscriptTimerRef.current !== null) {
            clearTimeout(interimTranscriptTimerRef.current);
            interimTranscriptTimerRef.current = null;
        }
    }, []);

    const applyConnectionState = useCallback(
        (connectionState: ConnectionState, error: string | null | undefined) => {
            const { isConnected, isConnecting } = deriveConnectionFlags(connectionState);
            setState(prev => {
                const nextError = error === undefined ? prev.error : error;
                if (
                    prev.connectionState === connectionState
                    && prev.isConnected === isConnected
                    && prev.isConnecting === isConnecting
                    && prev.error === nextError
                ) {
                    return prev;
                }
                return {
                    ...prev,
                    connectionState,
                    isConnected,
                    isConnecting,
                    error: nextError,
                };
            });
        },
        [],
    );

    const clearPendingMessages = useCallback(() => {
        if (pendingMessagesRef.current.size() === 0) {
            return;
        }
        pendingMessagesRef.current.clear();
    }, []);

    const resetRealtimeRuntimeState = useCallback(() => {
        currentStreamIdRef.current = null;
        currentRequestIdRef.current = 0;
        isBackpressureActiveRef.current = false;
        localAudioBufferRef.current = [];
        isFlushingRef.current = false;
        flushSessionRef.current = 0;
        audioQueueRef.current = [];
        isPlayingRef.current = false;
        clearPendingMessages();
        clearInterimTranscriptThrottle();
        interruptStreamingPlayback();

        setState(prev => {
            const nextAiState = prev.sessionStatus === "in_progress" ? "listening" : "idle";
            if (
                !prev.isPlayingAudio
                && !prev.isStreamingTTS
                && !prev.isBackpressureActive
                && !prev.isNetworkSlow
                && !prev.interimTranscript
                && prev.aiState === nextAiState
                && prev.actionCard === null
                && prev.fuzzyDetections.length === 0
            ) {
                return prev;
            }
            return {
                ...prev,
                aiState: nextAiState,
                isPlayingAudio: false,
                isStreamingTTS: false,
                isBackpressureActive: false,
                isNetworkSlow: false,
                interimTranscript: "",
                actionCard: null,
                fuzzyDetections: [],
            };
        });
    }, [
        audioQueueRef,
        clearInterimTranscriptThrottle,
        clearPendingMessages,
        interruptStreamingPlayback,
        isPlayingRef,
    ]);

    // ── Send helpers ──
    const flushPendingMessages = useCallback(() => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            return;
        }
        pendingMessagesRef.current.flushTo((message) => {
            ws.send(JSON.stringify(message));
        });
    }, []);

    const sendMessage = useCallback((type: string, data: unknown, options?: { priority?: OutgoingMessagePriority }) => {
        const message: WSMessage = {
            type,
            timestamp: new Date().toISOString(),
            data,
        };
        if (options?.priority) {
            message.priority = options.priority;
        }

        const ws = wsRef.current;
        if (ws?.readyState === WebSocket.OPEN) {
            flushPendingMessages();
            ws.send(JSON.stringify(message));
            return;
        }

        pendingMessagesRef.current.enqueue(message, {
            connectionState: connectionStateRef.current,
        });
    }, [flushPendingMessages]);

    const sendText = useCallback((content: string) => {
        if (state.sessionStatus !== "in_progress") {
            return;
        }
        debug.log("[PracticeWS] Send text", {
            length: content.length,
            preview: content.slice(0, 80),
        });
        sendMessage("text", { text: content });
        const newMsg: ChatMessage = {
            id: `user-${Date.now()}`,
            sender: "user",
            message: content,
            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        };
        setState(prev => {
            const nextMessages = [...prev.messages, newMsg];
            return {
                ...prev,
                messages:
                    nextMessages.length > MAX_CHAT_MESSAGES
                        ? nextMessages.slice(-MAX_CHAT_MESSAGES)
                        : nextMessages,
            };
        });
    }, [sendMessage, state.sessionStatus]);

    /**
     * Flush local audio buffer when backpressure is released.
     * Critical Fix #4: flushing flag prevents interleaving with sendAudio.
     * Requirements: Voice Practice Optimization P0-2
     */
    const flushLocalAudioBuffer = useCallback(() => {
        if (localAudioBufferRef.current.length === 0) return;
        if (isFlushingRef.current) {
            debug.log("[Backpressure] Already flushing, skipping duplicate flush");
            return;
        }

        const flushSessionId = ++flushSessionRef.current;
        isFlushingRef.current = true;
        const chunksToSend = localAudioBufferRef.current.splice(0);
        debug.log(`[Backpressure] Flushing ${chunksToSend.length} buffered audio chunks`);

        let index = 0;
        const sendNext = () => {
            if (flushSessionRef.current !== flushSessionId) {
                // Flush was explicitly aborted (e.g. interrupt): do not requeue old chunks.
                isFlushingRef.current = false;
                debug.log("[Backpressure] Flush aborted by newer session");
                return;
            }

            if (index < chunksToSend.length && !isBackpressureActiveRef.current) {
                sendMessage("audio_chunk", { audio: chunksToSend[index], sample_rate: 16000, interrupt: false });
                index++;
                setTimeout(sendNext, 10);
            } else if (index < chunksToSend.length && isBackpressureActiveRef.current) {
                // Backpressure re-activated during flush: put unsent chunks back at queue head.
                const unsentChunks = chunksToSend.slice(index);
                if (unsentChunks.length > 0) {
                    localAudioBufferRef.current = [...unsentChunks, ...localAudioBufferRef.current];
                }
                isFlushingRef.current = false;
                debug.warn(
                    `[Backpressure] Flush paused by slow_down, re-queued ${unsentChunks.length} chunks`,
                );
            } else {
                isFlushingRef.current = false;
                if (index >= chunksToSend.length) {
                    debug.log(`[Backpressure] Flush complete, sent ${index} chunks`);
                }
            }
        };
        sendNext();
    }, [sendMessage]);

    /**
     * v1-13: Send raw binary frame over WebSocket.
     * Skips JSON + Base64 overhead entirely → ~33% bandwidth reduction for audio.
     */
    const sendBinaryFrame = useCallback((frameType: number, payload: ArrayBuffer | Uint8Array) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const payloadBytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
            const frame = new Uint8Array(1 + payloadBytes.length);
            frame[0] = frameType;
            frame.set(payloadBytes, 1);
            wsRef.current.send(frame.buffer);
        }
    }, []);

    /**
     * v1-13: Send audio as binary frame (preferred path).
     * Accepts Int16Array (PCM) directly from audio recorder — no Base64 encoding.
     * With backpressure awareness. Falls back to buffering when backpressure active.
     */
    const sendAudioBinary = useCallback((pcmData: Int16Array, interrupt = false) => {
        if (
            wsRef.current?.readyState !== WebSocket.OPEN
            || state.connectionState !== "connected"
            || state.sessionStatus !== "in_progress"
        ) {
            return;
        }

        const payload = new Uint8Array(pcmData.buffer, pcmData.byteOffset, pcmData.byteLength);

        if (interrupt) {
            sendBinaryFrame(BINARY_AUDIO_INTERRUPT, payload);
            return;
        }

        if (isBackpressureActiveRef.current || isFlushingRef.current) {
            // During backpressure, fall back to Base64 buffering (buffer stores strings)
            // This is acceptable because backpressure is rare and short-lived
            const base64 = pcmToBase64(pcmData);
            if (localAudioBufferRef.current.length >= MAX_LOCAL_BUFFER_SIZE) {
                localAudioBufferRef.current.shift();
                debug.warn("[Backpressure] Local buffer full, dropping oldest chunk");
                setState(prev => (prev.isNetworkSlow ? prev : { ...prev, isNetworkSlow: true }));
            }
            localAudioBufferRef.current.push(base64);
            return;
        }

        setState(prev => (prev.isNetworkSlow ? { ...prev, isNetworkSlow: false } : prev));
        sendBinaryFrame(BINARY_AUDIO_CHUNK, payload);
    }, [sendBinaryFrame, state.connectionState, state.sessionStatus]);

    /**
     * Send audio data with backpressure awareness (legacy Base64 JSON path).
     * Critical Fix #4: buffers during flushing to prevent interleaving.
     * Requirements: Voice Practice Optimization P0-2
     */
    const sendAudio = useCallback((audioData: string, interrupt = false) => {
        if (
            wsRef.current?.readyState !== WebSocket.OPEN
            || state.connectionState !== "connected"
            || state.sessionStatus !== "in_progress"
        ) {
            return;
        }

        if (interrupt) {
            sendMessage("audio_chunk", { audio: audioData, sample_rate: 16000, interrupt: true });
            return;
        }

        if (isBackpressureActiveRef.current || isFlushingRef.current) {
            if (localAudioBufferRef.current.length >= MAX_LOCAL_BUFFER_SIZE) {
                localAudioBufferRef.current.shift();
                debug.warn("[Backpressure] Local buffer full, dropping oldest chunk");
                setState(prev => (prev.isNetworkSlow ? prev : { ...prev, isNetworkSlow: true }));
            }
            localAudioBufferRef.current.push(audioData);
            if (isFlushingRef.current && !isBackpressureActiveRef.current) {
                debug.log("[Backpressure] Buffering audio during flush");
            }
            return;
        }

        setState(prev => (prev.isNetworkSlow ? { ...prev, isNetworkSlow: false } : prev));
        sendMessage("audio_chunk", { audio: audioData, sample_rate: 16000, interrupt: false });
    }, [sendMessage, state.connectionState, state.sessionStatus]);

    const sendAudioEnd = useCallback(() => {
        sendMessage("audio_end", {});
        clearInterimTranscriptThrottle();
        setState(prev => {
            const nextAiState = prev.sessionStatus === "in_progress" ? "thinking" : prev.aiState;
            if (prev.interimTranscript === "" && prev.aiState === nextAiState) {
                return prev;
            }
            return {
                ...prev,
                interimTranscript: "",
                aiState: nextAiState,
            };
        });
    }, [sendMessage, clearInterimTranscriptThrottle]);

    const commitAudio = useCallback(() => {
        sendMessage("user_speaking", { speaking: false });
    }, [sendMessage]);

    const startSpeaking = useCallback(() => {
        sendMessage("user_speaking", { speaking: true });
    }, [sendMessage]);

    const clearLocalAudioRuntime = useCallback(() => {
        interruptStreamingPlayback();
        audioQueueRef.current = [];
        isPlayingRef.current = false;
        clearInterimTranscriptThrottle();
        setState(prev => {
            if (
                !prev.isPlayingAudio
                && !prev.isStreamingTTS
                && !prev.interimTranscript
                && !prev.isBackpressureActive
            ) {
                return prev;
            }
            return {
                ...prev,
                isPlayingAudio: false,
                isStreamingTTS: false,
                interimTranscript: "",
                isBackpressureActive: false,
            };
        });
    }, [audioQueueRef, clearInterimTranscriptThrottle, interruptStreamingPlayback, isPlayingRef]);

    const sendControl = useCallback((action: "start" | "pause" | "resume" | "end") => {
        debug.log("[PracticeWS] Send control", {
            action,
            sessionId,
            scenarioType,
            voiceMode,
        });

        if (action === "pause" || action === "end") {
            clearLocalAudioRuntime();
        }

        sendMessage("control", { action }, { priority: "normal" });
    }, [
        clearLocalAudioRuntime,
        scenarioType,
        sendMessage,
        sessionId,
        voiceMode,
    ]);

    // ── Message handler (delegates to extracted module) ──
    // NEW-10/11 Fix: Ref-based approach breaks circular dependency chain
    const handleMessageRef = useRef<((event: MessageEvent) => void) | null>(null);

    const handleMessage = useCallback((event: MessageEvent) => {
        handleWebSocketMessage(event, {
            onMessage, onError, onTTSChunk, useStreamingTTS,
            setState, queueTTSAudio, addAiMessageIfNew,
            streamingPlayer, currentStreamIdRef, currentRequestIdRef,
            isBackpressureActiveRef, audioQueueRef, isPlayingRef,
            flushLocalAudioBuffer, scheduleInterimTranscriptUpdate,
            clearInterimTranscriptThrottle,
            sendMessage,
        });
    }, [
        onMessage,
        onError,
        queueTTSAudio,
        addAiMessageIfNew,
        onTTSChunk,
        useStreamingTTS,
        streamingPlayer,
        flushLocalAudioBuffer,
        audioQueueRef,
        isPlayingRef,
        scheduleInterimTranscriptUpdate,
        clearInterimTranscriptThrottle,
        sendMessage,
    ]);

    // Keep ref in sync with latest handleMessage closure
    handleMessageRef.current = handleMessage;

    // ── Connection management ──
    const buildWsUrl = useCallback(() => {
        return buildPracticeWebSocketUrl({
            baseUrl: WS_BASE_URL,
            scenarioType,
            sessionId,
            agentId,
            personaId,
            voiceMode,
            traceId: getSharedTraceId(),
        });
    }, [sessionId, scenarioType, agentId, personaId, voiceMode]);

    const connect = useCallback(() => {
        if (isConnectingRef.current) return;
        if (wsRef.current?.readyState === WebSocket.OPEN ||
            wsRef.current?.readyState === WebSocket.CONNECTING) return;

        if (connectionStateRef.current === "failed") {
            reconnectAttempts.current = 0;
        }

        manualDisconnectRef.current = false;
        isConnectingRef.current = true;
        const connectingState: ConnectionState =
            reconnectAttempts.current > 0 ? "reconnecting" : "connecting";
        applyConnectionState(connectingState, null);

        const url = buildWsUrl();
        debug.log("[PracticeWS] Connecting", {
            sessionId,
            scenarioType,
            voiceMode,
            agentId: agentId || null,
            personaId: personaId || null,
            reconnectAttempt: reconnectAttempts.current,
            url: maskWsUrlToken(url),
            debugEnabled: debug.enabled(),
        });
        const ws = new WebSocket(url);

        ws.onopen = () => {
            debug.log("[PracticeWS] WebSocket connected", {
                sessionId,
                scenarioType,
                voiceMode,
            });
            reconnectAttempts.current = 0;
            isConnectingRef.current = false;
            applyConnectionState("connected", null);
            flushPendingMessages();
            sendMessage("negotiate", { prefer_binary: true }, { priority: "normal" });
        };

        // NEW-10/11 Fix: Use ref to always get latest handleMessage
        ws.onmessage = (event: MessageEvent) => {
            handleMessageRef.current?.(event);
        };

        ws.onerror = () => {
            debug.warn("[PracticeWS] WebSocket error event (details usually unavailable, wait for onclose)", {
                sessionId,
                readyState: ws.readyState,
                reconnectAttempt: reconnectAttempts.current,
            });
            isConnectingRef.current = false;
            if (ws.readyState === WebSocket.CLOSED) {
                return;
            }

            const shouldRetry = reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS;
            applyConnectionState(
                shouldRetry ? "reconnecting" : "failed",
                shouldRetry ? "连接中断，正在尝试恢复..." : "连接失败，请点击“重新连接”",
            );
        };

        ws.onclose = (event) => {
            if (wsRef.current === ws) {
                wsRef.current = null;
            }
            isConnectingRef.current = false;

            if (manualDisconnectRef.current) {
                return;
            }

            const closeReasonText = toCloseReasonMessage(event.reason || "");
            const shouldRetry =
                reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
                && event.code !== 1000
                && event.code !== 1001;

            debug.warn("[PracticeWS] WebSocket closed", {
                sessionId,
                code: event.code,
                reason: event.reason,
                reasonHint: closeReasonText,
                wasClean: event.wasClean,
                shouldRetry,
                reconnectAttempt: reconnectAttempts.current,
            });

            if (shouldRetry) {
                resetRealtimeRuntimeState();
                applyConnectionState(
                    "reconnecting",
                    closeReasonText || "连接中断，正在重连...",
                );
                const delay = nextReconnectDelay(reconnectAttempts.current);
                reconnectAttempts.current++;
                debug.log(`[PracticeWS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
                setTimeout(() => {
                    if (!manualDisconnectRef.current) {
                        connect();
                    }
                }, delay);
                return;
            }

            resetRealtimeRuntimeState();
            applyConnectionState(
                "failed",
                closeReasonText || "连接失败，请点击“重新连接”",
            );
        };

        wsRef.current = ws;
    }, [
        agentId,
        applyConnectionState,
        buildWsUrl,
        personaId,
        flushPendingMessages,
        resetRealtimeRuntimeState,
        scenarioType,
        sendMessage,
        sessionId,
        voiceMode,
    ]);

    const disconnect = useCallback(() => {
        manualDisconnectRef.current = true;
        debug.log("[PracticeWS] Disconnect requested by user", { sessionId });
        isConnectingRef.current = false;
        reconnectAttempts.current = 0;
        clearInterimTranscriptThrottle();
        resetRealtimeRuntimeState();
        pendingMessagesRef.current.clear();
        applyConnectionState("failed", null);
        if (wsRef.current) {
            wsRef.current.close(1000, "User disconnected");
            wsRef.current = null;
        }
    }, [applyConnectionState, clearInterimTranscriptThrottle, resetRealtimeRuntimeState, sessionId]);

    // ── Interrupt ──
    /**
     * Send an interrupt signal to stop AI response.
     * Property 6: Interrupt Stops Playback
     * Property 7: Interrupt Queue Clearing
     * Validates: Requirements 3.1, 3.2
     */
    const sendInterrupt = useCallback((reason: InterruptReason = 'user_speaking'): { wasPlaying: boolean; clearedChunks: number } => {
        // Abort any in-flight flush before clearing buffers.
        flushSessionRef.current += 1;
        isFlushingRef.current = false;
        isBackpressureActiveRef.current = false;

        const bufferedAudioChunks = localAudioBufferRef.current.length;
        localAudioBufferRef.current = [];
        clearPendingMessages();
        clearInterimTranscriptThrottle();

        const { wasPlaying, clearedChunks } = interruptStreamingPlayback();

        if (isPlayingRef.current) isPlayingRef.current = false;
        const nonStreamingQueueLength = audioQueueRef.current.length;
        audioQueueRef.current = [];

        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }

        setState(prev => ({
            ...prev,
            isPlayingAudio: false,
            aiState: "listening",
            isStreamingTTS: false,
            isBackpressureActive: false,
            isNetworkSlow: false,
            interimTranscript: "",
        }));

        const interruptData: InterruptMessageData = { reason, timestamp: Date.now() };
        sendMessage("interrupt", interruptData, { priority: "high" });

        const totalCleared = clearedChunks + nonStreamingQueueLength + bufferedAudioChunks;
        debug.log(`[Interrupt] Sent interrupt signal (reason: ${reason}, wasPlaying: ${wasPlaying}, clearedChunks: ${totalCleared})`);
        return { wasPlaying, clearedChunks: totalCleared };
    }, [
        clearInterimTranscriptThrottle,
        clearPendingMessages,
        interruptStreamingPlayback,
        sendMessage,
        audioQueueRef,
        isPlayingRef,
    ]);

    // ── Auto-connect effect ──
    // Reconnect automatically if session runtime lock (scenario/voice mode) changes.
    useEffect(() => {
        connect();
        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    // ── Public API ──
    return {
        ...state,
        sessionStatus: state.sessionStatus,
        connect,
        disconnect,
        sendText,
        sendAudio,
        sendAudioEnd,
        sendControl,
        sendMessage,
        commitAudio,
        startSpeaking,
        unlockAudio,
        /**
         * Send an interrupt signal to stop AI response
         * Implements Property 6 (stop playback) and Property 7 (clear queue)
         * Validates: Requirements 3.1, 3.2
         */
        sendInterrupt,
        /** v1-13: Send audio as binary frame (preferred, ~33% less bandwidth) */
        sendAudioBinary,
        /** Send binary frame directly */
        sendBinaryFrame,
        /** Stop streaming TTS playback */
        stopStreamingTTS: stopStreamingPlayback,
        /** Reset streaming TTS player */
        resetStreamingTTS: resetStreamingPlayback,
        /** Streaming player state */
        streamingPlayerState: streamingPlayer.state,
        /** Clear the streaming audio queue */
        clearStreamingQueue: clearStreamingPlaybackQueue,
        /** Interrupt streaming playback (stop + clear queue) */
        interruptStreamingTTS: interruptStreamingPlayback,
        /** Flush local audio buffer (for backpressure control) */
        flushLocalAudioBuffer,
    };
}
