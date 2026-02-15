"use client";

/**
 * usePracticeWebSocket — Orchestrator hook for real-time sales / presentation practice.
 *
 * v1-6 Refactor: Split from monolithic 1097-line file into composable modules:
 *   - websocket/types.ts              — All type definitions & constants
 *   - websocket/use-audio-playback.ts — Audio queue, playback, unlock
 *   - websocket/message-handlers.ts   — WebSocket message routing (switch)
 *   - (this file)                     — Orchestrator: state, connection, send, backpressure, interrupt
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useStreamingAudioPlayer } from "./use-streaming-audio-player";
import { debug } from "@/lib/debug";

// ── Re-export every public type so existing consumers stay untouched ──
export type {
    InterruptReason, InterruptMessageData, WSMessage, ChatMessage,
    FuzzyDetection, SalesStage, ScoreDimension, ScoreUpdate,
    SlideUpdate, PointCovered, ForbiddenWordDetection,
    TTSAudioData, TTSChunkMessage, PracticeState, SessionStatus, ConnectionState,
    UsePracticeWebSocketOptions, TTSChunkData,
} from "./websocket/types";

import type {
    WSMessage, ChatMessage, PracticeState, InterruptMessageData,
    UsePracticeWebSocketOptions, ConnectionState,
} from "./websocket/types";
import type { InterruptReason } from "./websocket/types";
import { WS_BASE_URL, INITIAL_PRACTICE_STATE } from "./websocket/types";
import { useAudioPlayback } from "./websocket/use-audio-playback";
import { handleWebSocketMessage } from "./websocket/message-handlers";

// ── Constants ──
const MAX_RECONNECT_ATTEMPTS = 5;
const MAX_LOCAL_BUFFER_SIZE = 200; // ~4 seconds of audio at 20ms chunks
const INTERIM_TRANSCRIPT_THROTTLE_MS = 80;
const MAX_CHAT_MESSAGES = 200;

// v1-13: Binary frame type constants (must match backend)
const BINARY_AUDIO_CHUNK = 0x01;
const BINARY_AUDIO_INTERRUPT = 0x02;

function deriveConnectionFlags(connectionState: ConnectionState): {
    isConnected: boolean;
    isConnecting: boolean;
} {
    return {
        isConnected: connectionState === "connected",
        isConnecting: connectionState === "connecting" || connectionState === "reconnecting",
    };
}

function maskWsUrlToken(url: string): string {
    return url.replace(/([?&]token=)[^&]+/i, "$1***");
}

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

    // ── Core refs ──
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const isConnectingRef = useRef(false);
    const manualDisconnectRef = useRef(false);

    // ── State ──
    const [state, setState] = useState<PracticeState>(INITIAL_PRACTICE_STATE);
    const connectionStateRef = useRef<ConnectionState>(INITIAL_PRACTICE_STATE.connectionState);
    connectionStateRef.current = state.connectionState;

    // ── High-frequency transcript throttling ──
    const interimTranscriptPendingRef = useRef("");
    const interimTranscriptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ── Streaming audio player (for tts_chunk messages) ──
    const streamingPlayer = useStreamingAudioPlayer({
        onPlaybackStart: () => {
            setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));
        },
        onPlaybackEnd: () => {
            setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening", isStreamingTTS: false }));
        },
        onError: (error) => {
            console.error("[StreamingTTS] Error:", error);
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
    const seenAiMessagesRef = useRef<Set<string>>(new Set());

    // P1-7 + P2-15: Extracted helper for adding AI messages with O(1) Set-based dedup
    const addAiMessageIfNew = useCallback((text: string, extraState?: Partial<PracticeState>) => {
        if (!text) return;
        if (seenAiMessagesRef.current.has(text)) return;
        // NEW-4 Fix: Cap Set size to prevent unbounded memory growth
        if (seenAiMessagesRef.current.size >= 200) {
            const first = seenAiMessagesRef.current.values().next().value;
            if (first !== undefined) seenAiMessagesRef.current.delete(first);
        }
        seenAiMessagesRef.current.add(text);
        const newMsg: ChatMessage = {
            id: `ai-${Date.now()}`,
            sender: "ai",
            message: text,
            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        };
        setState(prev => {
            const nextMessages = [...prev.messages, newMsg];
            return {
                ...prev,
                ...extraState,
                messages:
                    nextMessages.length > MAX_CHAT_MESSAGES
                        ? nextMessages.slice(-MAX_CHAT_MESSAGES)
                        : nextMessages,
            };
        });
    }, []);

    // ── Stream tracking (Critical Fix #2) ──
    const currentStreamIdRef = useRef<string | null>(null);
    const currentRequestIdRef = useRef<number>(0);

    // ── Backpressure state (Voice Practice Optimization P0-2) ──
    const isBackpressureActiveRef = useRef(false);
    const localAudioBufferRef = useRef<string[]>([]);
    const isFlushingRef = useRef(false); // Critical Fix #4

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

    const resetRealtimeRuntimeState = useCallback(() => {
        currentStreamIdRef.current = null;
        currentRequestIdRef.current = 0;
        isBackpressureActiveRef.current = false;
        localAudioBufferRef.current = [];
        isFlushingRef.current = false;
        audioQueueRef.current = [];
        isPlayingRef.current = false;
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
            };
        });
    }, [audioQueueRef, clearInterimTranscriptThrottle, interruptStreamingPlayback, isPlayingRef]);

    // ── Send helpers ──
    const sendMessage = useCallback((type: string, data: unknown) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const message: WSMessage = { type, timestamp: new Date().toISOString(), data };
            wsRef.current.send(JSON.stringify(message));
        }
    }, []);

    const sendText = useCallback((content: string) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
            return;
        }
        if (state.sessionStatus !== "in_progress" || state.connectionState !== "connected") {
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
    }, [sendMessage, state.connectionState, state.sessionStatus]);

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

        isFlushingRef.current = true;
        const chunksToSend = localAudioBufferRef.current.splice(0);
        debug.log(`[Backpressure] Flushing ${chunksToSend.length} buffered audio chunks`);

        let index = 0;
        const sendNext = () => {
            if (index < chunksToSend.length && !isBackpressureActiveRef.current) {
                sendMessage("audio_chunk", { audio: chunksToSend[index], sample_rate: 16000, interrupt: false });
                index++;
                setTimeout(sendNext, 10);
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

    const sendControl = useCallback((action: "start" | "pause" | "resume" | "end") => {
        debug.log("[PracticeWS] Send control", {
            action,
            sessionId,
            scenarioType,
            voiceMode,
        });
        if (action === "start" || action === "resume") {
            setState(prev => ({
                ...prev,
                sessionStatus: "in_progress",
                aiState: "listening",
            }));
        } else if (action === "pause") {
            interruptStreamingPlayback();
            audioQueueRef.current = [];
            isPlayingRef.current = false;
            clearInterimTranscriptThrottle();
            setState(prev => ({
                ...prev,
                sessionStatus: "paused",
                aiState: "idle",
                isPlayingAudio: false,
                isStreamingTTS: false,
                interimTranscript: "",
            }));
        } else if (action === "end") {
            clearInterimTranscriptThrottle();
            setState(prev => ({
                ...prev,
                aiState: "idle",
                isPlayingAudio: false,
                isStreamingTTS: false,
                interimTranscript: "",
            }));
        }

        sendMessage("control", { action });
    }, [
        audioQueueRef,
        clearInterimTranscriptThrottle,
        interruptStreamingPlayback,
        isPlayingRef,
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
    const getToken = useCallback(() => {
        if (typeof window !== "undefined") {
            return localStorage.getItem("token") || "";
        }
        return "";
    }, []);

    const buildWsUrl = useCallback(() => {
        const token = getToken();
        const tokenParam = token ? `&token=${encodeURIComponent(token)}` : "";
        let url = `${WS_BASE_URL}/ws/${scenarioType}?session_id=${sessionId}${tokenParam}`;
        if (agentId) url += `&agent_id=${agentId}`;
        if (personaId) url += `&persona_id=${personaId}`;
        if (voiceMode) url += `&voice_mode=${voiceMode}`;
        return url;
    }, [sessionId, scenarioType, agentId, personaId, voiceMode, getToken]);

    const connect = useCallback(() => {
        if (isConnectingRef.current) return;
        if (wsRef.current?.readyState === WebSocket.OPEN ||
            wsRef.current?.readyState === WebSocket.CONNECTING) return;

        if (connectionStateRef.current === "failed") {
            reconnectAttempts.current = 0;
        }

        manualDisconnectRef.current = false;
        isConnectingRef.current = true;
        // NEW-4 Fix: Reset dedup set on reconnect so welcome messages are not swallowed
        seenAiMessagesRef.current.clear();
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
            if (ws.readyState !== WebSocket.CLOSED) {
                setState(prev => ({
                    ...prev,
                    error: reconnectAttempts.current > 0
                        ? "连接中断，正在尝试恢复..."
                        : "连接错误",
                }));
            }
        };

        ws.onclose = (event) => {
            if (wsRef.current === ws) {
                wsRef.current = null;
            }
            isConnectingRef.current = false;

            if (manualDisconnectRef.current) {
                return;
            }

            const shouldRetry =
                reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
                && event.code !== 1000
                && event.code !== 1001;

            debug.warn("[PracticeWS] WebSocket closed", {
                sessionId,
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean,
                shouldRetry,
                reconnectAttempt: reconnectAttempts.current,
            });

            if (shouldRetry) {
                resetRealtimeRuntimeState();
                applyConnectionState("reconnecting", "连接中断，正在重连...");
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
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
            applyConnectionState("failed", "连接失败，请点击“重新连接”");
        };

        wsRef.current = ws;
    }, [
        agentId,
        applyConnectionState,
        buildWsUrl,
        personaId,
        resetRealtimeRuntimeState,
        scenarioType,
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
        const { wasPlaying, clearedChunks } = interruptStreamingPlayback();

        if (isPlayingRef.current) isPlayingRef.current = false;
        const nonStreamingQueueLength = audioQueueRef.current.length;
        audioQueueRef.current = [];

        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }

        setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening", isStreamingTTS: false }));

        const interruptData: InterruptMessageData = { reason, timestamp: Date.now() };
        sendMessage("interrupt", interruptData);

        const totalCleared = clearedChunks + nonStreamingQueueLength;
        debug.log(`[Interrupt] Sent interrupt signal (reason: ${reason}, wasPlaying: ${wasPlaying}, clearedChunks: ${totalCleared})`);
        return { wasPlaying, clearedChunks: totalCleared };
    }, [interruptStreamingPlayback, sendMessage, audioQueueRef, isPlayingRef]);

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
