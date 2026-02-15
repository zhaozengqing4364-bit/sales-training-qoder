import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { UseStreamingAudioPlayerReturn, TTSChunkData } from "../use-streaming-audio-player";
import { debug } from "@/lib/debug";
import type {
    WSMessage, ChatMessage, PracticeState, TTSAudioData,
    FuzzyDetection, SalesStage, ScoreUpdate, SlideUpdate,
    PointCovered, ForbiddenWordDetection, TTSChunkMessage, SessionStatus, ConnectionState,
} from "./types";

/**
 * Dependencies required by the WebSocket message handler.
 * Passed in from the orchestrator hook to keep this module pure.
 */
export interface MessageHandlerDeps {
    onMessage?: (message: WSMessage) => void;
    onError?: (error: string) => void;
    onTTSChunk?: (data: TTSChunkData) => void;
    useStreamingTTS: boolean;
    setState: Dispatch<SetStateAction<PracticeState>>;
    queueTTSAudio: (data: TTSAudioData) => void;
    addAiMessageIfNew: (text: string, extraState?: Partial<PracticeState>) => void;
    streamingPlayer: UseStreamingAudioPlayerReturn;
    currentStreamIdRef: MutableRefObject<string | null>;
    currentRequestIdRef: MutableRefObject<number>;
    isBackpressureActiveRef: MutableRefObject<boolean>;
    audioQueueRef: MutableRefObject<TTSAudioData[]>;
    isPlayingRef: MutableRefObject<boolean>;
    flushLocalAudioBuffer: () => void;
    scheduleInterimTranscriptUpdate: (text: string) => void;
    clearInterimTranscriptThrottle: () => void;
    sendMessage?: (type: string, data: unknown) => void;
}

const MAX_CHAT_MESSAGES = 200;

function appendMessageCapped(
    existing: ChatMessage[],
    message: ChatMessage,
): ChatMessage[] {
    const next = [...existing, message];
    return next.length > MAX_CHAT_MESSAGES ? next.slice(-MAX_CHAT_MESSAGES) : next;
}

function isSameSalesStage(current: SalesStage | null, incoming: SalesStage): boolean {
    if (!current) return false;
    if (
        current.current_stage !== incoming.current_stage
        || current.stage_name !== incoming.stage_name
        || current.guidance !== incoming.guidance
        || current.progress !== incoming.progress
    ) {
        return false;
    }
    if (current.key_actions.length !== incoming.key_actions.length) {
        return false;
    }
    return current.key_actions.every((action, index) => action === incoming.key_actions[index]);
}

/**
 * Process a single WebSocket message event.
 *
 * Extracted from the monolithic usePracticeWebSocket hook (v1-6 refactor)
 * to improve readability and testability.
 */
export function handleWebSocketMessage(
    event: MessageEvent,
    deps: MessageHandlerDeps,
): void {
    const {
        onMessage, onError, onTTSChunk, useStreamingTTS,
        setState, queueTTSAudio, addAiMessageIfNew,
        streamingPlayer, currentStreamIdRef, currentRequestIdRef,
        isBackpressureActiveRef, audioQueueRef, isPlayingRef,
        flushLocalAudioBuffer, scheduleInterimTranscriptUpdate,
        clearInterimTranscriptThrottle,
        sendMessage,
    } = deps;

    try {
        const message: WSMessage = JSON.parse(event.data);
        onMessage?.(message);

        switch (message.type) {
            case "connected":
                debug.log("[PracticeWS] Connected event received", {
                    traceId: message.trace_id || null,
                });
                setState(prev => ({
                    ...prev,
                    connectionState: "connected",
                    isConnected: true,
                    isConnecting: false,
                    error: null,
                }));
                break;

            case "transcript":
            case "asr_transcript": {
                const data = message.data as { text: string; is_final: boolean };
                
                if (data.is_final) {
                    clearInterimTranscriptThrottle();
                    // 最终结果：添加消息（如果有文本）并清空中间结果
                    if (data.text.trim()) {
                        const newMsg: ChatMessage = {
                            id: `user-${Date.now()}`,
                            sender: "user",
                            message: data.text,
                            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
                        };
                        setState(prev => ({
                            ...prev,
                            messages: appendMessageCapped(prev.messages, newMsg),
                            interimTranscript: "",
                        }));
                    } else {
                        // 即使最终文本为空，也要清空中间结果
                        setState(prev => ({
                            ...prev,
                            interimTranscript: "",
                        }));
                    }
                } else if (data.text) {
                    // 中间结果：节流更新，降低高频渲染压力
                    scheduleInterimTranscriptUpdate(data.text);
                }
                break;
            }

            case "response": {
                const data = message.data as { text: string };
                const newMsg: ChatMessage = {
                    id: `ai-${Date.now()}`,
                    sender: "ai",
                    message: data.text,
                    timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
                };
                setState(prev => ({
                    ...prev,
                    messages: appendMessageCapped(prev.messages, newMsg),
                    aiState: "speaking",
                }));
                break;
            }

            case "interruption": {
                const data = message.data as {
                    ai_message?: string;
                    message?: string;
                    reason?: string;
                };
                const aiMessage = (data.ai_message || data.message || "").trim();

                if (aiMessage) {
                    addAiMessageIfNew(aiMessage, { aiState: "speaking" });
                } else {
                    setState(prev => ({
                        ...prev,
                        aiState: "speaking",
                    }));
                }
                break;
            }

            case "tts_audio": {
                const data = message.data as TTSAudioData;
                
                // Critical Fix #2: 检查stream_id和request_id，过滤过期的TTS消息
                const messageStreamId = message.stream_id;
                const messageRequestId = message.request_id;
                
                if (messageStreamId) {
                    // 更新当前stream_id（如果有新的）
                    if (!currentStreamIdRef.current || messageStreamId !== currentStreamIdRef.current) {
                        debug.log(`[TTS Audio] New stream: stream_id=${messageStreamId}, request_id=${messageRequestId}`);
                        currentStreamIdRef.current = messageStreamId;
                        if (messageRequestId !== undefined) {
                            currentRequestIdRef.current = messageRequestId;
                        }
                    }
                }
                
                // P2-15: O(1) dedup check + add AI message
                addAiMessageIfNew(data.text, { aiState: "speaking" });
                queueTTSAudio(data);
                break;
            }

            /**
             * Handle streaming TTS chunks
             * 
             * Requirements: 2.2, 2.3, 2.4
             * - Initialize streaming player on first chunk (chunk_index=0)
             * - Append chunks to player buffer
             * - End stream when is_final=true
             */
            case "tts_chunk": {
                const chunkData = message.data as TTSChunkMessage;
                const isPCMChunk = (chunkData.audio_format || "").toLowerCase() === "pcm16";
                
                // Critical Fix #2: 检查stream_id，过滤过期的TTS chunk
                const messageStreamId = message.stream_id;
                const messageRequestId = message.request_id;
                
                // 如果这是第一个chunk (chunk_index === 0)，更新当前的stream_id
                if (chunkData.chunk_index === 0) {
                    if (messageStreamId) {
                        debug.log(`[TTS] New stream started: stream_id=${messageStreamId}, request_id=${messageRequestId}`);
                        currentStreamIdRef.current = messageStreamId;
                        if (messageRequestId !== undefined) {
                            currentRequestIdRef.current = messageRequestId;
                        }
                    }
                } else {
                    // 对于非首chunk，检查stream_id是否匹配
                    if (messageStreamId && messageStreamId !== currentStreamIdRef.current) {
                        debug.warn(
                            `[TTS] Dropping stale chunk: expected stream_id=${currentStreamIdRef.current}, ` +
                            `got stream_id=${messageStreamId}, chunk_index=${chunkData.chunk_index}`
                        );
                        return; // 忽略过期的chunk
                    }
                }
                
                // Convert to TTSChunkData format for streaming player
                const chunk: TTSChunkData = {
                    chunk_index: chunkData.chunk_index,
                    audio: chunkData.audio,
                    duration_ms: chunkData.duration_ms,
                    is_final: chunkData.is_final,
                    text: chunkData.text,
                    total_duration_ms: chunkData.total_duration_ms,
                    audio_format: chunkData.audio_format,
                    sample_rate: chunkData.sample_rate,
                };
                
                // Notify callback
                onTTSChunk?.(chunk);
                
                // P1-7: Unified TTS chunk handling (extracted from duplicate branches)
                // Initialize player on first chunk
                if (chunkData.chunk_index === 0) {
                    if (isPCMChunk) {
                        streamingPlayer.reset();
                    } else {
                        streamingPlayer.start();
                    }
                    if (useStreamingTTS) {
                        setState(prev => ({ 
                            ...prev, 
                            isStreamingTTS: true,
                            aiState: "speaking",
                        }));
                        debug.log("[TTS Streaming] Started streaming playback");
                    }
                }
                
                // Append chunk to player
                streamingPlayer.appendChunk(chunk);
                
                // Handle final chunk - add message and end stream
                if (chunkData.is_final) {
                    if (chunkData.text) {
                        addAiMessageIfNew(chunkData.text);
                    }
                    streamingPlayer.end();
                    debug.log("[TTS Streaming] Stream ended, total duration:", chunkData.total_duration_ms, "ms");
                }
                break;
            }

            case "status": {
                const data = message.data as {
                    ai_state?: string;
                    session_status?: string;
                    connection_state?: string;
                };
                debug.log("[PracticeWS] Status update", {
                    traceId: message.trace_id || null,
                    aiState: data.ai_state || null,
                    sessionStatus: data.session_status || null,
                    connectionState: data.connection_state || null,
                });
                setState(prev => {
                    const next: PracticeState = { ...prev };
                    if (data.ai_state) {
                        next.aiState = data.ai_state as PracticeState["aiState"];
                    }
                    if (data.session_status) {
                        next.sessionStatus = data.session_status as SessionStatus;
                    }
                    if (
                        data.connection_state
                        && ["connecting", "connected", "reconnecting", "failed"].includes(data.connection_state)
                    ) {
                        const connectionState = data.connection_state as ConnectionState;
                        next.connectionState = connectionState;
                        next.isConnected = connectionState === "connected";
                        next.isConnecting = connectionState === "connecting" || connectionState === "reconnecting";
                    }
                    if (
                        next.aiState === prev.aiState
                        && next.sessionStatus === prev.sessionStatus
                        && next.connectionState === prev.connectionState
                    ) {
                        return prev;
                    }
                    return next;
                });
                break;
            }

            case "session_ended": {
                const data = message.data as { session_status?: string };
                debug.log("[PracticeWS] Session ended", {
                    traceId: message.trace_id || null,
                    sessionStatus: data.session_status || "completed",
                });
                setState(prev => ({
                    ...prev,
                    sessionStatus: (data.session_status || "completed") as SessionStatus,
                    aiState: "idle",
                    isPlayingAudio: false,
                    isStreamingTTS: false,
                }));
                break;
            }

            /**
             * Handle interrupt confirmation from backend
             * 
             * Property 9: Interrupt Confirmation
             * Property 10: Interrupt State Transition Timing
             * 
             * Validates: Requirements 3.5, 3.6
             */
            case "interrupted": {
                const data = message.data as { reason: string };
                
                // Critical Fix #2: 检查stream_id，只停止被中断的那个流
                const interruptedStreamId = message.stream_id;
                
                if (interruptedStreamId && interruptedStreamId !== currentStreamIdRef.current) {
                    // 这是一个过期流的中断消息，忽略
                    debug.log(
                        `[Interrupt] Ignoring stale interrupt: interrupted_stream=${interruptedStreamId}, ` +
                        `current_stream=${currentStreamIdRef.current}`
                    );
                    break;
                }
                
                // 清除当前stream_id，表示没有活跃的TTS流
                if (interruptedStreamId) {
                    currentStreamIdRef.current = null;
                }
                
                // Ensure playback is stopped (in case it wasn't already)
                streamingPlayer.interrupt();
                
                // Clear any non-streaming audio
                audioQueueRef.current = [];
                isPlayingRef.current = false;
                
                // Cancel browser speech synthesis
                if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                }
                
                // Transition to listening state (Property 10)
                setState(prev => ({
                    ...prev,
                    isPlayingAudio: false,
                    aiState: "listening",
                    isStreamingTTS: false,
                }));
                
                debug.log(`[Interrupt] Received confirmation from backend (reason: ${data.reason}, stream_id: ${interruptedStreamId})`);
                break;
            }

            case "fuzzy_detection": {
                const data = message.data as { detections: FuzzyDetection[] };
                setState(prev => ({
                    ...prev,
                    fuzzyDetections: data.detections,
                }));
                break;
            }

            case "stage_update": {
                const data = message.data as SalesStage;
                setState(prev => {
                    if (isSameSalesStage(prev.salesStage, data)) {
                        return prev;
                    }
                    return {
                        ...prev,
                        salesStage: data,
                    };
                });
                break;
            }

            case "score_update": {
                const data = message.data as ScoreUpdate;
                setState(prev => {
                    // Idempotent update: only update if score data changed
                    if (prev.scores &&
                        prev.scores.overall_score === data.overall_score &&
                        prev.scores.turn_count === data.turn_count) {
                        return prev;
                    }
                    return {
                        ...prev,
                        scores: data,
                    };
                });
                break;
            }

            case "feedback": {
                const data = message.data as { message?: string };
                if (data.message) {
                    setState(prev => ({
                        ...prev,
                        fuzzyDetections: [{
                            category: "feedback",
                            matched: [],
                            suggestion: data.message || "",
                            severity: "medium",
                        }],
                    }));
                }
                break;
            }

            case "error": {
                const data = message.data as { message: string };
                debug.error("[PracticeWS] Backend error message", {
                    traceId: message.trace_id || null,
                    errorMessage: data.message,
                });
                setState(prev => ({ ...prev, error: data.message }));
                onError?.(data.message);
                break;
            }

            case "slide_update": {
                const raw = message.data as SlideUpdate;
                setState(prev => ({
                    ...prev,
                    currentSlide: {
                        current_page: raw.current_page ?? raw.page_number ?? prev.currentSlide?.current_page ?? 1,
                        page_number: raw.page_number ?? raw.current_page ?? prev.currentSlide?.page_number,
                        total_pages: raw.total_pages ?? prev.currentSlide?.total_pages ?? null,
                        content: raw.content ?? raw.page_content ?? prev.currentSlide?.content,
                        page_content: raw.page_content ?? raw.content ?? prev.currentSlide?.page_content,
                        image_url: raw.image_url ?? prev.currentSlide?.image_url,
                    },
                }));
                break;
            }

            case "point_covered": {
                const data = message.data as PointCovered;
                setState(prev => {
                    const existingIndex = prev.points.findIndex(p => p.point_id === data.point_id);
                    if (existingIndex >= 0) {
                        const updatedPoints = [...prev.points];
                        updatedPoints[existingIndex] = data;
                        return { ...prev, points: updatedPoints };
                    }
                    return { ...prev, points: [...prev.points, data] };
                });
                break;
            }

            case "points_reset": {
                setState(prev => {
                    if (prev.points.length === 0) {
                        return prev;
                    }
                    return { ...prev, points: [] };
                });
                break;
            }

            case "forbidden_word": {
                const data = message.data as { detections: ForbiddenWordDetection[] };
                // NEW-12 Fix: Cap forbiddenWords to last 10 entries to prevent unbounded growth
                setState(prev => {
                    const updated = [...prev.forbiddenWords, ...data.detections];
                    return {
                        ...prev,
                        forbiddenWords: updated.length > 10 ? updated.slice(-10) : updated,
                    };
                });
                break;
            }

            case "heartbeat":
                sendMessage?.("heartbeat_ack", { client_ts: new Date().toISOString() });
                break;

            case "reconnected": {
                const data = message.data as {
                    restored_state?: {
                        session_status?: SessionStatus;
                        ai_state?: PracticeState["aiState"];
                    };
                };
                const restored = data?.restored_state;
                setState(prev => ({
                    ...prev,
                    connectionState: "connected",
                    isConnected: true,
                    isConnecting: false,
                    error: null,
                    sessionStatus: (restored?.session_status || prev.sessionStatus) as SessionStatus,
                    aiState: (restored?.ai_state || prev.aiState) as PracticeState["aiState"],
                }));
                break;
            }

            case "session_timeout": {
                const data = message.data as { message?: string };
                setState(prev => ({
                    ...prev,
                    connectionState: "failed",
                    isConnected: false,
                    isConnecting: false,
                    aiState: "idle",
                    isPlayingAudio: false,
                    isStreamingTTS: false,
                    error: data?.message || "会话超时，请重新开始",
                }));
                onError?.(data?.message || "会话超时，请重新开始");
                break;
            }

            /**
             * Handle backpressure signal from backend
             * 
             * Requirements: Voice Practice Optimization P0-2
             * - slow_down: Pause sending audio, buffer locally
             * - resume: Flush local buffer and resume normal sending
             */
            case "backpressure": {
                const data = message.data as { action: string; queue_size: number };
                const isSlowDown = data.action === "slow_down";
                
                isBackpressureActiveRef.current = isSlowDown;
                setState(prev => ({ ...prev, isBackpressureActive: isSlowDown }));
                
                if (isSlowDown) {
                    debug.warn(`[Backpressure] Activated - server queue size: ${data.queue_size}`);
                } else {
                    debug.log(`[Backpressure] Deactivated - server queue size: ${data.queue_size}`);
                    // Flush local buffer when backpressure is released
                    flushLocalAudioBuffer();
                }
                break;
            }

            default:
                debug.log("Unknown message type:", message.type);
        }
    } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
    }
}
