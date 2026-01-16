"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useStreamingAudioPlayer, TTSChunkData, InterruptReason } from "./use-streaming-audio-player";

// Re-export InterruptReason for consumers
export type { InterruptReason } from "./use-streaming-audio-player";

/**
 * Interrupt message data sent to backend
 * 
 * Property 6: Interrupt Stops Playback
 * Property 7: Interrupt Queue Clearing
 * 
 * Validates: Requirements 3.1, 3.2
 */
export interface InterruptMessageData {
    reason: InterruptReason;
    timestamp: number;
}

// WebSocket 消息类型
// Critical Fix #2: 添加stream_id和request_id字段用于消息版本控制
export interface WSMessage {
    type: string;
    timestamp: string;
    trace_id?: string;
    stream_id?: string;  // TTS流ID，用于识别消息属于哪个流
    request_id?: number;  // 请求ID，用于识别消息属于哪个请求
    data: unknown;
}

export interface ChatMessage {
    id: string;
    sender: "user" | "ai";
    message: string;
    timestamp: string;
}

export interface FuzzyDetection {
    category: string;
    matched: string[];
    suggestion: string;
    severity: "high" | "medium" | "low";
}

export interface SalesStage {
    current_stage: string;
    stage_name: string;
    key_actions: string[];
    guidance: string;
    progress: number;
}

export interface ScoreDimension {
    name: string;
    score: number;
    trend: "up" | "down" | "stable";
    delta: number;
}

export interface ScoreUpdate {
    overall: number;
    dimensions: ScoreDimension[];
    feedback?: string;
}

export interface TTSAudioData {
    text: string;
    audio: string;
    duration_ms: number;
    fallback?: string;
}

/**
 * TTS Chunk message data from WebSocket
 * Used for streaming TTS playback
 */
export interface TTSChunkMessage {
    chunk_index: number;
    audio: string;        // Base64 encoded MP3 chunk
    duration_ms: number;
    is_final: boolean;
    text?: string;        // Only on final chunk
    total_duration_ms?: number;  // Only on final chunk
}

export interface PracticeState {
    isConnected: boolean;
    isConnecting: boolean;
    aiState: "listening" | "thinking" | "speaking" | "idle";
    messages: ChatMessage[];
    fuzzyDetections: FuzzyDetection[];
    salesStage: SalesStage | null;
    scores: ScoreUpdate | null;
    error: string | null;
    isPlayingAudio: boolean;
    interimTranscript: string;
    audioUnlocked: boolean;
    /** Whether streaming TTS is currently active */
    isStreamingTTS: boolean;
    /** Whether backpressure is active (audio sending should pause) */
    isBackpressureActive: boolean;
    /** Whether network is slow (backpressure buffer overflow detected) */
    isNetworkSlow: boolean;
}

interface UsePracticeWebSocketOptions {
    sessionId: string;
    agentId?: string;
    personaId?: string;
    onMessage?: (message: WSMessage) => void;
    onError?: (error: string) => void;
    onTTSAudio?: (data: TTSAudioData) => void;
    /** Callback when a TTS chunk is received (for streaming) */
    onTTSChunk?: (data: TTSChunkData) => void;
    /** Whether to use streaming TTS playback (default: true) */
    useStreamingTTS?: boolean;
}

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export function usePracticeWebSocket(options: UsePracticeWebSocketOptions) {
    const { 
        sessionId, 
        agentId, 
        personaId, 
        onMessage, 
        onError, 
        onTTSAudio,
        onTTSChunk,
        useStreamingTTS = true,
    } = options;
    
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const maxReconnectAttempts = 5;
    const audioQueueRef = useRef<TTSAudioData[]>([]);
    const isPlayingRef = useRef(false);
    const audioUnlockedRef = useRef(false);
    const isConnectingRef = useRef(false);
    
    // Streaming audio player for tts_chunk messages
    const streamingPlayer = useStreamingAudioPlayer({
        onPlaybackStart: () => {
            setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));
        },
        onPlaybackEnd: () => {
            setState(prev => ({ 
                ...prev, 
                isPlayingAudio: false, 
                aiState: "listening",
                isStreamingTTS: false,
            }));
        },
        onError: (error) => {
            console.error("[StreamingTTS] Error:", error);
            setState(prev => ({ 
                ...prev, 
                isPlayingAudio: false, 
                aiState: "listening",
                isStreamingTTS: false,
            }));
        },
    });
    
    // Track current streaming TTS text for message display
    const currentStreamingTextRef = useRef<string | null>(null);
    
    // Critical Fix #2: 跟踪当前TTS流ID，用于过滤过期的TTS消息
    const currentStreamIdRef = useRef<string | null>(null);
    const currentRequestIdRef = useRef<number>(0);
    
    // Backpressure control state (Requirements: Voice Practice Optimization P0-2)
    const isBackpressureActiveRef = useRef(false);
    const localAudioBufferRef = useRef<string[]>([]);  // Buffer for audio during backpressure
    const MAX_LOCAL_BUFFER_SIZE = 200;  // ~4 seconds of audio at 20ms chunks
    
    // Critical Fix #4: 添加flushing标志防止flush和sendAudio交错
    const isFlushingRef = useRef(false);
    
    const [state, setState] = useState<PracticeState>({
        isConnected: false,
        isConnecting: false,
        aiState: "idle",
        messages: [],
        fuzzyDetections: [],
        salesStage: null,
        scores: null,
        error: null,
        isPlayingAudio: false,
        interimTranscript: "",
        audioUnlocked: false,
        isStreamingTTS: false,
        isBackpressureActive: false,
        isNetworkSlow: false,
    });

    const getToken = useCallback(() => {
        if (typeof window !== "undefined") {
            return localStorage.getItem("token") || "";
        }
        return "";
    }, []);

    const buildWsUrl = useCallback(() => {
        const token = getToken();
        let url = `${WS_BASE_URL}/ws/sales?session_id=${sessionId}&token=${token}`;
        if (agentId) url += `&agent_id=${agentId}`;
        if (personaId) url += `&persona_id=${personaId}`;
        return url;
    }, [sessionId, agentId, personaId, getToken]);

    // 处理音频队列
    const processAudioQueue = useCallback(() => {
        if (isPlayingRef.current || audioQueueRef.current.length === 0) {
            return;
        }
        
        if (!audioUnlockedRef.current) {
            // 音频未解锁，保存到待播放列表
            return;
        }
        
        isPlayingRef.current = true;
        const nextAudio = audioQueueRef.current.shift();
        if (nextAudio) {
            playTTSAudioInternal(nextAudio);
        } else {
            isPlayingRef.current = false;
        }
    }, []);

    // 内部播放函数
    const playTTSAudioInternal = useCallback(async (data: TTSAudioData) => {
        // 使用浏览器 TTS 作为 fallback
        if (data.fallback === "browser_tts" || !data.audio) {
            if ("speechSynthesis" in window) {
                const utterance = new SpeechSynthesisUtterance(data.text);
                utterance.lang = "zh-CN";
                utterance.onend = () => {
                    setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                    isPlayingRef.current = false;
                    processAudioQueue();
                };
                utterance.onerror = () => {
                    setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                    isPlayingRef.current = false;
                    processAudioQueue();
                };
                window.speechSynthesis.speak(utterance);
                setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));
            } else {
                isPlayingRef.current = false;
                processAudioQueue();
            }
            return;
        }

        try {
            const binaryString = atob(data.audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const blob = new Blob([bytes], { type: "audio/mp3" });
            const audioUrl = URL.createObjectURL(blob);
            const audio = new Audio(audioUrl);

            setState(prev => ({ ...prev, isPlayingAudio: true, aiState: "speaking" }));

            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                isPlayingRef.current = false;
                processAudioQueue();
            };

            audio.onerror = () => {
                URL.revokeObjectURL(audioUrl);
                setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
                isPlayingRef.current = false;
                // 回退到浏览器 TTS
                if ("speechSynthesis" in window) {
                    const utterance = new SpeechSynthesisUtterance(data.text);
                    utterance.lang = "zh-CN";
                    window.speechSynthesis.speak(utterance);
                }
                processAudioQueue();
            };

            await audio.play();
        } catch (e) {
            console.error("Failed to play TTS audio:", e);
            setState(prev => ({ ...prev, isPlayingAudio: false, aiState: "listening" }));
            isPlayingRef.current = false;
            // 回退到浏览器 TTS
            if ("speechSynthesis" in window) {
                const utterance = new SpeechSynthesisUtterance(data.text);
                utterance.lang = "zh-CN";
                window.speechSynthesis.speak(utterance);
            }
            processAudioQueue();
        }
    }, [processAudioQueue]);

    // 添加音频到队列
    const queueTTSAudio = useCallback((data: TTSAudioData) => {
        audioQueueRef.current.push(data);
        onTTSAudio?.(data);
        
        if (audioUnlockedRef.current && !isPlayingRef.current) {
            processAudioQueue();
        }
    }, [onTTSAudio, processAudioQueue]);

    // 解锁音频 - 用户点击"开始"按钮时调用
    const unlockAudio = useCallback(async () => {
        if (audioUnlockedRef.current) return;
        
        try {
            // 播放一个静音音频来解锁
            const audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
            
            if (audioContext.state === "suspended") {
                await audioContext.resume();
            }
            
            // 创建一个短暂的静音缓冲区并播放
            const buffer = audioContext.createBuffer(1, 1, 22050);
            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);
            source.start(0);
            
            audioUnlockedRef.current = true;
            setState(prev => ({ ...prev, audioUnlocked: true }));
            
            // 播放待播放的音频
            if (audioQueueRef.current.length > 0 && !isPlayingRef.current) {
                processAudioQueue();
            }
            
            console.log("Audio unlocked successfully");
        } catch (e) {
            console.error("Failed to unlock audio:", e);
            // 即使失败也标记为已解锁，让后续尝试播放
            audioUnlockedRef.current = true;
            setState(prev => ({ ...prev, audioUnlocked: true }));
        }
    }, [processAudioQueue]);

    // 处理收到的消息
    const handleMessage = useCallback((event: MessageEvent) => {
        try {
            const message: WSMessage = JSON.parse(event.data);
            onMessage?.(message);

            switch (message.type) {
                case "connected":
                    setState(prev => ({ ...prev, isConnected: true, isConnecting: false, error: null }));
                    break;

                case "transcript":
                case "asr_transcript": {
                    const data = message.data as { text: string; is_final: boolean };
                    
                    if (data.is_final) {
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
                                messages: [...prev.messages, newMsg],
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
                        // 中间结果：更新显示
                        setState(prev => ({
                            ...prev,
                            interimTranscript: data.text,
                        }));
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
                        messages: [...prev.messages, newMsg],
                        aiState: "speaking",
                    }));
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
                            console.log(`[TTS Audio] New stream: stream_id=${messageStreamId}, request_id=${messageRequestId}`);
                            currentStreamIdRef.current = messageStreamId;
                            if (messageRequestId !== undefined) {
                                currentRequestIdRef.current = messageRequestId;
                            }
                        }
                    }
                    
                    // 检查是否已有相同文本的消息（避免重复）
                    setState(prev => {
                        // 检查所有消息中是否已存在相同文本的 AI 消息
                        const isDuplicate = prev.messages.some(
                            msg => msg.sender === "ai" && msg.message === data.text
                        );
                        if (isDuplicate) {
                            return prev;
                        }
                        const newMsg: ChatMessage = {
                            id: `ai-${Date.now()}`,
                            sender: "ai",
                            message: data.text,
                            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
                        };
                        return {
                            ...prev,
                            messages: [...prev.messages, newMsg],
                            aiState: "speaking",
                        };
                    });
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
                    
                    // Critical Fix #2: 检查stream_id，过滤过期的TTS chunk
                    const messageStreamId = message.stream_id;
                    const messageRequestId = message.request_id;
                    
                    // 如果这是第一个chunk (chunk_index === 0)，更新当前的stream_id
                    if (chunkData.chunk_index === 0) {
                        if (messageStreamId) {
                            console.log(`[TTS] New stream started: stream_id=${messageStreamId}, request_id=${messageRequestId}`);
                            currentStreamIdRef.current = messageStreamId;
                            if (messageRequestId !== undefined) {
                                currentRequestIdRef.current = messageRequestId;
                            }
                        }
                    } else {
                        // 对于非首chunk，检查stream_id是否匹配
                        if (messageStreamId && messageStreamId !== currentStreamIdRef.current) {
                            console.warn(
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
                    };
                    
                    // Notify callback
                    onTTSChunk?.(chunk);
                    
                    // Handle streaming TTS if enabled
                    if (useStreamingTTS) {
                        // Initialize player on first chunk (Property 4: Streaming Playback Initialization)
                        if (chunkData.chunk_index === 0) {
                            streamingPlayer.start();
                            setState(prev => ({ 
                                ...prev, 
                                isStreamingTTS: true,
                                aiState: "speaking",
                            }));
                            console.log("[TTS Streaming] Started streaming playback");
                        }
                        
                        // Append chunk to player (Property 5: MediaSource Buffer Appending)
                        streamingPlayer.appendChunk(chunk);
                        
                        // Handle final chunk - add message and end stream
                        if (chunkData.is_final) {
                            // Add AI message to chat when we have the full text
                            if (chunkData.text) {
                                setState(prev => {
                                    // 检查所有消息中是否已存在相同文本的 AI 消息
                                    const isDuplicate = prev.messages.some(
                                        msg => msg.sender === "ai" && msg.message === chunkData.text
                                    );
                                    if (isDuplicate) {
                                        return prev;
                                    }
                                    const newMsg: ChatMessage = {
                                        id: `ai-${Date.now()}`,
                                        sender: "ai",
                                        message: chunkData.text || "",
                                        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
                                    };
                                    return {
                                        ...prev,
                                        messages: [...prev.messages, newMsg],
                                    };
                                });
                            }
                            
                            // Signal end of stream
                            streamingPlayer.end();
                            console.log("[TTS Streaming] Stream ended, total duration:", chunkData.total_duration_ms, "ms");
                        }
                    } else {
                        // Fallback: collect all chunks and play when final
                        // This is handled by the streaming player's fallback mode
                        if (chunkData.chunk_index === 0) {
                            streamingPlayer.start();
                        }
                        streamingPlayer.appendChunk(chunk);
                        if (chunkData.is_final) {
                            streamingPlayer.end();
                            if (chunkData.text) {
                                setState(prev => {
                                    // 检查所有消息中是否已存在相同文本的 AI 消息
                                    const isDuplicate = prev.messages.some(
                                        msg => msg.sender === "ai" && msg.message === chunkData.text
                                    );
                                    if (isDuplicate) {
                                        return prev;
                                    }
                                    const newMsg: ChatMessage = {
                                        id: `ai-${Date.now()}`,
                                        sender: "ai",
                                        message: chunkData.text || "",
                                        timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
                                    };
                                    return {
                                        ...prev,
                                        messages: [...prev.messages, newMsg],
                                    };
                                });
                            }
                        }
                    }
                    break;
                }

                case "status": {
                    const data = message.data as { ai_state?: string };
                    if (data.ai_state) {
                        setState(prev => ({
                            ...prev,
                            aiState: data.ai_state as PracticeState["aiState"],
                        }));
                    }
                    break;
                }

                /**
                 * Handle interrupt confirmation from backend
                 * 
                 * Property 9: Interrupt Confirmation
                 * - Backend sends "interrupted" message after processing interrupt
                 * 
                 * Property 10: Interrupt State Transition Timing
                 * - Transition to "listening" state within 100ms
                 * 
                 * Validates: Requirements 3.5, 3.6
                 */
                case "interrupted": {
                    const data = message.data as { reason: string };
                    
                    // Critical Fix #2: 检查stream_id，只停止被中断的那个流
                    const interruptedStreamId = message.stream_id;
                    
                    if (interruptedStreamId && interruptedStreamId !== currentStreamIdRef.current) {
                        // 这是一个过期流的中断消息，忽略
                        console.log(
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
                    
                    console.log(`[Interrupt] Received confirmation from backend (reason: ${data.reason}, stream_id: ${interruptedStreamId})`);
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
                    setState(prev => ({
                        ...prev,
                        salesStage: data,
                    }));
                    break;
                }

                case "score_update": {
                    const data = message.data as ScoreUpdate;
                    setState(prev => ({
                        ...prev,
                        scores: data,
                    }));
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
                    setState(prev => ({ ...prev, error: data.message }));
                    onError?.(data.message);
                    break;
                }

                case "heartbeat":
                    break;

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
                        console.warn(`[Backpressure] Activated - server queue size: ${data.queue_size}`);
                    } else {
                        console.log(`[Backpressure] Deactivated - server queue size: ${data.queue_size}`);
                        // Flush local buffer when backpressure is released
                        flushLocalAudioBuffer();
                    }
                    break;
                }

                default:
                    console.log("Unknown message type:", message.type);
            }
        } catch (e) {
            console.error("Failed to parse WebSocket message:", e);
        }
    }, [onMessage, onError, queueTTSAudio]);

    // 连接状态 ref，避免 StrictMode 重复连接
    // (isConnectingRef 已在上面声明)

    // 连接 WebSocket
    const connect = useCallback(() => {
        // 防止重复连接
        if (isConnectingRef.current) {
            return;
        }
        if (wsRef.current?.readyState === WebSocket.OPEN || 
            wsRef.current?.readyState === WebSocket.CONNECTING) {
            return;
        }

        isConnectingRef.current = true;
        setState(prev => ({ ...prev, isConnecting: true, error: null }));

        const url = buildWsUrl();
        const ws = new WebSocket(url);

        ws.onopen = () => {
            console.log("WebSocket connected");
            reconnectAttempts.current = 0;
            isConnectingRef.current = false;
            setState(prev => ({ ...prev, isConnected: true, isConnecting: false }));
        };

        ws.onmessage = handleMessage;

        ws.onerror = () => {
            isConnectingRef.current = false;
            if (ws.readyState !== WebSocket.CLOSED) {
                setState(prev => ({ ...prev, error: "连接错误" }));
            }
        };

        ws.onclose = (event) => {
            console.log("WebSocket closed:", event.code, event.reason);
            isConnectingRef.current = false;
            setState(prev => ({ ...prev, isConnected: false, isConnecting: false }));

            if (reconnectAttempts.current < maxReconnectAttempts && 
                event.code !== 1000 && 
                event.code !== 1001) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
                reconnectAttempts.current++;
                console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);
                setTimeout(connect, delay);
            }
        };

        wsRef.current = ws;
    }, [buildWsUrl, handleMessage]);

    const disconnect = useCallback(() => {
        isConnectingRef.current = false;
        if (wsRef.current) {
            wsRef.current.close(1000, "User disconnected");
            wsRef.current = null;
        }
    }, []);

    const sendMessage = useCallback((type: string, data: unknown) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const message: WSMessage = {
                type,
                timestamp: new Date().toISOString(),
                data,
            };
            wsRef.current.send(JSON.stringify(message));
        }
    }, []);

    const sendText = useCallback((content: string) => {
        sendMessage("text", { content });
        const newMsg: ChatMessage = {
            id: `user-${Date.now()}`,
            sender: "user",
            message: content,
            timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        };
        setState(prev => ({
            ...prev,
            messages: [...prev.messages, newMsg],
        }));
    }, [sendMessage]);

    /**
     * Flush local audio buffer when backpressure is released
     * 
     * Sends buffered audio chunks with rate limiting to avoid
     * immediately overwhelming the server again.
     * 
     * Critical Fix #4: 添加flushing标志防止与sendAudio交错
     * 
     * Requirements: Voice Practice Optimization P0-2
     */
    const flushLocalAudioBuffer = useCallback(() => {
        if (localAudioBufferRef.current.length === 0) {
            return;
        }
        
        // Critical Fix #4: 设置flushing标志，防止新的sendAudio调用交错
        if (isFlushingRef.current) {
            console.log("[Backpressure] Already flushing, skipping duplicate flush");
            return;
        }
        
        isFlushingRef.current = true;
        const chunksToSend = localAudioBufferRef.current.splice(0);
        console.log(`[Backpressure] Flushing ${chunksToSend.length} buffered audio chunks`);
        
        // Send chunks with 10ms interval to avoid overwhelming server
        let index = 0;
        const sendNext = () => {
            if (index < chunksToSend.length && !isBackpressureActiveRef.current) {
                sendMessage("audio_chunk", {
                    audio: chunksToSend[index],
                    sample_rate: 16000,
                    interrupt: false,
                });
                index++;
                setTimeout(sendNext, 10);  // 10ms interval between chunks
            } else {
                // Flush完成，清除标志
                isFlushingRef.current = false;
                if (index >= chunksToSend.length) {
                    console.log(`[Backpressure] Flush complete, sent ${index} chunks`);
                }
            }
        };
        sendNext();
    }, [sendMessage]);

    /**
     * Send audio data with backpressure awareness
     * 
     * When backpressure is active, audio is buffered locally instead
     * of being sent immediately.
     * 
     * Critical Fix #4: 在flushing期间将音频加入buffer，防止交错
     * 
     * Requirements: Voice Practice Optimization P0-2
     */
    const sendAudio = useCallback((audioData: string, interrupt = false) => {
        // Interrupt messages bypass backpressure
        if (interrupt) {
            sendMessage("audio_chunk", {
                audio: audioData,
                sample_rate: 16000,
                interrupt: true,
            });
            return;
        }
        
        // Critical Fix #4: 如果正在flushing或backpressure激活，则缓冲
        if (isBackpressureActiveRef.current || isFlushingRef.current) {
            // Enforce local buffer limit to prevent memory issues
            if (localAudioBufferRef.current.length >= MAX_LOCAL_BUFFER_SIZE) {
                // Drop oldest chunk and notify user about slow network
                localAudioBufferRef.current.shift();
                console.warn("[Backpressure] Local buffer full, dropping oldest chunk");
                // Set network slow flag to notify user
                setState(prev => {
                    if (!prev.isNetworkSlow) {
                        return { ...prev, isNetworkSlow: true };
                    }
                    return prev;
                });
            }
            localAudioBufferRef.current.push(audioData);
            
            // 如果是因为flushing而缓冲，记录日志
            if (isFlushingRef.current && !isBackpressureActiveRef.current) {
                console.log("[Backpressure] Buffering audio during flush");
            }
            return;
        }
        
        // Normal send - clear network slow flag if it was set
        setState(prev => {
            if (prev.isNetworkSlow) {
                return { ...prev, isNetworkSlow: false };
            }
            return prev;
        });
        
        sendMessage("audio_chunk", {
            audio: audioData,
            sample_rate: 16000,
            interrupt: false,
        });
    }, [sendMessage]);

    const sendAudioEnd = useCallback(() => {
        sendMessage("audio_end", {});
        // 清空中间转录结果，避免残留显示
        setState(prev => ({ ...prev, interimTranscript: "" }));
    }, [sendMessage]);

    const commitAudio = useCallback(() => {
        sendMessage("user_speaking", { speaking: false });
    }, [sendMessage]);

    const startSpeaking = useCallback(() => {
        sendMessage("user_speaking", { speaking: true });
    }, [sendMessage]);

    const sendControl = useCallback((action: "pause" | "resume" | "end") => {
        sendMessage("control", { action });
    }, [sendMessage]);

    /**
     * Send an interrupt signal to stop AI response
     * 
     * This function implements the complete interrupt handling flow:
     * 1. Immediately stops TTS playback (Property 6)
     * 2. Clears the audio chunk queue (Property 7)
     * 3. Sends interrupt message with reason and timestamp
     * 
     * Property 6: Interrupt Stops Playback
     * - Audio stops within the same event loop tick as interrupt detection
     * 
     * Property 7: Interrupt Queue Clearing
     * - Queue is cleared BEFORE sending the interrupt signal
     * 
     * Validates: Requirements 3.1, 3.2
     * 
     * @param reason - The reason for the interrupt ('user_speaking' or 'manual')
     * @returns Object containing wasPlaying and clearedChunks info
     */
    const sendInterrupt = useCallback((reason: InterruptReason = 'user_speaking'): { wasPlaying: boolean; clearedChunks: number } => {
        // Step 1 & 2: Immediately stop TTS playback and clear queue
        // This happens synchronously in the same event loop tick
        const { wasPlaying, clearedChunks } = streamingPlayer.interrupt();
        
        // Also stop any non-streaming audio playback
        if (isPlayingRef.current) {
            isPlayingRef.current = false;
        }
        
        // Clear the non-streaming audio queue as well
        const nonStreamingQueueLength = audioQueueRef.current.length;
        audioQueueRef.current = [];
        
        // Cancel any browser speech synthesis
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        
        // Update state immediately
        setState(prev => ({
            ...prev,
            isPlayingAudio: false,
            aiState: "listening",
            isStreamingTTS: false,
        }));
        
        // Step 3: Send interrupt message with reason and timestamp
        // This happens AFTER the queue is cleared (Property 7)
        const interruptData: InterruptMessageData = {
            reason,
            timestamp: Date.now(),
        };
        
        sendMessage("interrupt", interruptData);
        
        const totalCleared = clearedChunks + nonStreamingQueueLength;
        console.log(`[Interrupt] Sent interrupt signal (reason: ${reason}, wasPlaying: ${wasPlaying}, clearedChunks: ${totalCleared})`);
        
        return { wasPlaying, clearedChunks: totalCleared };
    }, [streamingPlayer, sendMessage]);

    useEffect(() => {
        connect();
        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    return {
        ...state,
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
        /** Stop streaming TTS playback */
        stopStreamingTTS: streamingPlayer.stop,
        /** Reset streaming TTS player */
        resetStreamingTTS: streamingPlayer.reset,
        /** Streaming player state */
        streamingPlayerState: streamingPlayer.state,
        /** Clear the streaming audio queue */
        clearStreamingQueue: streamingPlayer.clearQueue,
        /** Interrupt streaming playback (stop + clear queue) */
        interruptStreamingTTS: streamingPlayer.interrupt,
        /** Flush local audio buffer (for backpressure control) */
        flushLocalAudioBuffer,
    };
}
